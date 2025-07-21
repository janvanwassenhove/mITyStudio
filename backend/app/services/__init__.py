"""
Services Package
Business logic layer for mITyStudio backend
"""

from .ai_service import AIService
from .audio_service import AudioService
from .project_service import ProjectService

# Try to import LangChain service, but don't fail if dependencies are missing
try:
    from .langchain_service import LangChainService
    __all__ = ['AIService', 'AudioService', 'ProjectService', 'LangChainService']
except ImportError as e:
    print(f"Warning: LangChain service not available - {e}")
    LangChainService = None
    __all__ = ['AIService', 'AudioService', 'ProjectService']
