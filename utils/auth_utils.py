from flask import session, redirect, url_for
from functools import wraps

def require_teacher_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('teacher_logged_in'):
            return redirect(url_for('teacher_auth_bp.teacher_login'))
        return f(*args, **kwargs)
    return decorated_function
