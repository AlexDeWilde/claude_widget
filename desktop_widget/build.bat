@echo off
setlocal

echo === Claude Widget - EXE Builder ===
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3 and add it to PATH.
    pause
    exit /b 1
)

:: Check / install PyInstaller
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
    if errorlevel 1 (
        echo ERROR: Failed to install PyInstaller.
        pause
        exit /b 1
    )
)

:: Build
echo Building ClaudeWidget.exe ...
python -m PyInstaller --onefile --windowed --name "ClaudeWidget" app.py

if errorlevel 1 (
    echo.
    echo ERROR: Build failed. See output above.
    pause
    exit /b 1
)

echo.
echo Build complete!
echo Output: dist\ClaudeWidget.exe
echo.
echo You can copy ClaudeWidget.exe anywhere and run it standalone.
echo widget_config.json (position memory) will be created next to the exe on first close.
pause
