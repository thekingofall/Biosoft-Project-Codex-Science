"""Reproducible R figures from CSV tables, with project-scoped outputs."""
from __future__ import annotations
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

CODE = Path(__file__).resolve().parent
PALETTE = ['#355C7D', '#52796F', '#B56B45', '#806A87', '#BA994F', '#6B8793']

def scoped(workspace: str, path: str, must_exist: bool = False) -> Path:
    root=Path(workspace).expanduser().resolve(strict=True)
    if not root.is_dir(): raise ValueError('workspace must be a directory')
    target=(root/path).resolve()
    if target == root or not target.is_relative_to(root): raise ValueError('Path must stay within workspace')
    if must_exist and not target.is_file(): raise FileNotFoundError(str(target))
    return target

def rscript() -> str:
    candidate=os.environ.get('CODEX_SCIENCE_RSCRIPT') or shutil.which('Rscript')
    if not candidate and os.name=='nt':
        found=sorted(Path('C:/Program Files/R').glob('R-*/bin/Rscript.exe'))
        if found: candidate=str(found[-1])
    if not candidate: raise RuntimeError('Install R with jsonlite, or set CODEX_SCIENCE_RSCRIPT')
    return candidate

def plot_table(workspace: str, csv_path: str, output_prefix: str, kind: str,
               x: str, y: str, group: str = '', width_mm: float = 100,
               height_mm: float = 80, x_label: str = '', y_label: str = '') -> dict:
    """Plot measured CSV values with R; save PNG, PDF and reproducible parameters.

    kind: scatter, line, box or bar. Bar requires unique x values per group.
    No hypothesis tests or aggregation are added. Labels must be English.
    """
    if kind not in {'scatter','line','box','bar'}: raise ValueError('Unknown plot kind')
    if not 40<=width_mm<=300 or not 40<=height_mm<=300: raise ValueError('Figure dimensions must be 40..300 mm')
    if not output_prefix.strip(): raise ValueError('Provide an output prefix')
    for label in (x_label or x, y_label or y, group):
        if any('\u4e00'<=c<='\u9fff' for c in label): raise ValueError('Use English axis and group labels')
    source=scoped(workspace,csv_path,True)
    if source.stat().st_size>25_000_000: raise ValueError('Provide plot-ready CSV smaller than 25 MB')
    with source.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f); columns=reader.fieldnames or []; rows=list(reader)
    if not rows: raise ValueError('CSV has no data rows')
    if any(k not in columns for k in [x,y]+([group] if group else [])): raise ValueError('Requested column is absent')
    if len(rows)>100000: raise ValueError('Provide at most 100000 plot-ready rows')
    if any(not str(r[x] or '').strip() or (group and not str(r[group] or '').strip()) for r in rows):
        raise ValueError('X and group values must be present')
    if kind=='bar':
        keys=[(r[x],r[group] if group else '') for r in rows]
        if len(keys)!=len(set(keys)): raise ValueError('Bar input needs one value per x/group; aggregate explicitly first')
    prefix=scoped(workspace,output_prefix)
    outputs={k:scoped(workspace,str(prefix)+'.'+k) for k in ['png','pdf','json']}
    if any(p.exists() for p in outputs.values()): raise FileExistsError('Choose a new output prefix; existing files are preserved')
    prefix.parent.mkdir(parents=True,exist_ok=True)
    params=dict(csv=str(source),output=str(prefix),kind=kind,x=x,y=y,group=group,
                width_mm=width_mm,height_mm=height_mm,x_label=x_label or x,y_label=y_label or y,
                palette=PALETTE,font='Arial',input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                script=str(CODE/'plot_table.R'),script_sha256=hashlib.sha256((CODE/'plot_table.R').read_bytes()).hexdigest())
    with outputs['json'].open('x',encoding='utf-8') as f: json.dump(params,f,ensure_ascii=False,indent=2)
    env=dict(os.environ)
    if os.name=='nt': env.update(LC_ALL='C',LANG='C')
    result=subprocess.run([rscript(),'--vanilla',str(CODE/'plot_table.R'),str(outputs['json'])],
                          capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120,env=env)
    if result.returncode: raise RuntimeError('R plotting failed: '+result.stderr[-3500:])
    for key in ['png','pdf']:
        if not outputs[key].is_file() or outputs[key].stat().st_size<100: raise RuntimeError('R did not produce '+key)
    return {'files':{k:str(p) for k,p in outputs.items()},'rows':len(rows),'engine':'R',
            'input_sha256':params['input_sha256'],'warnings':result.stderr[-2000:]}

def register_tools(mcp):
    mcp.tool(name='science_plot_table')(plot_table)
