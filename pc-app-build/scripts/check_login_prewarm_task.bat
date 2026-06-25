@echo off
setlocal

set TASK_NAME=NoteAssistantVoicePrewarm

echo === Scheduled task ===
schtasks /Query /TN "%TASK_NAME%" /V /FO LIST

echo.
echo === Sidecar health ===
powershell -NoProfile -Command "try { Invoke-RestMethod 'http://127.0.0.1:17891/api/health' | ConvertTo-Json -Depth 6 } catch { Write-Host $_.Exception.Message; exit 1 }"

echo.
echo === Recent voice bridge events ===
powershell -NoProfile -Command "try { (Invoke-RestMethod 'http://127.0.0.1:17891/api/events?limit=30').items | Where-Object { $_.type -in @('runtime_stage','assistant_bridge_heartbeat','startup_trace') } | Select-Object -Last 10 | ConvertTo-Json -Depth 6 } catch { Write-Host $_.Exception.Message }"
