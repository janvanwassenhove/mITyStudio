@echo off
echo.
echo ========================================
echo   mITyStudio Cleanup Utility
echo ========================================
echo.

echo ⚠️  This will remove all installed dependencies and build files
echo    You will need to run setup.bat again after cleanup
echo.
set /p confirm="Are you sure you want to continue? (y/N): "
if /i not "%confirm%"=="y" (
    echo Cleanup cancelled
    pause
    exit /b 0
)

echo.
echo 🧹 Cleaning up development environment...
echo.

REM Remove node_modules directories
echo Removing Node.js dependencies...
if exist "node_modules" (
    echo - Root node_modules
    rmdir /s /q node_modules
)
if exist "frontend\node_modules" (
    echo - Frontend node_modules
    rmdir /s /q frontend\node_modules
)
if exist "electron\node_modules" (
    echo - Electron node_modules
    rmdir /s /q electron\node_modules
)

REM Remove Python virtual environment
if exist "backend\venv" (
    echo - Python virtual environment
    rmdir /s /q backend\venv
)

REM Remove Python cache files
echo Removing Python cache files...
for /d /r backend %%d in (__pycache__) do (
    if exist "%%d" rmdir /s /q "%%d"
)

REM Remove build directories
echo Removing build files...
if exist "frontend\dist" (
    echo - Frontend build
    rmdir /s /q frontend\dist
)
if exist "backend\build" (
    echo - Backend build
    rmdir /s /q backend\build
)
if exist "electron\dist" (
    echo - Electron build
    rmdir /s /q electron\dist
)

REM Remove log files
echo Removing log files...
if exist "*.log" del /q *.log
if exist "frontend\*.log" del /q frontend\*.log
if exist "backend\*.log" del /q backend\*.log
if exist "electron\*.log" del /q electron\*.log

REM Remove TypeScript build info
echo Removing TypeScript build cache...
if exist "*.tsbuildinfo" del /q *.tsbuildinfo
if exist "frontend\*.tsbuildinfo" del /q frontend\*.tsbuildinfo

REM Remove package-lock files (will be regenerated)
echo Removing lock files...
if exist "package-lock.json" del /q package-lock.json
if exist "frontend\package-lock.json" del /q frontend\package-lock.json
if exist "electron\package-lock.json" del /q electron\package-lock.json

REM Optionally remove .env file
echo.
set /p remove_env="Remove .env file (you'll need to reconfigure API keys)? (y/N): "
if /i "%remove_env%"=="y" (
    if exist "backend\.env" (
        echo - Removing .env file
        del /q backend\.env
    )
)

echo.
echo ✅ Cleanup completed!
echo.
echo Next steps:
echo 1. Run setup.bat to reinstall dependencies
echo 2. Configure API keys in backend\.env
echo 3. Run start.bat to launch the application
echo.
pause
