@echo off
setlocal

echo Sending test assistant runtime events to PC Assistant Sidecar...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$items = @(@{type='assistant_transcript'; source='test_assistant_runtime_event'; text='帮我记录一条测试便签'; message='识别文本：帮我记录一条测试便签'}, @{type='assistant_reply'; source='test_assistant_runtime_event'; text='好的，已帮你记录。'; message='助手回复：好的，已帮你记录。'}, @{type='assistant_state'; source='test_assistant_runtime_event'; state='speaking'; message='语音助手正在播报'}); foreach ($item in $items) { $body = $item | ConvertTo-Json -Compress; Invoke-WebRequest -UseBasicParsing -Method POST -Uri http://127.0.0.1:17891/api/events -Body $body -ContentType 'application/json; charset=utf-8' | Out-Null }; Write-Host 'OK: test assistant runtime events sent.'"

exit /b %ERRORLEVEL%
