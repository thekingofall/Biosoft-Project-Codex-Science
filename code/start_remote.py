"""Start the project runtime from its own Mamba environment on Linux."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
import remote_runtime as runtime


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",required=True)
    args=parser.parse_args()
    root=Path(args.root).resolve();env=Path(sys.prefix).resolve()
    if not env.is_relative_to(root/"envs") or not (env/"bin/R").is_file():
        raise RuntimeError("Run with the Python interpreter from this project's envs/runtime Mamba environment")
    os.umask(0o077);root.mkdir(parents=True,exist_ok=True)
    for folder in ("code","runtime","sessions","jobs","projects/main","reports","logs"):(root/folder).mkdir(parents=True,exist_ok=True)
    metadata=root/"runtime/daemon.json"
    if metadata.exists() and runtime.alive(runtime.read_json(metadata)):
        print("Runtime already running; use science_remote health to check it.")
        return
    kernels=env/"share/jupyter/kernels/codex-r";kernels.mkdir(parents=True,exist_ok=True)
    runtime.write_json(kernels/"kernel.json",{"argv":[str(env/"bin/R"),"--vanilla","--slave","-e","IRkernel::main()","--args","{connection_file}"],"display_name":"Codex Science R","language":"R"})
    subprocess.run([sys.executable,"-m","ipykernel","install","--prefix",str(env),"--name","python3"],check=True)
    with (root/"logs/runtime.log").open("ab") as log:
        process=subprocess.Popen([sys.executable,str(Path(__file__).with_name("remote_runtime.py")),"--root",str(root),"--serve"],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env={**os.environ,"PYTHONNOUSERSITE":"1"})
    time.sleep(2)
    if process.poll() is not None:raise RuntimeError("Runtime exited; inspect logs/runtime.log")
    print(json.dumps({"root":str(root),"pid":process.pid,"environment":str(env)}))

if __name__=="__main__":main()
