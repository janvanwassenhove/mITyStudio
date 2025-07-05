#!/usr/bin/env python3
"""
Setup script for mITyStudio Backend
Initializes the database and creates necessary directories
"""

import os
import sys
from pathlib import Path

def setup_backend():
    """Set up the backend environment"""
    print("🚀 Setting up mITyStudio Backend...")
    
    # Create necessary directories
    directories = [
        'uploads',
        'temp_audio',
        'audio_cache',
        'logs',
        'migrations'
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✅ Created directory: {directory}")
    
    # Check if .env file exists
    if not Path('.env').exists():
        if Path('.env.example').exists():
            print("📝 Copying .env.example to .env")
            import shutil
            shutil.copy('.env.example', '.env')
            print("⚠️  Please edit .env file with your API keys")
        else:
            print("❌ .env.example not found")
    else:
        print("✅ .env file already exists")
    
    # Check Python dependencies
    try:
        import flask
        print("✅ Flask is installed")
    except ImportError:
        print("❌ Flask not found. Run: pip install -r requirements.txt")
        return False
    
    print("\n🎉 Backend setup complete!")
    print("\n📋 Next steps:")
    print("1. Edit the .env file with your API keys")
    print("2. Run: python run.py")
    print("3. Visit: http://localhost:5000/health")
    
    return True

if __name__ == '__main__':
    setup_backend()
