$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "==> Gate 6.2 cumulative automated/Fake acceptance"
python tools/verify_gate6_2_cumulative.py
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "Gate 6.2 cumulative automated/Fake acceptance passed."
exit 0
