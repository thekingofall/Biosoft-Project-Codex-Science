"""Exercise the same stdio entry point configured for Codex."""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]

async def main():
    (ROOT/'reports').mkdir(exist_ok=True)
    report = {'timestamp': datetime.now(timezone.utc).isoformat(), 'checks': []}
    params = StdioServerParameters(command=sys.executable,
        args=['-X', 'utf8', str(ROOT/'code/science_mcp.py')],
        env={**os.environ, 'PYTHONUTF8': '1'})
    try:
        async with asyncio.timeout(180):
            async with stdio_client(params) as (reader, writer):
                async with ClientSession(reader, writer) as client:
                    result = await client.initialize()
                    report['server'] = result.serverInfo.model_dump()
                    listing = await client.list_tools()
                    catalog = [t.model_dump(mode='json', exclude_none=True) for t in listing.tools]
                    (ROOT/'reports/tool-catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
                    names = {t.name for t in listing.tools}
                    report['tool_count'] = len(names)
                    assert len(names)==224, f'Unexpected tool count: {len(names)}'
                    assert all(t.inputSchema.get('type')=='object' for t in listing.tools)
                    report['checks'].append({'name':'initialize_and_list_tools','passed':True})
                    for name in ['ensembl_lookup','get_uniprot_entries','pubchem_search_compounds','search_articles']:
                        tool=next(t for t in listing.tools if t.name==name)
                        print(name,json.dumps(tool.inputSchema,ensure_ascii=False))
    except Exception as exc:
        report['error']=repr(exc)
        raise
    finally:
        (ROOT/'reports/handshake.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':
    asyncio.run(main())
