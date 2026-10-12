$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$python = Join-Path $project '.venv\Scripts\python.exe'
$entry = Join-Path $project 'code\science_mcp.py'
if (!(Test-Path -LiteralPath $python)) { throw 'Python environment missing. Install requirements.txt first.' }
& $python -X utf8 $entry --check
if ($LASTEXITCODE -ne 0) { throw 'Asset verification failed.' }
$existingRaw = & codex mcp get science-bio --json 2>$null
if ($LASTEXITCODE -eq 0) {
    $existing = ($existingRaw -join "`n") | ConvertFrom-Json
    if ($existing.transport.command -ne $python -or $existing.transport.args -notcontains $entry) {
        throw 'An existing science-bio registration points elsewhere. Review that configuration before installing.'
    }
    Write-Output 'Matching science-bio registration already exists.'
} else {
    $sourceArgs=@()
    if ($env:CODEX_SCIENCE_RELEASE) {
        $release=(Resolve-Path -LiteralPath $env:CODEX_SCIENCE_RELEASE).Path
        $sourceArgs=@('--env', "CODEX_SCIENCE_RELEASE=$release")
    }
    & codex mcp add science-bio --env PYTHONUTF8=1 @sourceArgs -- $python -X utf8 $entry
    if ($LASTEXITCODE -ne 0) { throw 'Codex MCP registration failed.' }
}
& $python -X utf8 (Join-Path $project 'code\configure_codex.py')
if ($LASTEXITCODE -ne 0) { throw 'Codex timeout configuration failed.' }
$skillSource=Join-Path $project 'skill'
$skillPath=Join-Path $env:USERPROFILE '.agents\skills\codex-science'
if (Test-Path -LiteralPath $skillPath) {
    $link=Get-Item -LiteralPath $skillPath
    if ($link.LinkType -ne 'Junction' -or $link.Target -notcontains $skillSource) { throw 'Existing skill has another source.' }
} else {
    New-Item -ItemType Junction -Path $skillPath -Target $skillSource | Out-Null
}
Write-Output 'Codex Science is installed ($codex-science + science-bio).'

$legacyPath=Join-Path $env:USERPROFILE '.agents\skills\claude-science-codex'
if (Test-Path -LiteralPath $legacyPath) {
    $legacy=Get-Item -LiteralPath $legacyPath
    if ($legacy.LinkType -eq 'Junction' -and $legacy.Target -contains $skillSource) {
        Remove-Item -LiteralPath $legacyPath -Force
        Write-Output 'Updated the skill entry from claude-science-codex to codex-science.'
    }
}

& (Join-Path $PSScriptRoot "install-workbench.ps1")
