@echo off
rem Opens MWB's API key window (mwb\ui\api_key.py). From Phase 1 the tray menu opens the same window.
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" -m mwb.ui.api_key
) else (
  start "" pyw -3.14 -m mwb.ui.api_key
)
