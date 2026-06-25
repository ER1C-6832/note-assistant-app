@echo off
setlocal

REM Set PC_APP_STOP_PY_XIAOZHI_ON_EXIT=0 in pc-app-build\.env.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$envPath = Join-Path (Resolve-Path '%~dp0..') '.env';" ^
  "$key = 'PC_APP_STOP_PY_XIAOZHI_ON_EXIT';" ^
  "$value = '0';" ^
  "$lines = @();" ^
  "if (Test-Path $envPath) { $lines = Get-Content $envPath -Encoding UTF8 }" ^
  "$found = $false;" ^
  "$out = foreach ($line in $lines) { if ($line -match ('^\s*' + [regex]::Escape($key) + '\s*=')) { $found = $true; $key + '=' + $value } else { $line } };" ^
  "if (-not $found) { $out += $key + '=' + $value }" ^
  "$out | Set-Content $envPath -Encoding UTF8"

echo Updated .env: PC_APP_STOP_PY_XIAOZHI_ON_EXIT=0
