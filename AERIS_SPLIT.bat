@echo off
REM -- AERIS split-architecture text driver ----------------------------
REM Runs the crash-isolated brain: the BRAIN (torch + encoder + skills)
REM runs in its OWN child process, this window stays ML-free. A native
REM crash in the brain can't kill this driver - the supervisor restarts it.
REM
REM Interpreter comes from _python.bat (override: set AERIS_PYTHON=<path>).
set KMP_DUPLICATE_LIB_OK=TRUE
cd /d "%~dp0"
call "%~dp0_python.bat"
"%AERIS_PY%" run_split.py
pause
