"""Read Codex's MCP discovery through its app-server protocol; no model turn."""
import asyncio,json,os,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SERVER=sys.argv[1] if len(sys.argv)>1 else 'science-bio'
if SERVER not in {'science-bio','science-workbench'}: raise ValueError('Choose science-bio or science-workbench')
def codex_binary():
 explicit=os.environ.get('CODEX_BIN') or shutil.which('codex.exe')
 if explicit and Path(explicit).is_file():return Path(explicit)
 shim=shutil.which('codex.cmd')
 if shim:
  candidate=Path(shim).parent/'node_modules/@openai/codex/node_modules/@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/bin/codex.exe'
  if candidate.is_file():return candidate
 raise RuntimeError('Set CODEX_BIN to the native Codex executable for this optional host check.')

async def main():
 (ROOT/'reports').mkdir(exist_ok=True)
 log=(ROOT/'reports/codex-host.stderr.log').open('wb')
 process=await asyncio.create_subprocess_exec(str(codex_binary()),'app-server','--stdio',stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=log,limit=4*1024*1024)
 async def request(i,method,params):
  process.stdin.write((json.dumps({'id':i,'method':method,'params':params})+'\n').encode());await process.stdin.drain()
  async with asyncio.timeout(110):
   while line:=await process.stdout.readline():
    msg=json.loads(line)
    if msg.get('id')==i:
     if 'error' in msg:raise RuntimeError(msg['error'])
     return msg['result']
   raise RuntimeError('Codex app-server closed')
 try:
  await request(1,'initialize',{'clientInfo':{'name':'science_mcp_acceptance','version':'0.1.0'},'capabilities':{'experimentalApi':True}})
  process.stdin.write(b'{"method":"initialized","params":{}}\n');await process.stdin.drain()
  result=await request(2,'mcpServerStatus/list',{'serverName':SERVER,'detail':'toolsAndAuthOnly'})
  (ROOT/('reports/codex-host-discovery.json' if SERVER=='science-bio' else 'reports/workbench-host-discovery.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps({'status':'Codex discovery response saved','keys':list(result),'data_summary':[{k:(len(v) if isinstance(v,(dict,list)) else v) for k,v in x.items()} for x in result.get('data',[])]},ensure_ascii=False))
 finally:
  process.stdin.close()
  try:await asyncio.wait_for(process.wait(),10)
  except asyncio.TimeoutError:process.terminate();await process.wait()
  log.close()
asyncio.run(main())
