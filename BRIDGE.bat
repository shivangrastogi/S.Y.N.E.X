@echo off
REM -- AERIS Phone Bridge (standalone) ---------------------------------
REM Runs ONLY the phone<->laptop bridge - no torch, no brain, no GUI.
REM Lets you pair + control the laptop from the mobile app WHILE the
REM intent model is still training in another window.
REM
REM Interpreter comes from _python.bat (override: set AERIS_PYTHON=<path>).
set KMP_DUPLICATE_LIB_OK=TRUE
cd /d "%~dp0"
call "%~dp0_python.bat"
"%AERIS_PY%" run_bridge.py
pause
