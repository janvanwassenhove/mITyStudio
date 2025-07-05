"""
Utility decorators for the backend API
"""

import functools
import traceback
from flask import jsonify, current_app
from typing import Callable


def handle_errors(f: Callable) -> Callable:
    """
    Decorator to handle and format API errors consistently
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            current_app.logger.warning(f"Validation error in {f.__name__}: {str(e)}")
            return jsonify({'error': str(e)}), 400
        except FileNotFoundError as e:
            current_app.logger.warning(f"File not found in {f.__name__}: {str(e)}")
            return jsonify({'error': 'Resource not found'}), 404
        except PermissionError as e:
            current_app.logger.warning(f"Permission error in {f.__name__}: {str(e)}")
            return jsonify({'error': 'Access denied'}), 403
        except Exception as e:
            current_app.logger.error(f"Unexpected error in {f.__name__}: {str(e)}")
            current_app.logger.error(traceback.format_exc())
            return jsonify({'error': 'Internal server error'}), 500
    
    return decorated_function


def require_json(f: Callable) -> Callable:
    """
    Decorator to ensure request has JSON content type
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import request
        
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
        
        return f(*args, **kwargs)
    
    return decorated_function


def validate_fields(required_fields: list, optional_fields: list = None) -> Callable:
    """
    Decorator to validate required and optional fields in JSON request
    """
    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import request
            
            if not request.is_json:
                return jsonify({'error': 'Request must be JSON'}), 400
            
            data = request.get_json()
            
            # Check required fields
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                return jsonify({
                    'error': f'Missing required fields: {", ".join(missing_fields)}'
                }), 400
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def log_api_call(f: Callable) -> Callable:
    """
    Decorator to log API calls for monitoring
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import request
        
        current_app.logger.info(f"API call: {request.method} {request.path}")
        
        try:
            result = f(*args, **kwargs)
            current_app.logger.info(f"API call successful: {request.method} {request.path}")
            return result
        except Exception as e:
            current_app.logger.error(f"API call failed: {request.method} {request.path} - {str(e)}")
            raise
    
    return decorated_function
