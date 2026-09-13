@echo off
rem Double-click to start your adopted pets (or adopt one, the first time).
rem "Perchling.bat horns" starts Gold on its own; antenna = Teal, ears = Pink, leaf = Green.
rem Right-click a pet to quit. For the packaged download, see tools\build_exe.py.
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if not exist "%PY%" set "PY=pythonw"
if "%~1"=="" (
  start "" "%PY%" "%~dp0app\perchling.py"
) else (
  start "" "%PY%" "%~dp0app\perchling.py" --pet %~1
)
