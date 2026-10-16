@echo off
rem Starts MWB (mwb\app.py) with no console window. It lives in the tray; a second start does nothing.
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" -m mwb
) else (
  echo MWB's environment is missing: see README.md, "Setup".
  pause
)
