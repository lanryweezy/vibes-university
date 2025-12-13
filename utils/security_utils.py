import hashlib
import secrets
import os
import re
from functools import wraps
from flask import session, jsonify, request
import hmac

def generate_secure_token():
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(32)

def hash_password(password):
    """Hash a password using a salt."""
    salt = secrets.token_hex(16)
    pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return salt + pwdhash.hex()

def verify_password(stored_password, provided_password):
    """Verify a stored password against a provided password."""
    salt = stored_password[:32]
    stored_hash = stored_password[32:]
    pwdhash = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return hmac.compare_digest(stored_hash, pwdhash.hex())

def validate_email(email):
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    """Validate phone number format (simple validation)."""
    # Remove all non-digit characters
    digits_only = re.sub(r'\D', '', phone)
    # Check if it's between 10-15 digits
    return 10 <= len(digits_only) <= 15

def sanitize_input(text):
    """Basic input sanitization to prevent XSS."""
    if not isinstance(text, str):
        return text
    # Remove potentially dangerous characters
    text = text.replace('<', '&lt;').replace('>', '&gt;')
    text = text.replace('"', '&quot;').replace("'", '&#x27;')
    return text

def require_admin_auth(f):
    """Decorator to require admin authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return jsonify({'error': 'Not authorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

def require_student_auth(f):
    """Decorator to require student authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('enrollment'):
            return jsonify({'error': 'Not authorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

def get_env_variable(var_name, default_value=None, required=False):
    """Safely get environment variable with optional default."""
    value = os.environ.get(var_name, default_value)
    if required and value is None:
        raise ValueError(f"Required environment variable {var_name} is not set")
    return value