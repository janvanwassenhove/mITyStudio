@echo off
echo.
echo ========================================
echo   mITyStudio Desktop App
echo ========================================
echo.

REM Check if Electron dependencies are installed
if not exist "electron\node_modules" (
    echo 📦 Installing Electron dependencies...
    cd electron
    call npm install
    cd ..
)

REM Check if frontend is built for Electron
if not exist "frontend\dist" (
    echo 🏗️ Building frontend for desktop app...
    cd frontend
    call npx vite build --mode development
    cd ..
    echo ✅ Frontend built successfully
)

REM Start backend if not running
echo 🔍 Checking if backend is running...
curl -f http://localhost:5000/health >nul 2>&1
if %errorlevel% neq 0 (
    echo 🚀 Starting backend server...
    start "Backend for Desktop" cmd /k "cd backend && venv\Scripts\activate && python run.py"
    echo Waiting for backend to start...
    timeout /t 5 /nobreak >nul
) else (
    echo ✅ Backend is already running
)

echo.
echo 🖥️  Launching desktop application...
cd electron
call npm start
cd ..

echo.
echo Desktop app launched!
echo Backend runs at: http://localhost:5000
echo.
pause
