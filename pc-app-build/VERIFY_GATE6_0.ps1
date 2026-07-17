$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Invoke-GateCheck {
    param([string]$Name, [string[]]$Arguments)
    Write-Host "[Gate 6.0] $Name"
    & python @Arguments
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

Invoke-GateCheck "compileall" @("-m", "compileall", "-q", "apps", "tools", "tests")
Invoke-GateCheck "black" @("-m", "black", "--check", "apps", "tools", "tests")
Invoke-GateCheck "ruff" @("-m", "ruff", "check", "apps", "tools", "tests")
Invoke-GateCheck "pytest" @("-m", "pytest", "-W", "error", "tests", "-q")
Invoke-GateCheck "qml-smoke" @("tools/verify_gate2_6_ui_smoke.py")
Invoke-GateCheck "gate5-cumulative" @("tools/verify_gate5_4_cumulative.py")
Invoke-GateCheck "gate6.0-fake" @("tools/verify_gate6_0_fake_probe.py")

Write-Host "Gate 6.0 automated/Fake verification complete. Real probes remain explicit."
exit 0
