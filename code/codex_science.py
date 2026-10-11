"""Inspect Codex Science configuration and its saved scientific tool catalog."""
import argparse
import json
import os
from pathlib import Path
import tomllib
from science_mcp import PROJECT, BIO, prepare


def main():
    parser=argparse.ArgumentParser(prog='codex-science',description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    commands.add_parser('status',help='Check local assets, registration and prior validation.')
    tools=commands.add_parser('tools',help='Search the saved tool catalog; no network request.')
    tools.add_argument('--query',default='')
    tools.add_argument('--domain',default=None)
    tools.add_argument('--limit',type=int,default=20)
    args=parser.parse_args()
    if args.command=='status':
        source=prepare()
        cfg=Path(os.environ.get('CODEX_HOME') or str(Path.home()/'.codex'))/'config.toml'
        config=tomllib.loads(cfg.read_text(encoding='utf-8')) if cfg.exists() else {}
        registration=config.get('mcp_servers',{}).get('science-bio',{})
        expected=PROJECT/'code/science_mcp.py'
        correct=any(Path(a).resolve()==expected.resolve() for a in registration.get('args',[]) if a.endswith('science_mcp.py'))
        if correct:
            correct=Path(registration.get('command','')).resolve()==(PROJECT/'.venv/Scripts/python.exe').resolve()
        previous_path=PROJECT/'reports/live-tests.json'
        previous=json.loads(previous_path.read_text(encoding='utf-8')) if previous_path.exists() else {}
        result={'product':'Codex Science','version':'0.1.0','skill':'$codex-science',
          'mcp_server':'science-bio','registered_to_this_project':correct,
          'enabled':registration.get('enabled',True) if registration else False,
          'tools':source['tool_count'],'domains':len(source['domains']),
          'verified_source_files':source['verified_files'],
          'credentials_configured':source['credentials_configured'],
          'last_online_test_at':previous.get('timestamp'),
          'last_online_test_passed':previous.get('passed'),
          'online_tested_tools':[c['tool'] for c in previous.get('calls', [])],
          'network_checked_now':False}
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return
    if not 1<=args.limit<=224: parser.error('--limit must be between 1 and 224')
    catalog_path=PROJECT/'reports/tool-catalog.json'
    if not catalog_path.is_file():
        parser.error('Run code/verify_mcp.py first to create your local tool catalog.')
    catalog=json.loads(catalog_path.read_text(encoding='utf-8'))
    domains=json.loads((BIO/'lib/mcp_bio/domains.json').read_text(encoding='utf-8'))
    if args.domain is not None and args.domain not in domains:
        parser.error('Unknown domain. Available: '+', '.join(sorted(domains)))
    selected=[t for t in catalog if (args.domain is None or t['name'] in domains[args.domain])
              and args.query.casefold() in (t['name']+' '+t.get('description','')).casefold()]
    print(json.dumps({'total_matches':len(selected),'shown':min(len(selected),args.limit),
          'tools':[{'name':t['name'],'description':t.get('description',''),
                    'input_schema':t['inputSchema']} for t in selected[:args.limit]]},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
