$ErrorActionPreference='Stop'
$python=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$entry=Join-Path $PSScriptRoot 'code\codex_science.py'
& $python -X utf8 $entry @args
exit $LASTEXITCODE
