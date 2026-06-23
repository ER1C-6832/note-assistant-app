@echo off
setlocal

echo Checking PC Assistant Sidecar health...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "try { $r = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:17891/api/health; Write-Host $r.Content } catch { Write-Host $_; exit 1 }"

exit /b %ERRORLEVEL%
