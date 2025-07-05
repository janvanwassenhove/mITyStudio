@echo off
echo.
echo ========================================
echo   mITyStudio Production Build
echo ========================================
echo.

REM Check if Node.js and Python are available
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Node.js is required for building
    pause
    exit /b 1
)

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python is required for building
    pause
    exit /b 1
)

echo ✅ Prerequisites checked
echo.

REM Install dependencies if needed
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
echo 🏗️  Building production assets...
echo.

REM Build frontend
echo Building frontend...
cd frontend
call npm run build
if %errorlevel% neq 0 (
    echo ❌ Frontend build failed
    cd ..
    pause
    exit /b 1
)
cd ..
echo ✅ Frontend built successfully

REM Prepare backend for production
echo.
echo Preparing backend for production...
cd backend
call venv\Scripts\activate

REM Create production requirements if not exists
if not exist "requirements-prod.txt" (
    echo Creating production requirements...
    echo gunicorn==21.2.0 > requirements-prod.txt
    echo Flask==3.0.0 >> requirements-prod.txt
    echo Flask-CORS==4.0.0 >> requirements-prod.txt
    echo Flask-SQLAlchemy==3.1.1 >> requirements-prod.txt
    echo Flask-Migrate==4.0.5 >> requirements-prod.txt
    echo Flask-JWT-Extended==4.6.0 >> requirements-prod.txt
    echo python-dotenv==1.0.0 >> requirements-prod.txt
    echo marshmallow==3.20.2 >> requirements-prod.txt
    echo webargs==8.3.0 >> requirements-prod.txt
    echo redis==5.0.1 >> requirements-prod.txt
    echo celery==5.3.4 >> requirements-prod.txt
    echo langchain==0.1.0 >> requirements-prod.txt
    echo langchain-openai==0.0.5 >> requirements-prod.txt
    echo langchain-anthropic==0.1.0 >> requirements-prod.txt
    echo openai==1.6.1 >> requirements-prod.txt
    echo anthropic==0.8.1 >> requirements-prod.txt
    echo pydub==0.25.1 >> requirements-prod.txt
    echo librosa==0.10.1 >> requirements-prod.txt
    echo soundfile==0.12.1 >> requirements-prod.txt
    echo numpy==1.24.3 >> requirements-prod.txt
)

pip install -r requirements-prod.txt
cd ..
echo ✅ Backend prepared for production

echo.
echo 🎉 Production build completed!
echo.
echo Frontend build: frontend/dist/
echo Backend ready for deployment with gunicorn
echo.
echo To start production server:
echo   cd backend ^&^& venv\Scripts\activate ^&^& gunicorn -w 4 -b 0.0.0.0:5000 run:app
echo.
pause
