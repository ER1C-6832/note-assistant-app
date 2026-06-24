@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
call integrations\py-xiaozhi\scripts\install_headless_runtime_patch.bat
exit /b %ERRORLEVEL%
