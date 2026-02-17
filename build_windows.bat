@echo off
REM Build script for creating moddingcartel.exe on Windows

echo ============================================
echo Building moddingcartel.exe
echo ============================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.10 or later from https://www.python.org/
    pause
    exit /b 1
)

echo [1/4] Installing dependencies...
python -m pip install --upgrade pip
pip install pyinstaller
pip install -r requirements.txt

echo.
echo [2/4] Running PyInstaller...
pyinstaller moddingcartel.spec

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    pause
    exit /b 1
)

echo.
echo [3/4] Checking build output...
if exist "dist\moddingcartel.exe" (
    echo SUCCESS: moddingcartel.exe created!
    echo Location: dist\moddingcartel.exe
) else (
    echo ERROR: moddingcartel.exe was not created
    pause
    exit /b 1
)

echo.
echo [4/4] Build complete!
echo.
echo The executable is located at: dist\moddingcartel.exe
echo You can now distribute this single .exe file.
echo.
pause
