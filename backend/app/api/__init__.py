"""
API Blueprint Package
"""

from .ai_routes import ai_bp
from .audio_routes import audio_bp
from .project_routes import project_bp
from .auth_routes import auth_bp

__all__ = ['ai_bp', 'audio_bp', 'project_bp', 'auth_bp']
