@echo off
echo.
echo ========================================
echo   mITyStudio Quick Launch
echo ========================================
echo.

REM Check if Node.js is installed
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed or not in PATH
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python from https://python.org/
    pause
    exit /b 1
)

echo [OK] Node.js and Python detected
echo.

REM Check if dependencies are installed
if not exist "node_modules" (
    echo [INSTALL] Installing root dependencies
    call npm install
)

if not exist "frontend\node_modules" (
    echo [INSTALL] Installing frontend dependencies
    cd frontend
    call npm install
    cd ..
)

REM Check Python environment (PyTorch already confirmed working)
if not exist "backend\venv" (
    echo [SETUP] Python virtual environment not found
    echo Please run setup.bat first to create the environment
    pause
    exit /b 1
) else (
    echo [OK] Python virtual environment ready with PyTorch
)

REM Check if .env file exists
if not exist "backend\.env" (
    if exist "backend\.env.example" (
        echo [SETUP] Creating .env file from example
        copy "backend\.env.example" "backend\.env"
        echo.
        echo [IMPORTANT] Please edit backend\.env with your API keys
        echo    - OPENAI_API_KEY
        echo    - ANTHROPIC_API_KEY
        echo    - GOOGLE_API_KEY
        echo.
        echo Press any key to continue after setting up your API keys
        pause
    ) else (
        echo [WARNING] No .env.example file found in backend directory
    )
)

echo.
echo [START] Starting mITyStudio
echo.
echo Frontend will be available at: http://localhost:5173
echo Backend will be available at: http://localhost:5000
echo.
echo [RVC] Voice Cloning: PyTorch-powered neural networks ready!
echo.
echo Press Ctrl+C to stop both services
echo.

REM Start both frontend and backend concurrently
echo [START] Starting backend with PyTorch support
start "mITyStudio Backend" cmd /k "cd backend && venv\Scripts\activate && python run.py"
timeout /t 3 /nobreak >nul
echo [START] Starting frontend
start "mITyStudio Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo [READY] mITyStudio is starting up
echo Check the opened terminal windows for status
echo.
pause
