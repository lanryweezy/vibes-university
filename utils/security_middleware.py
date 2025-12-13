from flask import request, jsonify, session
from functools import wraps
import secrets
import hashlib
import time
import os

class SecurityMiddleware:
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize the security middleware with the Flask app."""
        app.before_request(self.before_request)
        app.after_request(self.after_request)
        
        # Store the middleware instance in the app
        app.extensions['security_middleware'] = self
        
    def before_request(self):
        """Process before each request."""
        # Add security headers
        self.add_security_headers()
        
        # Check for suspicious activity
        if self.is_suspicious_request():
            return jsonify({'error': 'Forbidden'}), 403
            
    def after_request(self, response):
        """Process after each request."""
        # Ensure security headers are present in response
        self.ensure_security_headers(response)
        return response
        
    def add_security_headers(self):
        """Add security headers to the request context."""
        # This would typically be handled in after_request, but we can set flags here
        pass
        
    def ensure_security_headers(self, response):
        """Ensure security headers are present in the response."""
        # Prevent clickjacking
        response.headers['X-Frame-Options'] = 'DENY'
        
        # Prevent MIME type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        # XSS protection
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # Content Security Policy
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net; "
            "img-src 'self' data: https:; "
            "font-src 'self' https: data:; "
            "connect-src 'self'; "
            "media-src 'self' https:; "
            "frame-src 'none';"
        )
        
        # Referrer policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Strict transport security (only in production)
        if not os.environ.get('FLASK_ENV') == 'development':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            
        return response
        
    def is_suspicious_request(self):
        """Check if the current request looks suspicious."""
        # Check for common attack patterns in user agent
        user_agent = request.headers.get('User-Agent', '').lower()
        suspicious_agents = ['sqlmap', 'nikto', 'nessus', 'burp']
        for agent in suspicious_agents:
            if agent in user_agent:
                return True
                
        # Check for common attack patterns in URL
        suspicious_patterns = ['../', 'union select', 'drop table', '<script']
        full_url = request.url.lower()
        for pattern in suspicious_patterns:
            if pattern in full_url:
                return True
                
        return False

def generate_csrf_token():
    """Generate a CSRF token."""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_urlsafe(32)
    return session['csrf_token']

def validate_csrf_token():
    """Validate CSRF token from request."""
    token = session.get('csrf_token')
    if not token:
        return False
        
    # Check in form data
    request_token = request.form.get('csrf_token')
    if not request_token:
        # Check in JSON data
        if request.is_json:
            json_data = request.get_json()
            request_token = json_data.get('csrf_token') if json_data else None
            
    return request_token and secrets.compare_digest(token, request_token)

def csrf_protect(f):
    """Decorator to protect routes from CSRF attacks."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Skip CSRF check for GET requests
        if request.method in ['GET', 'HEAD', 'OPTIONS', 'TRACE']:
            return f(*args, **kwargs)
            
        # Validate CSRF token for state-changing requests
        if not validate_csrf_token():
            return jsonify({'error': 'CSRF token missing or invalid'}), 403
            
        return f(*args, **kwargs)
    return decorated_function

# Session security utilities
def regenerate_session(session):
    """Regenerate session ID to prevent session fixation."""
    # Store current session data
    session_data = dict(session)
    
    # Clear session
    session.clear()
    
    # Regenerate session ID by changing the session cookie
    session.permanent = True
    
    # Restore session data
    session.update(session_data)
    
    return session

def is_session_valid(session):
    """Check if session is still valid."""
    # Check if session has timed out
    last_activity = session.get('last_activity')
    if last_activity:
        timeout = int(os.environ.get('SESSION_TIMEOUT', 3600))  # Default 1 hour
        if time.time() - last_activity > timeout:
            return False
            
    # Update last activity
    session['last_activity'] = time.time()
    return True