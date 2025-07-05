#!/bin/bash

echo ""
echo "========================================"
echo "   mITyStudio Setup Utility (Unix)"
echo "========================================"
echo ""

echo "🔧 This script will set up your development environment"
echo ""

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed"
    echo "Please install Node.js from: https://nodejs.org/"
    echo "Recommended version: 18.x or 20.x LTS"
    exit 1
fi

if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "❌ Python is not installed"
    echo "Please install Python from: https://python.org/"
    echo "Recommended version: 3.8 or higher"
    exit 1
fi

# Use python3 if available, otherwise python
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_CMD="python"
fi

if ! command -v git &> /dev/null; then
    echo "⚠️  Git is not installed (optional but recommended)"
    echo "Install with your package manager or from: https://git-scm.com/"
fi

echo "✅ Prerequisites check completed"
echo ""

# Install root dependencies
echo "📦 Installing workspace dependencies..."
npm install
if [ $? -ne 0 ]; then
    echo "❌ Failed to install root dependencies"
    exit 1
fi

# Install frontend dependencies
echo "📦 Installing frontend dependencies..."
cd frontend
npm install
if [ $? -ne 0 ]; then
    echo "❌ Failed to install frontend dependencies"
    exit 1
fi
cd ..

# Install Electron dependencies
echo "📦 Installing Electron dependencies..."
cd electron
npm install
if [ $? -ne 0 ]; then
    echo "❌ Failed to install Electron dependencies"
    exit 1
fi
cd ..

# Set up Python environment
echo "🐍 Setting up Python virtual environment..."
cd backend
$PYTHON_CMD -m venv venv
if [ $? -ne 0 ]; then
    echo "❌ Failed to create virtual environment"
    exit 1
fi

source venv/bin/activate
echo "Upgrading pip to latest version..."
pip install --upgrade pip

echo "Installing core Python dependencies (minimal set first)..."
pip install -r requirements-minimal.txt
if [ $? -ne 0 ]; then
    echo "❌ Failed to install minimal Python dependencies"
    exit 1
fi

echo "Installing additional dependencies..."
pip install redis==5.0.8
pip install celery==5.3.6
pip install "numpy>=1.26.0,<2.0.0"
pip install "scipy>=1.11.0"
pip install pydub==0.25.1

echo "Installing audio processing libraries..."
pip install librosa==0.10.2
pip install soundfile==0.12.1

echo "Installing AI/LangChain libraries..."
pip install langchain==0.2.16
pip install langchain-openai==0.1.23
pip install langchain-anthropic==0.1.23

echo "Installing development tools..."
pip install pytest==8.3.3
pip install pytest-flask==1.3.0
pip install black==24.8.0
pip install flake8==7.1.1
pip install mypy==1.11.2
cd ..

# Set up environment files
echo "📝 Setting up environment configuration..."
if [ ! -f "backend/.env" ]; then
    if [ -f "backend/.env.example" ]; then
        cp "backend/.env.example" "backend/.env"
        echo "✅ Created .env file from example"
    else
        echo "Creating basic .env file..."
        cat > backend/.env << EOF
FLASK_ENV=development
FLASK_DEBUG=True
SECRET_KEY=dev-secret-key-change-in-production
DATABASE_URL=sqlite:///mitystudio.db
OPENAI_API_KEY=your-openai-api-key-here
ANTHROPIC_API_KEY=your-anthropic-api-key-here
GOOGLE_API_KEY=your-google-api-key-here
EOF
    fi
    
    echo ""
    echo "⚠️  IMPORTANT: Configure your API keys in backend/.env"
    echo "    - OPENAI_API_KEY: Get from https://platform.openai.com/"
    echo "    - ANTHROPIC_API_KEY: Get from https://console.anthropic.com/"
    echo "    - GOOGLE_API_KEY: Get from https://console.cloud.google.com/"
    echo ""
fi

echo ""
echo "🎉 Setup completed successfully!"
echo ""
echo "Available commands:"
echo "  ./start.sh     - Launch full development environment"
echo "  ./dev.sh       - Development mode with auto-reload"
echo "  ./desktop.sh   - Launch desktop application"
echo "  ./build.sh     - Build for production"
echo ""
echo "Next steps:"
echo "1. Configure API keys in backend/.env"
echo "2. Run './start.sh' to launch the application"
echo ""
echo "Note: You may need to make scripts executable:"
echo "  chmod +x *.sh"
echo ""
