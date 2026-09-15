@echo off
REM -- AERIS interpreter resolver --------------------------------------
REM Every AERIS_*.bat calls this instead of hardcoding a python path.
REM The launchers used to pin C:\Users\Shivang\anaconda3\python.exe; that
REM install was removed from this machine on/before 2026-08-30 and every
REM launcher broke silently at once. One resolver, one place to fix.
REM
REM Order (first hit wins):
REM   1. %AERIS_PYTHON%          - explicit override, set it and nothing else matters
REM   2. .venv\Scripts\python    - a project venv, if you ever make one
REM   3. anaconda3               - the historical env, if it comes back
REM   4. Python310 (user-local)  - CURRENT: repaired 2026-08-30 (pandas 2.3.3
REM                                vs numpy 2.2.6; the old "py3.10 is ABI-broken"
REM                                warning no longer applies)
REM   5. python on PATH          - last resort
REM
REM Sets AERIS_PY (console) and AERIS_PYW (windowless, falls back to AERIS_PY).

set "AERIS_PY="
set "AERIS_PYW="

if defined AERIS_PYTHON (
    set "AERIS_PY=%AERIS_PYTHON%"
    goto :resolved
)

if exist "%~dp0.venv\Scripts\python.exe" (
    set "AERIS_PY=%~dp0.venv\Scripts\python.exe"
    if exist "%~dp0.venv\Scripts\pythonw.exe" set "AERIS_PYW=%~dp0.venv\Scripts\pythonw.exe"
    goto :resolved
)

if exist "C:\Users\Shivang\anaconda3\python.exe" (
    set "AERIS_PY=C:\Users\Shivang\anaconda3\python.exe"
    if exist "C:\Users\Shivang\anaconda3\pythonw.exe" set "AERIS_PYW=C:\Users\Shivang\anaconda3\pythonw.exe"
    goto :resolved
)

if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set "AERIS_PY=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    if exist "%LOCALAPPDATA%\Programs\Python\Python310\pythonw.exe" set "AERIS_PYW=%LOCALAPPDATA%\Programs\Python\Python310\pythonw.exe"
    goto :resolved
)

set "AERIS_PY=python"

:resolved
if not defined AERIS_PYW set "AERIS_PYW=%AERIS_PY%"
exit /b 0
