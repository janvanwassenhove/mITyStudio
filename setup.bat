@echo off
echo ==================================================
echo Setting up mITyStudio Development Environment
echo ==================================================

REM Check for Node.js
echo Checking Node.js installation...
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Node.js is not installed or not in PATH
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

REM Check for Python
echo Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.12 from https://python.org/
    pause
    exit /b 1
)

echo ==================================================
echo Installing Frontend Dependencies
echo ==================================================

REM Install root workspace dependencies (excluding backend)
echo Installing workspace dependencies...
npm install --ignore-scripts

echo Installing frontend dependencies...
cd frontend
npm install
if %errorlevel% neq 0 (
    echo ERROR: Failed to install frontend dependencies
    cd ..
    pause
    exit /b 1
)
cd ..

echo Installing electron dependencies...
cd electron
npm install
if %errorlevel% neq 0 (
    echo WARNING: Failed to install electron dependencies
    echo You can install them later with: cd electron && npm install
)
cd ..

echo ==================================================
echo Setting up Python Backend Environment
echo ==================================================

REM Change to backend directory
cd backend

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating Python virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip first
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install compatible versions first
echo Installing core Python dependencies...
pip install wheel setuptools
pip install "numpy>=1.26.0,<2.0.0"
pip install "tensorflow>=2.15.0"

REM Install remaining requirements
echo Installing remaining Python dependencies...
pip install -r requirements.txt --upgrade

REM Return to root directory
cd ..

REM Set up environment files
echo Setting up environment configuration...
if not exist "backend\.env" (
    if exist "backend\.env.example" (
        copy "backend\.env.example" "backend\.env"
        echo Created .env file from example
    ) else (
        echo Creating basic .env file...
        echo FLASK_ENV=development > backend\.env
        echo FLASK_DEBUG=True >> backend\.env
        echo SECRET_KEY=dev-secret-key-change-in-production >> backend\.env
        echo DATABASE_URL=sqlite:///mitystudio.db >> backend\.env
        echo OPENAI_API_KEY=your-openai-api-key-here >> backend\.env
        echo ANTHROPIC_API_KEY=your-anthropic-api-key-here >> backend\.env
        echo GOOGLE_API_KEY=your-google-api-key-here >> backend\.env
    )
    
    echo.
    echo IMPORTANT: Configure your API keys in backend\.env
    echo - OPENAI_API_KEY: Get from https://platform.openai.com/
    echo - ANTHROPIC_API_KEY: Get from https://console.anthropic.com/
    echo - GOOGLE_API_KEY: Get from https://console.cloud.google.com/
    echo.
)

echo ==================================================
echo Setup Complete!
echo ==================================================
echo.
echo To start development:
echo   Frontend: npm run dev
echo   Backend:  cd backend && venv\Scripts\activate && python run.py
echo   Full:     npm run start
echo.
pause
