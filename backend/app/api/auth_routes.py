"""
Authentication API Routes
Handles user authentication and session management
"""

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from app.utils.decorators import handle_errors

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
@handle_errors
def login():
    """
    Simple authentication (for demo purposes)
    In production, implement proper user authentication
    """
    data = request.get_json()
    username = data.get('username', 'demo_user')
    
    # For demo purposes, always allow login
    access_token = create_access_token(identity=username)
    
    return jsonify({
        'access_token': access_token,
        'user': {
            'username': username,
            'id': 'demo_user_id'
        },
        'message': 'Login successful'
    })


@auth_bp.route('/verify', methods=['GET'])
@jwt_required()
@handle_errors
def verify_token():
    """
    Verify JWT token validity
    """
    current_user = get_jwt_identity()
    
    return jsonify({
        'valid': True,
        'user': current_user
    })


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
@handle_errors
def logout():
    """
    Logout endpoint (client-side token removal)
    """
    return jsonify({'message': 'Logout successful'})


@auth_bp.route('/user', methods=['GET'])
@jwt_required()
@handle_errors
def get_current_user():
    """
    Get current user information
    """
    current_user = get_jwt_identity()
    
    return jsonify({
        'user': {
            'username': current_user,
            'id': 'demo_user_id',
            'email': f"{current_user}@example.com",
            'preferences': {
                'theme': 'dark',
                'default_tempo': 120,
                'default_key': 'C'
            }
        }
    })
