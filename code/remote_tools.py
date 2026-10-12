"""SSH bridge to a privately configured Codex Science Linux runtime."""
from __future__ import annotations
import hashlib,json,os,re,shlex,socket,time
from pathlib import Path
from typing import Literal

PROJECT=Path(__file__).resolve().parents[1]

def config():
    p=Path(os.environ.get('CODEX_SCIENCE_REMOTE_CONFIG',str(PROJECT/'.local/remote.json'))).expanduser()
    if not p.is_file():raise RuntimeError('Configure a private CODEX_SCIENCE_REMOTE_CONFIG JSON file; see docs/remote.md')
    return json.loads(p.read_text(encoding='utf-8-sig'))

def connect():
    import paramiko
    cfg=config();client=paramiko.SSHClient();keys=paramiko.HostKeys(str(Path(cfg['known_hosts']).expanduser()))
    known=keys.lookup(cfg.get('host_key_alias',cfg['host']))
    if not known:raise RuntimeError('No verified host key for the configured server')
    destination=cfg['host'] if cfg.get('port',22)==22 else '[%s]:%s'%(cfg['host'],cfg['port'])
    matched=False
    for kind,key in known.items():
        if hashlib.sha256(key.asbytes()).hexdigest()==cfg['host_key_sha256']:
            client.get_host_keys().add(destination,kind,key);matched=True
    if not matched:raise RuntimeError('Configured host fingerprint differs from saved host identity')
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    password=os.environ.get(cfg.get('password_env',''))
    if not password and cfg.get('credentials_markdown'):
        rows=Path(cfg['credentials_markdown']).read_text(encoding='utf-8-sig').splitlines()
        pattern=r'\|\s*'+re.escape(cfg['credential_server'])+r'\s*\|'
        candidates=[]
        for row in rows:
            if not re.match(pattern,row):continue
            fields=[v.strip().strip('`') for v in row.split('|')]
            if len(fields)>5 and fields[2]==cfg['user']:candidates.append(fields)
        if len(candidates)!=1:raise RuntimeError('Credential source must have exactly one matching server/account row')
        fields=candidates[0]
        if fields[5]!=str(cfg['host'])+':'+str(cfg.get('port',22)):raise RuntimeError('Credential source endpoint differs from private profile')
        password=fields[3]
    key_file=cfg.get('identity_file')
    if not password and not key_file:raise RuntimeError('Configure an identity file or private credential source')
    for attempt in range(3):
        try:
            client.connect(cfg['host'],port=cfg.get('port',22),username=cfg['user'],password=password,key_filename=key_file,look_for_keys=False,allow_agent=False,timeout=10,auth_timeout=15,banner_timeout=15)
            break
        except (TimeoutError,ConnectionError,socket.timeout):
            client.close()
            if attempt==2:raise
            time.sleep(1)
        except Exception:
            client.close();raise
    return client,cfg

def request(action,params=None):
    body=json.dumps({'action':action,'params':params or {}},ensure_ascii=False)+'\n'
    if len(body.encode())>1_048_576:raise ValueError('Remote request exceeds one MiB')
    client,cfg=connect()
    try:
        root=cfg['root'];command=shlex.join([cfg.get('python',root+'/envs/runtime/bin/python'),root+'/code/remote_runtime.py','--root',root,'--request'])
        stdin,stdout,stderr=client.exec_command(command,timeout=120)
        stdin.write(body);stdin.flush();stdin.channel.shutdown_write()
        raw=stdout.read(2_000_001)
        if len(raw)>2_000_000:raise RuntimeError('Remote response exceeds transport limit')
        code=stdout.channel.recv_exit_status()
        if code:raise RuntimeError('Remote runtime command failed; check the server runtime logs')
        result=json.loads(raw)
        if not result.get('ok'):raise RuntimeError(result.get('error','Remote operation failed'))
        return result['result']
    finally:client.close()

def science_remote(action:Literal['health','sessions','session_start','session_execute','session_close','jobs','job_submit','job_status','job_cancel','job_logs','artifacts','artifact_info','file_write'],parameters:dict|None=None)->dict:
    """Operate the configured server: persistent Python/R sessions, detached jobs, logs and project artifacts.

    session_start: language python/r, project projects/main. session_execute: session_id, code, timeout<=90.
    job_submit: code, language python/r/bash, project, timeout<=604800, cpus. Jobs survive SSH disconnects.
    job_status/job_cancel/job_logs: job_id. file_write: project-relative path,text,overwrite=false.
    Execute only the user's authorized analysis. The remote account runs the submitted code.
    """
    result=request(action,parameters)
    return result if isinstance(result,dict) else {'items':result}

def science_fetch_artifact(remote_path:str,workspace:str,output:str)->dict:
    """Fetch one verified server artifact (up to 100 MiB) to a local workspace without overwriting files."""
    root=Path(workspace).expanduser().resolve(strict=True)
    relative=Path(output)
    target=(root/relative).resolve()
    if not root.is_dir() or relative.is_absolute() or relative.drive or target==root or not target.is_relative_to(root):raise ValueError('Use an output relative to the local workspace')
    if target.exists():raise FileExistsError(str(target))
    info=request('artifact_info',{'path':remote_path})
    if info['bytes']>100*1024*1024:raise ValueError('Keep large data on the server; fetch an explicitly selected smaller artifact')
    client,cfg=connect()
    created=False
    try:
        target.parent.mkdir(parents=True,exist_ok=True)
        with client.open_sftp() as sftp,target.open('xb') as out:
            created=True
            sftp.getfo(info['absolute_path'],out)
        digest=hashlib.sha256(target.read_bytes()).hexdigest()
        if digest!=info['sha256']:
            target.unlink();raise RuntimeError('Downloaded artifact differs from its source hash; retry after writing stops')
        return {'path':str(target),'remote_path':remote_path,'sha256':digest,'bytes':info['bytes']}
    except Exception:
        if created:target.unlink(missing_ok=True)
        raise
    finally:client.close()

def register_tools(mcp):
    mcp.tool()(science_remote);mcp.tool()(science_fetch_artifact)
