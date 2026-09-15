@echo off
REM -- AERIS launcher --------------------------------------------------
REM The interpreter is resolved by _python.bat - do not hardcode a path
REM here again (the pinned anaconda path broke every launcher when that
REM install was removed). Override with:  set AERIS_PYTHON=<path>
REM
REM pythonw.exe = no console window. For a debug console, run:
REM     AERIS.bat debug
set KMP_DUPLICATE_LIB_OK=TRUE
cd /d "%~dp0"
call "%~dp0_python.bat"
if /i "%1"=="debug" (
    "%AERIS_PY%" run_gui.py
) else (
    start "" "%AERIS_PYW%" run_gui.py
)
