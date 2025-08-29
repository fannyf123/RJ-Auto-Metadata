@echo off
REM 
echo Starting RJ Auto Metadata...
echo.

REM 
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found!
    echo Please install Python 3.9+ or run setup_windows.bat
    echo.
    pause
    exit /b 1
)

REM 
if not exist main.py (
    echo ERROR: main.py not found!
    echo Please run this script from the RJ Auto Metadata directory.
    echo Current directory: %CD%
    echo.
    pause
    exit /b 1
)

REM 
python -c "import customtkinter" 2>nul
if %errorlevel% neq 0 (
    echo Dependencies not installed. Installing...
    python -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo.
        echo ERROR: Failed to install dependencies.
        echo Please run setup_windows.bat
        echo.
        pause
        exit /b 1
    )
)

REM 
echo Launching application...
echo Close this window to stop the application.
echo.
python main.py

echo.
echo Application closed. Thanks for using RJ Auto Metadata!
pause
