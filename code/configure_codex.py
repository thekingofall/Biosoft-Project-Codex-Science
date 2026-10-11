"""Set startup budgets for the matching, registered local science-bio entry."""
from pathlib import Path
from datetime import datetime,timezone
import os,tomllib
ROOT=Path(__file__).resolve().parents[1]
config_dir=Path(os.environ.get('CODEX_HOME') or str(Path.home()/'.codex'))
p=config_dir/'config.toml'; text=p.read_text(encoding='utf-8'); before=tomllib.loads(text)
server=before['mcp_servers']['science-bio']
assert Path(server['command']).resolve()==(ROOT/'.venv/Scripts/python.exe').resolve()
assert str(ROOT/'code/science_mcp.py') in server['args']
key='[mcp_servers.science-bio]'; assert text.count(key)==1
lines=[]
if 'startup_timeout_sec' not in server: lines.append('startup_timeout_sec = 90')
if 'tool_timeout_sec' not in server: lines.append('tool_timeout_sec = 120')
if lines:
 updated=text.replace(key,key+'\n'+'\n'.join(lines),1); after=tomllib.loads(updated)
 for name,value in before.get('mcp_servers',{}).items():
  if name!='science-bio': assert after['mcp_servers'][name]==value
 backup=ROOT/'.local/backups'
 backup.mkdir(parents=True,exist_ok=True)
 (backup/('config.'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.toml.bak')).write_text(text,encoding='utf-8')
 p.write_text(updated,encoding='utf-8')
print('science-bio timeouts configured; unrelated settings preserved.')
