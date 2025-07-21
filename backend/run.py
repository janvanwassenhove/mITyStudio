#!/usr/bin/env python3
"""
Development server runner for mITyStudio Backend
"""

import os
import sys
import importlib.util
from flask import Flask

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import from the app.py file specifically to avoid conflict with app/ directory
app_py_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
spec = importlib.util.spec_from_file_location("app_module", app_py_path)
app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_module)
create_app = app_module.create_app

def run_dev_server():
    """Run the development server"""
    app = create_app('development')
    
    # Development server configuration
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '0.0.0.0')
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    print(f"Starting mITyStudio Backend on {host}:{port}")
    print(f"Debug mode: {debug}")
    print("Press Ctrl+C to stop the server")
    
    app.run(
        host=host,
        port=port,
        debug=debug,
        threaded=True
    )

if __name__ == '__main__':
    run_dev_server()
