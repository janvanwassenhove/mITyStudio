@echo off
echo.
echo ========================================
echo   mITyStudio Installation Test
echo ========================================
echo.

echo 🔍 Testing installation...

REM Test Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Node.js not found
    goto :error
) else (
    for /f "tokens=*" %%i in ('node --version') do echo ✅ Node.js: %%i
)

REM Test Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python not found
    goto :error
) else (
    for /f "tokens=*" %%i in ('python --version') do echo ✅ Python: %%i
)

REM Test Python packages
if exist "backend\venv" (
    echo ✅ Python virtual environment found
    cd backend
    call venv\Scripts\activate
    
    echo Testing Python packages...
    python -c "import flask; print('✅ Flask:', flask.__version__)" 2>nul || echo ❌ Flask not installed
    python -c "import openai; print('✅ OpenAI:', openai.__version__)" 2>nul || echo ❌ OpenAI not installed
    python -c "import anthropic; print('✅ Anthropic:', anthropic.__version__)" 2>nul || echo ❌ Anthropic not installed
    python -c "import numpy; print('✅ NumPy:', numpy.__version__)" 2>nul || echo ❌ NumPy not installed
    
    cd ..
) else (
    echo ❌ Python virtual environment not found
)

REM Test Node.js packages
if exist "frontend\node_modules" (
    echo ✅ Frontend dependencies installed
) else (
    echo ❌ Frontend dependencies not installed
)

if exist "node_modules\electron" (
    echo ✅ Electron dependencies installed
) else (
    echo ❌ Electron dependencies not installed
)

REM Test environment file
if exist "backend\.env" (
    echo ✅ Environment file found
) else (
    echo ⚠️  Environment file not found (backend\.env)
)

echo.
echo 🎉 Installation test completed!
echo.
echo If you see any ❌ errors above, try running:
echo - setup.bat (for fresh installation)
echo - fix-deps.bat (for fixing existing installation)
echo.
goto :end

:error
echo.
echo ❌ Installation test failed!
echo Please run setup.bat to install dependencies
echo.

:end
pause
