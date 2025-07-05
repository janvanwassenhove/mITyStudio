#!/bin/bash

echo ""
echo "========================================"
echo "   mITyStudio Cleanup Utility (Unix)"
echo "========================================"
echo ""

echo "⚠️  This will remove all installed dependencies and build files"
echo "    You will need to run ./setup.sh again after cleanup"
echo ""
read -p "Are you sure you want to continue? (y/N): " confirm
if [[ ! $confirm =~ ^[Yy]$ ]]; then
    echo "Cleanup cancelled"
    exit 0
fi

echo ""
echo "🧹 Cleaning up development environment..."
echo ""

# Remove node_modules directories
echo "Removing Node.js dependencies..."
if [ -d "node_modules" ]; then
    echo "- Root node_modules"
    rm -rf node_modules
fi
if [ -d "frontend/node_modules" ]; then
    echo "- Frontend node_modules"
    rm -rf frontend/node_modules
fi
if [ -d "electron/node_modules" ]; then
    echo "- Electron node_modules"
    rm -rf electron/node_modules
fi

# Remove Python virtual environment
if [ -d "backend/venv" ]; then
    echo "- Python virtual environment"
    rm -rf backend/venv
fi

# Remove Python cache files
echo "Removing Python cache files..."
find backend -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find backend -type f -name "*.pyc" -delete 2>/dev/null

# Remove build directories
echo "Removing build files..."
if [ -d "frontend/dist" ]; then
    echo "- Frontend build"
    rm -rf frontend/dist
fi
if [ -d "backend/build" ]; then
    echo "- Backend build"
    rm -rf backend/build
fi
if [ -d "electron/dist" ]; then
    echo "- Electron build"
    rm -rf electron/dist
fi

# Remove log files
echo "Removing log files..."
find . -name "*.log" -delete 2>/dev/null

# Remove TypeScript build info
echo "Removing TypeScript build cache..."
find . -name "*.tsbuildinfo" -delete 2>/dev/null

# Remove package-lock files (will be regenerated)
echo "Removing lock files..."
find . -name "package-lock.json" -delete 2>/dev/null

# Optionally remove .env file
echo ""
read -p "Remove .env file (you'll need to reconfigure API keys)? (y/N): " remove_env
if [[ $remove_env =~ ^[Yy]$ ]]; then
    if [ -f "backend/.env" ]; then
        echo "- Removing .env file"
        rm backend/.env
    fi
fi

echo ""
echo "✅ Cleanup completed!"
echo ""
echo "Next steps:"
echo "1. Run ./setup.sh to reinstall dependencies"
echo "2. Configure API keys in backend/.env"
echo "3. Run ./start.sh to launch the application"
echo ""
