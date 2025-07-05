@echo off
echo.
echo ========================================
echo   mITyStudio Setup Utility
echo ========================================
echo.

echo 🔧 This script will set up your development environment
echo.

REM Check prerequisites
echo Checking prerequisites...
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Node.js is not installed
    echo Please install Node.js from: https://nodejs.org/
    echo Recommended version: 18.x or 20.x LTS
    pause
    exit /b 1
)

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python is not installed
    echo Please install Python from: https://python.org/
    echo Recommended version: 3.8 or higher
    pause
    exit /b 1
)

git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠️  Git is not installed (optional but recommended)
    echo Download from: https://git-scm.com/
)

echo ✅ Prerequisites check completed
echo.

REM Install root dependencies
echo 📦 Installing workspace dependencies...
call npm install
if %errorlevel% neq 0 (
    echo ❌ Failed to install root dependencies
    pause
    exit /b 1
)

REM Install frontend dependencies
echo 📦 Installing frontend dependencies...
cd frontend
call npm install
if %errorlevel% neq 0 (
    echo ❌ Failed to install frontend dependencies
    cd ..
    pause
    exit /b 1
)
cd ..

REM Install Electron dependencies
echo 📦 Installing Electron dependencies...
cd electron
echo Installing Electron with extended timeout...
npm install electron@22.3.27 --save-dev --timeout=300000 --no-optional
if %errorlevel% neq 0 (
    echo ⚠️  Electron installation failed, you can install it later with install-electron.bat
    cd ..
    goto skip_electron
)

echo Installing remaining Electron dependencies...
npm install --timeout=120000
if %errorlevel% neq 0 (
    echo ⚠️  Some Electron dependencies failed, you can fix this later with install-electron.bat
)
cd ..
goto electron_done

:skip_electron
echo ⚠️  Skipping Electron installation - run install-electron.bat later
:electron_done

REM Set up Python environment
echo 🐍 Setting up Python virtual environment...
cd backend
python -m venv venv
if %errorlevel% neq 0 (
    echo ❌ Failed to create virtual environment
    cd ..
    pause
    exit /b 1
)

call venv\Scripts\activate
echo Upgrading pip to latest version...
python -m pip install --upgrade pip

echo Installing core Python dependencies (minimal set first)...
pip install -r requirements-minimal.txt
if %errorlevel% neq 0 (
    echo ❌ Failed to install minimal Python dependencies
    cd ..
    pause
    exit /b 1
)

echo Installing additional dependencies...
pip install redis==5.0.8
pip install celery==5.3.6
pip install "numpy>=1.26.0,<2.0.0"
pip install "scipy>=1.11.0"
pip install pydub==0.25.1

echo Installing audio processing libraries...
pip install librosa==0.10.2
pip install soundfile==0.12.1

echo Installing AI/LangChain libraries...
pip install langchain==0.2.16
pip install langchain-openai==0.1.23
pip install langchain-anthropic==0.1.23

echo Installing development tools...
pip install pytest==8.3.3
pip install pytest-flask==1.3.0
pip install black==24.8.0
pip install flake8==7.1.1
pip install mypy==1.11.2
cd ..

REM Set up environment files
echo 📝 Setting up environment configuration...
if not exist "backend\.env" (
    if exist "backend\.env.example" (
        copy "backend\.env.example" "backend\.env"
        echo ✅ Created .env file from example
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
    echo ⚠️  IMPORTANT: Configure your API keys in backend\.env
    echo    - OPENAI_API_KEY: Get from https://platform.openai.com/
    echo    - ANTHROPIC_API_KEY: Get from https://console.anthropic.com/
    echo    - GOOGLE_API_KEY: Get from https://console.cloud.google.com/
    echo.
)

echo.
echo 🎉 Setup completed successfully!
echo.
echo Available commands:
echo   start.bat    - Launch full development environment
echo   dev.bat      - Development mode with auto-reload
echo   desktop.bat  - Launch desktop application
echo   build.bat    - Build for production
echo.
echo Next steps:
echo 1. Configure API keys in backend\.env
echo 2. Run 'start.bat' to launch the application
echo.
pause
