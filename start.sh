#!/bin/bash

echo ""
echo "========================================"
echo "   mITyStudio Quick Launch (Unix)"
echo "========================================"
echo ""

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed or not in PATH"
    echo "Please install Node.js from https://nodejs.org/"
    exit 1
fi

# Check if Python is installed
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "❌ Python is not installed or not in PATH"
    echo "Please install Python from https://python.org/"
    exit 1
fi

# Use python3 if available, otherwise python
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_CMD="python"
fi

echo "✅ Node.js and Python detected"
echo ""

# Check if dependencies are installed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing root dependencies..."
    npm install
fi

if [ ! -d "frontend/node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    cd frontend
    npm install
    cd ..
fi

if [ ! -d "backend/venv" ]; then
    echo "🐍 Creating Python virtual environment..."
    cd backend
    $PYTHON_CMD -m venv venv
    source venv/bin/activate
    echo "📦 Installing full dependencies (including PyTorch for RVC)..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install dependencies"
        echo "This includes PyTorch which is required for RVC voice cloning"
        cd ..
        exit 1
    fi
    cd ..
else
    echo "✅ Python virtual environment exists"
    echo "🔍 Verifying PyTorch installation..."
    cd backend
    source venv/bin/activate
    python -c "import torch; print('PyTorch version:', torch.__version__)" 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "⚠️  PyTorch not found in virtual environment"
        echo "📦 Installing full dependencies..."
        pip install -r requirements.txt
        if [ $? -ne 0 ]; then
            echo "❌ Failed to install PyTorch dependencies"
            cd ..
            exit 1
        fi
    fi
    cd ..
fi

# Check if .env file exists
if [ ! -f "backend/.env" ]; then
    if [ -f "backend/.env.example" ]; then
        echo "📝 Creating .env file from example..."
        cp "backend/.env.example" "backend/.env"
        echo ""
        echo "⚠️  IMPORTANT: Please edit backend/.env with your API keys"
        echo "    - OPENAI_API_KEY"
        echo "    - ANTHROPIC_API_KEY"
        echo "    - GOOGLE_API_KEY"
        echo ""
        echo "Press any key to continue after setting up your API keys..."
        read -n 1 -s
    else
        echo "❌ No .env.example file found in backend directory"
    fi
fi

echo ""
echo "🚀 Starting mITyStudio..."
echo ""
echo "Frontend will be available at: http://localhost:5173"
echo "Backend will be available at: http://localhost:5000"
echo ""
echo "🎤 RVC Voice Cloning: PyTorch-powered neural networks ready!"
echo ""
echo "Press Ctrl+C to stop both services"
echo ""

# Start both frontend and backend concurrently
echo "🎵 Starting backend with PyTorch support..."
cd backend
source venv/bin/activate
$PYTHON_CMD run.py &
BACKEND_PID=$!
cd ..

echo "🎵 Starting frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "🎵 mITyStudio is running!"
echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for interrupt
trap "echo ''; echo 'Stopping services...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT

wait
