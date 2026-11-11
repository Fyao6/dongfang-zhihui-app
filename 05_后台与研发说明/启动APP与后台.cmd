@echo off
chcp 65001 >nul
setlocal
set "taskPython=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%taskPython%" (
  "%taskPython%" -B "%~dp0启动本地计时后台.py" %*
) else (
  py -3 -B "%~dp0启动本地计时后台.py" %*
)
