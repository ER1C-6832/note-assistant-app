param(
    [switch]$MicrophoneTest,
    [double]$Duration = 1.0
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Arguments = @("tools/verify_gate6_1_real_route.py")
if ($MicrophoneTest) {
    $Arguments += "--microphone-test"
    $Arguments += "--duration"
    $Arguments += "$Duration"
}

Write-Host "==> Gate 6.1 real Windows route acceptance"
python @Arguments
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "Gate 6.1 real Windows route acceptance passed."
exit 0
