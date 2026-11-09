@echo off
REM TCSA3000 - ordenes de consola (portatil). El menu es TCSA3000.exe; sin argumentos este archivo lo abre.
setlocal
set "TCSA3000_HOME=%~dp0"
if "%TCSA3000_HOME:~-1%"=="\" set "TCSA3000_HOME=%TCSA3000_HOME:~0,-1%"
set "PY=%TCSA3000_HOME%\runtime\python.exe"
if not exist "%PY%" set "PY=python"
set PYTHONDONTWRITEBYTECODE=1
if "%~1"=="" (
  start "" "%TCSA3000_HOME%\TCSA3000.exe"
  exit /b 0
)
"%PY%" -B "%TCSA3000_HOME%\tcsa3000\cli.py" %*
endlocal
