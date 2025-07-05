@echo off
echo.
echo ========================================
echo   mITyStudio Development Mode
echo ========================================
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
    echo 🐍 Setting up Python environment...
    cd backend
    python -m venv venv
    call venv\Scripts\activate
    pip install -r requirements.txt
    cd ..
)

echo.
echo 🔧 Starting development servers...
echo.
echo Frontend (Vite): http://localhost:5173
echo Backend (Flask): http://localhost:5000
echo.

REM Start backend in development mode with auto-reload
start "Backend Dev" cmd /k "cd backend && venv\Scripts\activate && set FLASK_ENV=development && python run.py"

REM Wait a moment for backend to start
timeout /t 3 /nobreak >nul

REM Start frontend with hot reload
start "Frontend Dev" cmd /k "cd frontend && npm run dev"

echo.
echo 🎵 Development servers starting...
echo Both servers will auto-reload on file changes
echo Press Ctrl+C in each terminal to stop
echo.
pause
