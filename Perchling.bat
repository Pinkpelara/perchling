@echo off
rem Double-click to put a Perchling on your desktop. Right-click the pet to quit.
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if not exist "%PY%" set "PY=pythonw"
start "" "%PY%" "%~dp0app\perchling.py" --pet antenna
