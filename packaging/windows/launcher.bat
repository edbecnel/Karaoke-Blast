@echo off
setlocal
set "APP_DIR=%~dp0"
set "PATH=%APP_DIR%ffmpeg;%PATH%"
start "" "%APP_DIR%venv\Scripts\pythonw.exe" -m karaoke_blast %*
