@echo off
REM -- AERIS launcher --------------------------------------------------
REM The interpreter is resolved by _python.bat - do not hardcode a path
REM here again (the pinned anaconda path broke every launcher when that
REM install was removed). Override with:  set AERIS_PYTHON=<path>
REM
REM pythonw.exe = no console window. For a debug console, run:
REM     AERIS.bat debug
REM
REM Speed profile (2026-09-15, measured on this laptop):
REM   AERIS_LITE_ML=1         window accepts commands in ~2 s instead of ~14 s
REM                           (no model weights loaded during boot)
REM   AERIS_PREWARM (on)      the models then load on a background thread, so
REM                           the first command that needs them doesn't stall
REM   AERIS_IDLE_UNLOAD_S     keep the brain's models warm for 30 min between
REM                           uses; reloading them costs ~4 s on the next command
REM   AERIS_LLM_IDLE_UNLOAD_S the 1 GB chat model still goes after 5 min (~3.6 s
REM                           to reload), since it is by far the biggest thing
REM For the smallest resting memory instead, use AERIS_LIGHT.bat.
set KMP_DUPLICATE_LIB_OK=TRUE
set AERIS_LITE_ML=1
set AERIS_IDLE_UNLOAD_S=1800
set AERIS_LLM_IDLE_UNLOAD_S=300
cd /d "%~dp0"
call "%~dp0_python.bat"
if /i "%1"=="debug" (
    "%AERIS_PY%" run_gui.py
) else (
    start "" "%AERIS_PYW%" run_gui.py
)
