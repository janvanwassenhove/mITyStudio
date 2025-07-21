"""
mITyStudio Backend API
Flask application serving AI-powered music composition APIs
"""

from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()


def create_app(config_name='development'):
    """Application factory pattern"""
    app = Flask(__name__)
    
    # Configuration
    app.config.update(
        SECRET_KEY=os.getenv('SECRET_KEY', 'dev-secret-key'),
        SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', 'sqlite:///mitystudio.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY=os.getenv('JWT_SECRET_KEY', 'jwt-secret-string'),
        JWT_ACCESS_TOKEN_EXPIRES=False,
        # AI Service API Keys
        OPENAI_API_KEY=os.getenv('OPENAI_API_KEY'),
        ANTHROPIC_API_KEY=os.getenv('ANTHROPIC_API_KEY'),
        GOOGLE_API_KEY=os.getenv('GOOGLE_API_KEY'),
        # Audio processing
        UPLOAD_FOLDER=os.getenv('UPLOAD_FOLDER', 'uploads'),
        MAX_CONTENT_LENGTH=1024 * 1024 * 1024,  # 1GB max file size for unlimited voice training
        # Voice training directories
        VOICES_DIR=os.getenv('VOICES_DIR', 'app/data/voices'),
        TRAINING_DIR=os.getenv('TRAINING_DIR', 'app/data/training'), 
        MODELS_DIR=os.getenv('MODELS_DIR', 'app/data/models'),
        # Redis for caching
        REDIS_URL=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    )
    
    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    
    # CORS configuration
    CORS(app, origins=[
        "http://localhost:3000",  # Frontend dev server
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ])
    
    # Register blueprints
    from app.api import ai_bp, audio_bp, project_bp, auth_bp, voice_bp
    
    app.register_blueprint(ai_bp, url_prefix='/api/ai')
    app.register_blueprint(audio_bp, url_prefix='/api/audio')
    app.register_blueprint(project_bp, url_prefix='/api/projects')
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(voice_bp, url_prefix='/api/voice')
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        return {'status': 'healthy', 'service': 'mITyStudio Backend'}
    
    @app.route('/api/status')
    def api_status():
        return {
            'status': 'online',
            'version': '1.0.0',
            'services': {
                'ai': bool(app.config.get('OPENAI_API_KEY') or app.config.get('ANTHROPIC_API_KEY')),
                'audio': True,
                'voice': True,
                'database': True
            }
        }
    
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
