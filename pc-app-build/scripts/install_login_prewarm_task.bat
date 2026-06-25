@echo off
setlocal

set TASK_NAME=NoteAssistantVoicePrewarm
set VBS=%~dp0start_voice_prewarm_hidden.vbs

echo Installing scheduled task: %TASK_NAME%
schtasks /Create /TN "%TASK_NAME%" /SC ONLOGON /TR "wscript.exe \"%VBS%\"" /RL LIMITED /F

echo.
echo Installed. It will prewarm Sidecar + py-xiaozhi after Windows login.
echo To start it now:
echo   schtasks /Run /TN "%TASK_NAME%"
