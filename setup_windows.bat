@echo off
REM 
REM 

echo ====================================
echo RJ Auto Metadata - Windows Setup
echo ====================================
echo.

REM 
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found!
    echo.
    echo Please install Python 3.9+ from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo Python found:
python --version
echo.

REM 
python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: pip not available!
    echo Please reinstall Python with pip included.
    pause
    exit /b 1
)

REM 
echo Upgrading pip...
python -m pip install --upgrade pip

REM 
echo.
echo Installing Python dependencies...
echo This may take a few minutes...
python -m pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo WARNING: Some dependencies failed to install.
    echo The app may still work for basic functionality.
    echo.
)

REM 
if not exist main.py (
    echo ERROR: main.py not found!
    echo Please run this script from the RJ Auto Metadata directory.
    pause
    exit /b 1
)

REM 
if exist test_cross_platform.py (
    echo.
    echo Running compatibility test...
    python test_cross_platform.py
)

REM 
echo.
echo Creating run script...
echo @echo off > run_app.bat
echo echo Starting RJ Auto Metadata... >> run_app.bat
echo python main.py >> run_app.bat
echo pause >> run_app.bat

echo.
echo ====================================
echo Setup completed!
echo ====================================
echo.
echo To run RJ Auto Metadata:
echo   1. Double-click run_app.bat
echo   2. Or run: python main.py
echo.
echo External tools status:
echo   - For vector files (.ai/.eps/.svg): Install Ghostscript
echo   - For video files (.mp4/.mkv): Install FFmpeg  
echo   - For metadata writing: Install ExifTool
echo.
echo Download links in README.md
echo.
pause
