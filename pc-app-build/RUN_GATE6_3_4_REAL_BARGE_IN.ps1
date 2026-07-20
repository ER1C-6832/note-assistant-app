$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "==> Gate 6.3+6.4 real Windows acoustic barge-in acceptance"
Write-Host "Use speakers, not headphones. The runner asks for one long reply and one interruption."
python tools/verify_gate6_3_4_real_barge_in.py
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "Gate 6.3+6.4 real acoustic barge-in acceptance passed."
exit 0
