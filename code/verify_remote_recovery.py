"""Opt-in Linux acceptance: restart this idle project runtime and verify recovery."""
import argparse,json,os,signal,socket,subprocess,sys,time
from pathlib import Path
import nbformat
import remote_runtime as runtime


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',required=True);args=parser.parse_args()
    root=Path(args.root).resolve();runtime.ROOT=root;checks=[];sessions=[]
    def rpc(action,**params):
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
            sock.settimeout(100);sock.connect(str(root/'runtime/science.sock'))
            sock.sendall((json.dumps({'action':action,'params':params})+'\n').encode())
            with sock.makefile('rb') as stream:response=json.loads(stream.readline())
        if not response['ok']:raise RuntimeError(response['error'])
        return response['result']
    def restart():
        meta=runtime.read_json(root/'runtime/daemon.json')
        if runtime.alive(meta):os.kill(meta['pid'],signal.SIGTERM)
        for _ in range(50):
            if not runtime.alive(meta):break
            time.sleep(.1)
        if runtime.alive(meta):raise RuntimeError('Runtime did not stop')
        subprocess.run([sys.executable,str(Path(__file__).with_name('start_remote.py')),'--root',str(root)],check=True)
    if any(item['alive'] for item in rpc('sessions')):raise RuntimeError('Close existing interactive sessions before this restart check')
    if any(item['status'] in ('queued','running') for item in rpc('jobs')):raise RuntimeError('Wait for existing jobs before this restart check')
    restart()
    try:
        for language,code in [('python','recovery_value = 42'),('r','recovery_value <- 42')]:
            session=rpc('session_start',language=language,project='projects/recovery-check',name='Recovery '+language)
            sessions.append(session)
            assert rpc('session_execute',session_id=session['id'],code=code)['status']=='ok'
        job=rpc('job_submit',project='projects/recovery-check',code="import time; from pathlib import Path; time.sleep(8); Path('recovered.txt').write_text('42')")
        restart();time.sleep(2)
        for session in sessions:
            result=rpc('session_execute',session_id=session['id'],code='print(recovery_value)')
            assert result['status']=='ok' and '42' in json.dumps(result['outputs'])
            nbformat.validate(nbformat.read(root/session['notebook'],as_version=4))
            checks.append(session['language']+' state recovered and notebook valid')
        result=rpc('session_execute',session_id=sessions[0]['id'],code="import sys, os, tempfile; assert os.environ['CONDA_PREFIX'] == sys.prefix; assert tempfile.gettempdir().startswith(os.environ['CONDA_PREFIX'].split('/envs/')[0]); print(sys.prefix)")
        assert result['status']=='ok';checks.append('Conda prefix and project temporary directory')
        result=rpc('session_execute',session_id=sessions[1]['id'],code="stopifnot(all(startsWith(.libPaths(), dirname(dirname(Sys.getenv('CONDA_PREFIX')))))); library(ggplot2); cat(as.character(packageVersion('ggplot2')))")
        assert result['status']=='ok';checks.append('R libraries confined to project environment')
        for _ in range(100):
            state=rpc('job_status',job_id=job['id'])
            if state['status'] not in ('running','queued'):break
            time.sleep(.2)
        assert state['status']=='succeeded' and (root/'projects/recovery-check/recovered.txt').read_text()=='42'
        checks.append('Detached job survived runtime restart')
    finally:
        for session in sessions:rpc('session_close',session_id=session['id'])
    report={'passed':True,'checks':checks,'health':rpc('health')}
    runtime.write_json(root/'reports/recovery-acceptance.json',report)
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
