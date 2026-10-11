"""Read-only network acceptance tests through the actual stdio MCP transport."""
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from science_mcp import BIO
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT=Path(__file__).resolve().parents[1]
CASES=[
 ('ensembl_lookup', {'query':'BRCA1','species':'homo_sapiens'}, 'ENSG00000012048'),
 ('get_uniprot_entries', {'accessions':['P04637'],'format':'fasta'}, 'P04637'),
 ('pubchem_search_compounds', {'query':'aspirin','max_cids':1,'with_properties':False}, '2244'),
]

async def main():
 (ROOT/'reports').mkdir(exist_ok=True)
 report={'timestamp':datetime.now(timezone.utc).isoformat(),'calls':[]}
 params=StdioServerParameters(command=sys.executable,args=['-X','utf8',str(ROOT/'code/science_mcp.py')],env={**os.environ,'PYTHONUTF8':'1'})
 async with stdio_client(params) as (reader,writer):
  async with ClientSession(reader,writer) as c:
   async with asyncio.timeout(90): await c.initialize()
   listing=await c.list_tools(); names={t.name for t in listing.tools}
   gate=json.loads((BIO/'lib/mcp_bio/deferred.json').read_text(encoding='utf-8'))
   forbidden=set(gate['license_tools']+gate['unavailable_tools']+gate['tools'])
   assert not (forbidden&names); report['exclusions_preserved']=True
   for name,args,expected in CASES:
    try:
     async with asyncio.timeout(75): result=await c.call_tool(name,args)
     payload=result.model_dump(mode='json',exclude_none=True)
     body=json.loads(next(x.text for x in result.content if getattr(x, 'type', None)=='text'))
     if name=='ensembl_lookup': valid=body.get('found') is True and body.get('record',{}).get('id')==expected
     elif name=='get_uniprot_entries': valid=body.get('n_found')==1 and body.get('records',{}).get(expected,'').startswith('>sp|P04637|')
     else: valid=body.get('cids')==[int(expected)]
     passed=not result.isError and valid
     row={'tool':name,'arguments':args,'passed':passed,'expected_marker':expected,'result':payload}
    except Exception as exc: row={'tool':name,'arguments':args,'passed':False,'error':repr(exc)}
    report['calls'].append(row)
    (ROOT/'reports/live-tests.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'tool':name,'passed':row['passed'],'preview':str(row.get('result',row.get('error')))[:950]},ensure_ascii=False),flush=True)
   # Schema enforcement: malformed calls must not be treated as successful queries.
   result=await c.call_tool('ensembl_lookup',{'query':123})
   report['invalid_arguments_rejected']=bool(result.isError)
 report['passed']=all(x['passed'] for x in report['calls']) and report['exclusions_preserved'] and report['invalid_arguments_rejected']
 (ROOT/'reports/live-tests.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print('ALL_PASSED='+str(report['passed']))
 return 0 if report['passed'] else 1

if __name__=='__main__': sys.exit(asyncio.run(main()))
