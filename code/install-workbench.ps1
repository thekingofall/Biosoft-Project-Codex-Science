$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$python = Join-Path $project '.venv\Scripts\python.exe'
$entry = Join-Path $project 'code\science_workbench.py'
if (!(Test-Path -LiteralPath $python)) { throw 'Install the Python environment and requirements first.' }
& $python -X utf8 $entry --check
if ($LASTEXITCODE -ne 0) { throw 'Workbench import check failed.' }
$existingRaw = & codex mcp get science-workbench --json 2>$null
if ($LASTEXITCODE -eq 0) {
    $existing = ($existingRaw -join "`n") | ConvertFrom-Json
    if ($existing.transport.command -ne $python -or $existing.transport.args -notcontains $entry) {
        throw 'An existing science-workbench entry points elsewhere. Review that entry first.'
    }
} else {
    $sourceArgs=@()
    if ($env:CODEX_SCIENCE_RELEASE) {
        $release=(Resolve-Path -LiteralPath $env:CODEX_SCIENCE_RELEASE).Path
        $sourceArgs=@('--env', "CODEX_SCIENCE_RELEASE=$release")
    }
    & codex mcp add science-workbench --env PYTHONUTF8=1 @sourceArgs -- $python -X utf8 $entry
    if ($LASTEXITCODE -ne 0) { throw 'Workbench registration failed.' }
}
& $python -X utf8 (Join-Path $project 'code\configure_codex.py') science-workbench
if ($LASTEXITCODE -ne 0) { throw 'Workbench timeout configuration failed.' }
$skillSource=Join-Path $project 'skill'
$skillPath=Join-Path $env:USERPROFILE '.agents\skills\codex-science'
if (Test-Path -LiteralPath $skillPath) {
    $link=Get-Item -LiteralPath $skillPath
    if ($link.LinkType -ne 'Junction' -or $link.Target -notcontains $skillSource) { throw 'Existing skill has another source.' }
} else {
    New-Item -ItemType Junction -Path $skillPath -Target $skillSource | Out-Null
}
Write-Output 'Codex Science workbench registered. Reload MCP connections to use it.'
