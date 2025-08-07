"""
Fallback utilities for LangGraph when full LangChain utils are not available
"""

import logging

logger = logging.getLogger(__name__)

def safe_log_error(msg: str) -> None:
    """Safely log error messages"""
    logger.error(msg)
    print(f"Error: {msg}")
