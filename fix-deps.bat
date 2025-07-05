@echo off
echo.
echo ========================================
echo   mITyStudio Dependency Fix
echo ========================================
echo.

echo 🔧 This script will update and fix dependencies
echo.

REM Check if virtual environment exists
if not exist "backend\venv" (
    echo ❌ Virtual environment not found. Please run setup.bat first.
    pause
    exit /b 1
)

echo 🐍 Updating Python dependencies...
cd backend
call venv\Scripts\activate

echo Upgrading pip...
python -m pip install --upgrade pip

echo Updating all packages...
pip install --upgrade -r requirements.txt

echo.
echo 📦 Updating Node.js dependencies...
cd ..
npm update

echo.
echo ✅ Dependencies updated successfully!
echo.
pause
pip install librosa==0.10.2
pip install soundfile==0.12.1
pip install langchain==0.2.16
pip install langchain-openai==0.1.23
pip install langchain-anthropic==0.1.23

echo Updating other packages...
pip install --upgrade Flask==3.0.3
pip install --upgrade openai==1.51.2
pip install --upgrade anthropic==0.34.2
pip install --upgrade requests==2.32.3

cd ..

echo.
echo Fixing frontend ESLint issues...
cd frontend
npm install eslint@^9.0.0 --save-dev
cd ..

echo.
echo ✅ Dependency fix completed!
echo.
echo You can now run start.bat to launch the application
echo.
pause
