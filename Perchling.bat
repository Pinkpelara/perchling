@echo off
rem Double-click to put Teal on your desktop. "Perchling.bat horns" for Gold, ears for Pink, leaf for Green.
rem Right-click the pet to quit.
set "PET=%~1"
if "%PET%"=="" set "PET=antenna"
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if not exist "%PY%" set "PY=pythonw"
start "" "%PY%" "%~dp0app\perchling.py" --pet %PET%
