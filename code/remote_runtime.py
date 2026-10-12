"""Single-user Linux research runtime: persistent Jupyter kernels and detached jobs.

Access is through an owner-only Unix socket carried over authenticated SSH.
The service executes the account owner's analysis code; it is not a code sandbox.
"""
from __future__ import annotations
import argparse,fcntl,hashlib,json,os,re,signal,socket,socketserver,subprocess,sys,threading,time,uuid
from pathlib import Path
from queue import Empty

ROOT=Path(os.environ.get('CODEX_SCIENCE_REMOTE_ROOT',Path(__file__).resolve().parents[1])).resolve()
MAX_REQUEST=1_048_576
SESSIONS={}

def write_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)

def read_json(path): return json.loads(path.read_text(encoding='utf-8'))
def ident(value):
    if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{32}',value): raise ValueError('Invalid object identifier')
    return value

def scoped(relative,areas=('projects','sessions','jobs','reports')):
    if not isinstance(relative,str) or not relative or Path(relative).is_absolute(): raise ValueError('Use a relative project path')
    p=(ROOT/relative).resolve()
    if not any(p.is_relative_to(ROOT/a) for a in areas): raise ValueError('Path is outside the research directories')
    return p

def identity(pid):
    try:
        fields=Path('/proc/%d/stat'%pid).read_text().split(') ',1)[1].split()
        return fields[19] if fields[0]!='Z' else None
    except (OSError,IndexError): return None

def alive(record,prefix=''):
    pid=record.get(prefix+'pid');tick=record.get(prefix+'start_tick')
    return bool(pid and tick and identity(pid)==tick)

def stop_process(record,signum=signal.SIGTERM):
    if alive(record):
        pid=record['pid']
        if os.getpgid(pid)==pid: os.killpg(pid,signum)
        else: os.kill(pid,signum)

def _session(sid):
    sid=ident(sid)
    if sid in SESSIONS:
        if alive(SESSIONS[sid]['meta']):return SESSIONS[sid]
        SESSIONS.pop(sid)['client'].stop_channels()
    folder=ROOT/'sessions'/sid; meta=read_json(folder/'meta.json')
    if meta['status']!='running' or not alive(meta): raise RuntimeError('Session is stopped; saved notebook remains available')
    from jupyter_client import BlockingKernelClient
    client=BlockingKernelClient(connection_file=str(folder/'connection.json'))
    client.load_connection_file();client.start_channels();client.wait_for_ready(timeout=15)
    session={'meta':meta,'client':client,'manager':None,'folder':folder}
    SESSIONS[sid]=session
    return session

def session_start(language='python',project='projects/main',name='Analysis'):
    if language not in ('python','r'): raise ValueError('language must be python or r')
    path=scoped(project,('projects',));path.mkdir(parents=True,exist_ok=True)
    if len([p for p in (ROOT/'sessions').glob('*/meta.json') if alive(read_json(p))])>=8: raise ValueError('Close an existing session before starting more than eight')
    from jupyter_client import KernelManager
    sid=uuid.uuid4().hex;folder=ROOT/'sessions'/sid;folder.mkdir()
    km=KernelManager(kernel_name='python3' if language=='python' else 'codex-r',connection_file=str(folder/'connection.json'))
    log=(folder/'kernel.log').open('ab')
    try:
        km.start_kernel(cwd=str(path),stdout=log,stderr=log,independent=True)
        client=km.blocking_client();client.start_channels();client.wait_for_ready(timeout=40)
    except Exception:
        km.shutdown_kernel(now=True);raise
    finally: log.close()
    pid=km.provisioner.pid
    meta={'id':sid,'name':name,'language':language,'project':project,'status':'running','pid':pid,'start_tick':identity(pid),'created_at':time.time(),'notebook':'sessions/'+sid+'/notebook.ipynb'}
    write_json(folder/'meta.json',meta)
    write_json(folder/'notebook.ipynb',{'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'name':'python3' if language=='python' else 'codex-r','display_name':'Codex Science '+language,'language':language}},'cells':[]})
    SESSIONS[sid]={'meta':meta,'client':client,'manager':km,'folder':folder}
    return meta

def session_execute(session_id,code,timeout=60):
    if not isinstance(code,str) or not code.strip() or len(code.encode())>100000: raise ValueError('Provide 1..100000 bytes of analysis code')
    if type(timeout) is not int or not 1<=timeout<=90: raise ValueError('timeout must be 1..90 seconds; use a background job for longer work')
    s=_session(session_id);client=s['client'];folder=s['folder']
    message_id=client.execute(code,allow_stdin=False,stop_on_error=True)
    deadline=time.monotonic()+timeout;outputs=[];count=None;status='ok';characters=0;truncated=False
    while True:
        remaining=deadline-time.monotonic()
        if remaining<=0:
            stop_process(s['meta'],signal.SIGINT);status='timed_out';break
        try: msg=client.get_iopub_msg(timeout=min(remaining,1))
        except Empty:
            if not alive(s['meta']): status='kernel_died';break
            continue
        if msg.get('parent_header',{}).get('msg_id')!=message_id: continue
        kind=msg['header']['msg_type'];content=msg['content']
        if kind=='status' and content['execution_state']=='idle': break
        if kind=='execute_input': count=content.get('execution_count')
        if kind=='error': status='error'
        out=None
        if kind=='stream': out={'output_type':'stream','name':content['name'],'text':content['text']}
        elif kind in ('execute_result','display_data'):
            out={'output_type':kind,'data':content.get('data',{}),'metadata':content.get('metadata',{})}
            if kind=='execute_result': out['execution_count']=content.get('execution_count')
        elif kind=='error': out={k:content.get(k) for k in ['ename','evalue','traceback']};out['output_type']='error'
        elif kind=='clear_output': outputs=[];characters=0
        if out:
            size=len(json.dumps(out,ensure_ascii=False))
            if characters+size<=200000: outputs.append(out);characters+=size
            else: truncated=True
    cell={'id':uuid.uuid4().hex[:12],'cell_type':'code','execution_count':count,'metadata':{'codex_science':{'status':status,'output_truncated':truncated}},'source':code,'outputs':outputs}
    if truncated: cell['outputs'].append({'output_type':'stream','name':'stderr','text':'[Output exceeded the 200000-character capture limit]\n'})
    notebook=read_json(folder/'notebook.ipynb');notebook['cells'].append(cell);write_json(folder/'notebook.ipynb',notebook)
    # Image payloads remain in the notebook; return small text to the MCP caller.
    summary=[]
    for output in outputs:
        if output['output_type']=='stream': summary.append({'type':'stream','name':output['name'],'text':output['text']})
        elif output['output_type']=='error': summary.append(output)
        else: summary.append({'type':output['output_type'],'text':output['data'].get('text/plain',''),'mime_types':list(output['data'])})
    return {'session_id':session_id,'status':status,'outputs':summary,'output_truncated':truncated,'notebook':s['meta']['notebook'],'cell_count':len(notebook['cells'])}

def session_close(session_id):
    s=_session(session_id)
    try:
        if s['manager']:s['manager'].shutdown_kernel(now=False)
        else:s['client'].shutdown(restart=False)
        end=time.time()+5
        while alive(s['meta']) and time.time()<end: time.sleep(.1)
        if alive(s['meta']): stop_process(s['meta'])
    finally:
        s['client'].stop_channels();s['meta']['status']='closed';write_json(s['folder']/'meta.json',s['meta']);SESSIONS.pop(session_id,None)
    return {'session_id':session_id,'status':'closed','notebook':s['meta']['notebook']}

def job_submit(code,language='python',project='projects/main',name='Analysis',timeout=3600,cpus=2):
    if language not in ('python','r','bash'): raise ValueError('Unsupported job language')
    if not isinstance(code,str) or not code.strip() or len(code.encode())>500000: raise ValueError('Provide up to 500000 bytes of job code')
    if type(timeout) is not int or not 1<=timeout<=604800: raise ValueError('Job timeout must be 1 second to 7 days')
    if type(cpus) is not int or not 1<=cpus<=64: raise ValueError('cpus must be 1..64')
    path=scoped(project,('projects',));path.mkdir(parents=True,exist_ok=True)
    jid=uuid.uuid4().hex;folder=ROOT/'jobs'/jid;folder.mkdir()
    filename='analysis.'+{'python':'py','r':'R','bash':'sh'}[language]
    (folder/filename).write_text(code,encoding='utf-8')
    spec={'id':jid,'name':name,'language':language,'project':project,'timeout':timeout,'cpus':cpus,'filename':filename,'created_at':time.time()}
    write_json(folder/'request.json',spec);write_json(folder/'status.json',{'id':jid,'status':'queued','created_at':spec['created_at']})
    with (folder/'worker.log').open('ab') as log:
        worker=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--root',str(ROOT),'--worker',jid],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
    write_json(folder/'worker.json',{'pid':worker.pid,'start_tick':identity(worker.pid)})
    threading.Thread(target=worker.wait,daemon=True).start()
    return {'id':jid,'status':'queued','project':project}

def job_worker(jid):
    folder=ROOT/'jobs'/ident(jid);spec=read_json(folder/'request.json')
    state={'id':jid,'status':'running','started_at':time.time()}
    env=dict(os.environ);env.update(OMP_NUM_THREADS=str(spec['cpus']),MKL_NUM_THREADS=str(spec['cpus']),OPENBLAS_NUM_THREADS=str(spec['cpus']))
    program={'python':sys.executable,'r':os.environ.get('CODEX_SCIENCE_RSCRIPT',str(Path(sys.prefix)/'bin/Rscript')),'bash':'/bin/bash'}[spec['language']]
    argv=[program]+(['--vanilla'] if spec['language']=='r' else [])+[str(folder/spec['filename'])]
    try:
        if (folder/'cancel.request').exists():
            state.update(status='cancelled',finished_at=time.time());write_json(folder/'status.json',state);return
        with (folder/'stdout.log').open('wb') as out,(folder/'stderr.log').open('wb') as err:
            child=subprocess.Popen(argv,cwd=scoped(spec['project'],('projects',)),stdout=out,stderr=err,stdin=subprocess.DEVNULL,env=env,start_new_session=True)
            state.update(pid=child.pid,start_tick=identity(child.pid));write_json(folder/'status.json',state)
            reason=None
            while child.poll() is None:
                if (folder/'cancel.request').exists(): reason='cancelled'
                elif time.time()-state['started_at']>spec['timeout']: reason='timed_out'
                if reason:
                    stop_process(state)
                    try: child.wait(timeout=5)
                    except subprocess.TimeoutExpired: stop_process(state,signal.SIGKILL);child.wait()
                    break
                time.sleep(.2)
            state.update(status=reason or ('succeeded' if child.returncode==0 else 'failed'),exit_code=child.returncode,finished_at=time.time())
    except Exception as exc: state.update(status='failed',error=str(exc),finished_at=time.time())
    write_json(folder/'status.json',state)

def job_status(job_id):
    folder=ROOT/'jobs'/ident(job_id);state=read_json(folder/'status.json')
    if state['status'] in ('queued','running'):
        worker=read_json(folder/'worker.json')
        if not alive(worker): state['status']='interrupted';state['detail']='Worker ended without a final status; inspect logs and output files'
    return state

def job_cancel(job_id):
    state=job_status(job_id)
    if state['status'] in ('queued','running','interrupted'):
        (ROOT/'jobs'/ident(job_id)/'cancel.request').touch()
        if state['status']=='interrupted' and alive(state): stop_process(state)
        return {'id':job_id,'status':'cancellation_requested'}
    return state

def job_logs(job_id,stream='stdout',offset=0,limit=32000):
    if stream not in ('stdout','stderr','worker'): raise ValueError('Unknown log stream')
    if type(offset) is not int or offset<0 or type(limit) is not int or not 1<=limit<=100000: raise ValueError('Invalid log offset/limit')
    p=ROOT/'jobs'/ident(job_id)/(stream+'.log')
    if not p.exists(): return {'text':'','next_offset':offset,'bytes':0}
    with p.open('rb') as f: f.seek(offset);data=f.read(limit)
    return {'text':data.decode('utf-8',errors='replace'),'next_offset':offset+len(data),'bytes':p.stat().st_size}

def artifact_info(path):
    p=scoped(path)
    if not p.is_file(): raise ValueError('Expected an existing artifact file')
    before=p.stat();h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    after=p.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns): raise RuntimeError('Artifact changed while hashing')
    return {'path':p.relative_to(ROOT).as_posix(),'absolute_path':str(p),'bytes':after.st_size,'sha256':h.hexdigest()}

def file_write(path,text,overwrite=False):
    if type(overwrite) is not bool:raise ValueError('overwrite must be a JSON boolean')
    p=scoped(path,('projects',))
    if not isinstance(text,str) or len(text.encode())>500000: raise ValueError('Text upload limit is 500000 bytes')
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w' if overwrite else 'x',encoding='utf-8') as f:f.write(text)
    return artifact_info(path)

def dispatch(action,params):
    if action=='health':
        from jupyter_client.kernelspec import KernelSpecManager
        return {'root':str(ROOT),'pid':os.getpid(),'python':sys.version.split()[0],'environment':sys.prefix,'kernels':list(KernelSpecManager().find_kernel_specs()),'transport':'owner-only Unix socket over SSH','deep_learning_models':'not_installed_by_this_runtime'}
    if action=='sessions':
        return [{**read_json(p),'alive':alive(read_json(p))} for p in sorted((ROOT/'sessions').glob('*/meta.json'))]
    if action=='jobs': return [job_status(p.parent.name) for p in sorted((ROOT/'jobs').glob('*/status.json'))][-100:]
    if action=='artifacts':
        p=scoped(params.get('path','projects/main'))
        return [{'path':x.relative_to(ROOT).as_posix(),'directory':x.is_dir(),'bytes':x.stat().st_size if x.is_file() else None} for x in sorted(p.iterdir())[:200] if x.resolve().is_relative_to(ROOT)]
    functions={'session_start':session_start,'session_execute':session_execute,'session_close':session_close,'job_submit':job_submit,'job_status':job_status,'job_cancel':job_cancel,'job_logs':job_logs,'artifact_info':artifact_info,'file_write':file_write}
    if action not in functions: raise ValueError('Unknown remote operation')
    return functions[action](**params)

class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            self.connection.settimeout(120)
            data=self.rfile.readline(MAX_REQUEST+1)
            if len(data)>MAX_REQUEST: raise ValueError('Request exceeds one MiB')
            request=json.loads(data);result={'ok':True,'result':dispatch(request['action'],request.get('params',{}))}
        except Exception as exc: result={'ok':False,'error':type(exc).__name__+': '+str(exc)}
        try:self.wfile.write((json.dumps(result,ensure_ascii=False)+'\n').encode())
        except (BrokenPipeError,ConnectionResetError): pass

def serve():
    os.umask(0o077)
    for area in ('runtime','sessions','jobs','projects','reports','logs'):(ROOT/area).mkdir(exist_ok=True)
    # Select only this environment's kernels and R user library.
    os.environ['JUPYTER_PATH']=str(Path(sys.prefix)/'share/jupyter')
    os.environ['PATH']=str(Path(sys.prefix)/'bin')+os.pathsep+os.environ.get('PATH','')
    os.environ['CONDA_PREFIX']=sys.prefix
    os.environ['TMPDIR']=str(ROOT/'runtime/tmp')
    (ROOT/'runtime/tmp').mkdir(exist_ok=True)
    os.environ['PYTHONNOUSERSITE']='1'
    os.environ['R_ENVIRON_USER']=os.devnull
    os.environ['R_PROFILE_USER']=os.devnull
    os.environ['R_LIBS_USER']=str(ROOT/'runtime/R-library')
    (ROOT/'runtime/R-library').mkdir(exist_ok=True)
    folder=ROOT/'runtime'
    lock=(folder/'daemon.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    sock=folder/'science.sock'
    if sock.exists():sock.unlink()
    server=socketserver.UnixStreamServer(str(sock),Handler)
    os.chmod(sock,0o600)
    write_json(folder/'daemon.json',{'pid':os.getpid(),'start_tick':identity(os.getpid()),'started_at':time.time()})
    try:server.serve_forever()
    finally:server.server_close();sock.unlink(missing_ok=True)

def request_cli():
    data=sys.stdin.buffer.readline(MAX_REQUEST+1)
    if len(data)>MAX_REQUEST:raise ValueError('Request too large')
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
        client.settimeout(115);client.connect(str(ROOT/'runtime/science.sock'));client.sendall(data.rstrip(b'\n')+b'\n')
        chunks=[]
        while True:
            chunk=client.recv(65536)
            if not chunk:break
            chunks.append(chunk)
        sys.stdout.buffer.write(b''.join(chunks))

def main():
    global ROOT
    p=argparse.ArgumentParser();p.add_argument('--root');p.add_argument('--serve',action='store_true');p.add_argument('--request',action='store_true');p.add_argument('--worker');args=p.parse_args()
    if args.root:ROOT=Path(args.root).resolve(strict=True)
    if args.serve:serve()
    elif args.worker:job_worker(args.worker)
    elif args.request:request_cli()
    else:p.error('Choose --serve, --request or --worker')
if __name__=='__main__':main()
