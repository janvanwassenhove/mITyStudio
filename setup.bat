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

REM Install core dependencies in the right order to avoid conflicts
echo Installing core Python dependencies...
pip install wheel setuptools

REM Install minimal requirements first (faster startup)
echo Installing minimal requirements for basic functionality...
pip install -r requirements-minimal.txt

REM Install scientific computing dependencies for audio analysis
echo Installing scientific computing dependencies...
pip install "numpy>=1.26.0,<2.0.0" "scipy==1.13.1" scikit-learn==1.5.2

REM Install audio processing dependencies
echo Installing audio processing dependencies...
pip install librosa==0.10.2 soundfile==0.12.1 pydub>=0.25.1

REM Install Redis and Celery for task processing
echo Installing task processing dependencies...
pip install redis==5.0.8 celery==5.3.6

REM Install TensorFlow and ML dependencies (this may take a while)
echo Installing TensorFlow and ML dependencies...
pip install tensorflow==2.17.1 tensorflow-hub==0.16.1

REM Install LangChain dependencies for AI features
echo Installing LangChain AI dependencies...
pip install langchain==0.2.16 langchain-openai==0.1.23 langchain-anthropic==0.1.23
pip install langgraph==0.2.39 "langgraph-checkpoint>=2.1.0" "langgraph-sdk>=0.1.32,<0.2.0"

REM Install development and testing tools
echo Installing development tools...
pip install pytest==8.3.3 pytest-flask==1.3.0 black==24.8.0 flake8==7.1.1 mypy==1.11.2

echo.
echo All core dependencies installed successfully!
echo.

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
echo   Frontend: cd frontend && npm run dev
echo   Backend:  cd backend && venv\Scripts\python.exe app.py  
echo   Full:     start.bat (starts both frontend and backend)
echo.
echo Frontend will be available at: http://localhost:5173/
echo Backend API will be available at: http://localhost:5000/
echo.
pause
