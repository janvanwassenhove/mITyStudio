@echo off
echo.
echo ========================================
echo   mITyStudio Installation Status
echo ========================================
echo.

echo 🔍 Checking installation status...
echo.

REM Check Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Node.js: Not installed
) else (
    for /f "tokens=*" %%i in ('node --version') do echo ✅ Node.js: %%i
)

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python: Not installed
) else (
    for /f "tokens=*" %%i in ('python --version') do echo ✅ Python: %%i
)

echo.
echo 📦 Dependency Status:
echo.

REM Check root dependencies
if exist "node_modules" (
    echo ✅ Root npm dependencies: Installed
) else (
    echo ❌ Root npm dependencies: Missing
)

REM Check frontend dependencies
if exist "frontend\node_modules" (
    echo ✅ Frontend dependencies: Installed
) else (
    echo ❌ Frontend dependencies: Missing
)

REM Check backend virtual environment
if exist "backend\venv" (
    echo ✅ Python virtual environment: Created
    
    REM Test key Python packages
    cd backend
    call venv\Scripts\activate
    python -c "import flask; print('✅ Flask: ' + flask.__version__)" 2>nul || echo ❌ Flask: Not installed
    python -c "import openai; print('✅ OpenAI: ' + openai.__version__)" 2>nul || echo ❌ OpenAI: Not installed
    python -c "import anthropic; print('✅ Anthropic: ' + anthropic.__version__)" 2>nul || echo ❌ Anthropic: Not installed
    cd ..
) else (
    echo ❌ Python virtual environment: Missing
)

REM Check Electron dependencies
if exist "node_modules\electron" (
    echo ✅ Electron dependencies: Installed
    npm list electron >nul 2>&1
    if %errorlevel% neq 0 (
        echo ⚠️  Electron: Dependencies incomplete
    ) else (
        echo ✅ Electron: Ready
    )
) else (
    echo ❌ Electron dependencies: Missing
)
) else (
    echo ❌ Electron dependencies: Missing
)

echo.
echo 📝 Configuration Status:
echo.

if exist "backend\.env" (
    echo ✅ Environment file: Found
) else (
    echo ❌ Environment file: Missing (backend\.env)
)

echo.
echo 🚀 Next Steps:
echo.

if not exist "backend\venv" (
    echo 1. Run install-backend.bat to set up Python environment
)

if not exist "frontend\node_modules" (
    echo 2. Run: cd frontend ^&^& npm install
)

if not exist "electron\node_modules" (
    echo 3. Run install-electron.bat to set up desktop app
)

if not exist "backend\.env" (
    echo 4. Create backend\.env file with your API keys
)

echo 5. Run start.bat to launch the application
echo.
pause
