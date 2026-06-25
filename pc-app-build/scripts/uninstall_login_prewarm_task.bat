@echo off
setlocal

set TASK_NAME=NoteAssistantVoicePrewarm

echo Removing scheduled task: %TASK_NAME%
schtasks /Delete /TN "%TASK_NAME%" /F
