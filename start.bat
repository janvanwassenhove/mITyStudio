@echo off
echo.
echo ========================================
echo   mITyStudio Quick Launch
echo ========================================
echo.

REM Check if Node.js is installed
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Node.js is not installed or not in PATH
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python is not installed or not in PATH
    echo Please install Python from https://python.org/
    pause
    exit /b 1
)

echo ✅ Node.js and Python detected
echo.

REM Check if dependencies are installed
if not exist "node_modules" (
    echo 📦 Installing root dependencies...
    call npm install
)

if not exist "frontend\node_modules" (
    echo 📦 Installing frontend dependencies...
    cd frontend
    call npm install
    cd ..
)

if not exist "backend\venv" (
    echo 🐍 Creating Python virtual environment...
    cd backend
    python -m venv venv
    call venv\Scripts\activate
    python -m pip install --upgrade pip
    pip install -r requirements-minimal.txt
    if %errorlevel% neq 0 (
        echo ❌ Failed to install minimal dependencies
        echo Try running fix-deps.bat or setup.bat
        cd ..
        pause
        exit /b 1
    )
    cd ..
) else (
    echo ✅ Python virtual environment exists
)

REM Check if .env file exists
if not exist "backend\.env" (
    if exist "backend\.env.example" (
        echo 📝 Creating .env file from example...
        copy "backend\.env.example" "backend\.env"
        echo.
        echo ⚠️  IMPORTANT: Please edit backend\.env with your API keys
        echo    - OPENAI_API_KEY
        echo    - ANTHROPIC_API_KEY
        echo    - GOOGLE_API_KEY
        echo.
        echo Press any key to continue after setting up your API keys...
        pause
    ) else (
        echo ❌ No .env.example file found in backend directory
    )
)

echo.
echo 🚀 Starting mITyStudio...
echo.
echo Frontend will be available at: http://localhost:5173
echo Backend will be available at: http://localhost:5000
echo.
echo Press Ctrl+C to stop both services
echo.

REM Start both frontend and backend concurrently
start "mITyStudio Backend" cmd /k "cd backend && venv\Scripts\activate && python run.py"
timeout /t 3 /nobreak >nul
start "mITyStudio Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo 🎵 mITyStudio is starting up...
echo Check the opened terminal windows for status
echo.
pause
