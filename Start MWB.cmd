@echo off
rem Starts MWB with no console window, through its watchdog (mwb\watchdog.py), which starts it again if it crashes.
rem It lives in the tray; a second start does nothing.
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" -m mwb.watchdog
) else (
  echo MWB's environment is missing: see README.md, "Setup".
  pause
)
