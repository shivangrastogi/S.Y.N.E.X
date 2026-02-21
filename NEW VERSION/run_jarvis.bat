REM Path: d:\New folder (2) - JARVIS\run_jarvis.bat
@echo off
echo ==========================================
echo       JARVIS ASSISTANT - STARTUP
echo ==========================================

echo [1/2] Checking/Installing Dependencies...
py -m pip install "numpy<2" PyQt6 opencv-python websockets fastapi uvicorn requests

echo.
echo [2/2] Launching JARVIS GUI...
echo (This will also start the backend server)
echo.

py ui_laptop/main.py

if %errorlevel% neq 0 (
    echo.
    echo ERROR: JARVIS crashed or failed to start.
    pause
)
