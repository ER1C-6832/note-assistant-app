$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

Push-Location $PSScriptRoot
try {
    Write-Host "==> Compile check"
    python -m compileall -q apps tools tests
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "==> Black check"
    python -m black --check apps tools tests
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "==> Ruff check"
    python -m ruff check apps tools tests
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "==> Full pytest regression"
    python -m pytest -W error --basetemp .\.gate6_3_4_hotfix_pytest_tmp tests -q
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "==> QML smoke"
    python tools/verify_gate2_6_ui_smoke.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "Gate 6.3/6.4 emergency stability hotfix automated acceptance passed."
}
finally {
    Pop-Location
}
