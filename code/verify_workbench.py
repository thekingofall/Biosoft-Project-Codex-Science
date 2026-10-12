"""Exercise new research tools through the real MCP stdio transport."""
import argparse,asyncio,json,os,sys,tempfile
from datetime import datetime,timezone
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
ROOT=Path(__file__).resolve().parents[1]
async def main(online=False):
 report={'timestamp':datetime.now(timezone.utc).isoformat(),'calls':[]}
 params=StdioServerParameters(command=sys.executable,args=['-X','utf8',str(ROOT/'code/science_workbench.py')],env=dict(os.environ))
 parent=os.environ.get('CODEX_SCIENCE_TEST_TMP')
 if parent: Path(parent).mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(dir=parent) as workspace:
  async with asyncio.timeout(180):
   async with stdio_client(params) as (reader,writer):
    async with ClientSession(reader,writer) as client:
     await client.initialize(); listing=await client.list_tools()
     report['tool_count']=len(listing.tools)
     report['tools']=[t.name for t in listing.tools]
     async def call(name,args):
      result=await client.call_tool(name,args)
      if result.isError: raise AssertionError((name,str(result.content)))
      structured=result.structuredContent
      if structured is None:
       structured=json.loads(next(x.text for x in result.content if x.type=='text'))
      report['calls'].append({'tool':name,'passed':True})
      return structured
     catalog=await call('science_list_capabilities',{})
     assert catalog['total']==29
     result=await call('science_run_helper',{'skill':'paper-narrative','function':'paper_brief_schema'})
     assert result['executed'] is True
     await call('science_create_manuscript',{'workspace':workspace,'title':'Research example','output':'draft.md'})
     await call('science_export_manuscript',{'workspace':workspace,'source':'draft.md','output':'draft.docx'})
     assert (Path(workspace)/'draft.docx').read_bytes().startswith(b'PK')
     await call('science_compute_environment',{})
     if online:
      result=await call('science_doi_lookup',{'doi':'10.1038/nature12373'})
      assert result['doi']=='10.1038/nature12373'
 report['passed']=True
 (ROOT/'reports').mkdir(exist_ok=True)
 (ROOT/'reports/workbench-acceptance.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--online',action='store_true');args=p.parse_args();asyncio.run(main(args.online))
