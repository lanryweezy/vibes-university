import time
from functools import wraps
from flask import request, jsonify
import hashlib

# Simple in-memory rate limiter (in production, use Redis or similar)
class RateLimiter:
    def __init__(self):
        self.requests = {}
        self.limits = {}
    
    def set_limit(self, key, max_requests, window_seconds):
        """Set rate limit for a key."""
        self.limits[key] = {
            'max_requests': max_requests,
            'window_seconds': window_seconds
        }
    
    def is_allowed(self, key):
        """Check if a request is allowed based on rate limiting."""
        if key not in self.limits:
            return True
            
        limit = self.limits[key]
        now = time.time()
        
        if key not in self.requests:
            self.requests[key] = []
        
        # Remove old requests outside the window
        self.requests[key] = [
            req_time for req_time in self.requests[key] 
            if now - req_time < limit['window_seconds']
        ]
        
        # Check if we're under the limit
        if len(self.requests[key]) < limit['max_requests']:
            self.requests[key].append(now)
            return True
        else:
            return False
    
    def get_client_key(self, request_obj):
        """Generate a key based on IP address and endpoint."""
        ip = request_obj.remote_addr or 'unknown'
        endpoint = request_obj.endpoint or 'unknown'
        return hashlib.md5(f"{ip}:{endpoint}".encode()).hexdigest()

# Global rate limiter instance
rate_limiter = RateLimiter()

# Set default limits
rate_limiter.set_limit('auth', 5, 60)  # 5 requests per minute for auth endpoints
rate_limiter.set_limit('api', 100, 60)  # 100 requests per minute for API endpoints

def rate_limit(limit_key='api'):
    """Decorator to apply rate limiting to a route."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_key = f"{rate_limiter.get_client_key(request)}:{limit_key}"
            if not rate_limiter.is_allowed(client_key):
                return jsonify({'error': 'Rate limit exceeded. Please try again later.'}), 429
            return f(*args, **kwargs)
        return decorated_function
    return decorator