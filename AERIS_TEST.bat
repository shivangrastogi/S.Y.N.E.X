@echo off
REM -- AERIS testing launcher ------------------------------------------
REM GUI + crash-isolated split-brain (a native brain crash can't kill the
REM app) + a visible debug console so you can watch logs while working
REM through docs\TESTING_CHECKLIST.md.
REM
REM Interpreter comes from _python.bat (override: set AERIS_PYTHON=<path>).
set KMP_DUPLICATE_LIB_OK=TRUE
set AERIS_SPLIT_BRAIN=1
cd /d "%~dp0"
call "%~dp0_python.bat"
echo Starting AERIS (split-brain, debug console)...
"%AERIS_PY%" run_gui.py
echo.
echo AERIS exited. Logs above. Press any key to close this window.
pause >nul
