@echo off
setlocal

echo Sending test event to PC Assistant Sidecar...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$body = @{type='tool_result'; source='test_sidecar_event'; tool_name='notes.test'; status='success'; success=$true; message='这是一条 Phase 5.2 Sidecar 事件测试'; note_changed=$false} | ConvertTo-Json -Compress; Invoke-WebRequest -UseBasicParsing -Method POST -Uri http://127.0.0.1:17891/api/events -Body $body -ContentType 'application/json; charset=utf-8' | Select-Object -ExpandProperty Content"

exit /b %ERRORLEVEL%
