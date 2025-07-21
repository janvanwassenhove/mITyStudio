"""
Services Package
Business logic layer for mITyStudio backend
"""

from .ai_service import AIService
from .audio_service import AudioService
from .project_service import ProjectService

# Try to import LangChain service, but don't fail if dependencies are missing
try:
    # Temporarily disable LangChain due to pydantic compatibility issues
    # from .langchain_service import LangChainService
    # __all__ = ['AIService', 'AudioService', 'ProjectService', 'LangChainService']
    LangChainService = None
    __all__ = ['AIService', 'AudioService', 'ProjectService']
    print("Warning: LangChain service temporarily disabled due to pydantic compatibility issues")
except ImportError as e:
    print(f"Warning: LangChain service not available - {e}")
    LangChainService = None
    __all__ = ['AIService', 'AudioService', 'ProjectService']
