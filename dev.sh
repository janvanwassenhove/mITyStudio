#!/bin/bash

echo ""
echo "========================================"
echo "   mITyStudio Development Mode (Unix)"
echo "========================================"
echo ""

# Use python3 if available, otherwise python
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_CMD="python"
fi

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
    echo "🐍 Setting up Python environment..."
    cd backend
    $PYTHON_CMD -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    cd ..
fi

echo ""
echo "🔧 Starting development servers..."
echo ""
echo "Frontend (Vite): http://localhost:5173"
echo "Backend (Flask): http://localhost:5000"
echo ""

# Start backend in development mode with auto-reload
echo "🎵 Starting backend in development mode..."
cd backend
source venv/bin/activate
export FLASK_ENV=development
$PYTHON_CMD run.py &
BACKEND_PID=$!
cd ..

# Wait a moment for backend to start
sleep 3

# Start frontend with hot reload
echo "🎵 Starting frontend with hot reload..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "🎵 Development servers starting..."
echo "Both servers will auto-reload on file changes"
echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for interrupt
trap "echo ''; echo 'Stopping development servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT

wait
