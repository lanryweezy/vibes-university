from flask import Blueprint, render_template, render_template_string, redirect, url_for, session, request, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import secrets

# Import utilities
from utils.db_utils import get_db_connection, return_db_connection
from utils.logging_utils import app_logger, security_logger, log_info, log_error, log_warning
from utils.security_utils import validate_email, validate_phone, sanitize_input, get_env_variable
from utils.security_middleware import generate_csrf_token, validate_csrf_token, csrf_protect

teacher_auth_bp = Blueprint('teacher_auth_bp', __name__, url_prefix='/teacher')

# Teacher registration is now admin-only
@teacher_auth_bp.route('/register')
def teacher_register_info():
    """Information page about teacher registration."""
    return render_template_string('''
    <html><head><title>Teacher Registration - Vibes University</title>
    <style>body{font-family:Arial,sans-serif;background:#111;color:#fff;}.container{max-width:500px;margin:60px auto;background:#222;padding:40px;border-radius:15px;box-shadow:0 8px 32px #0008;}h2{color:#ff6b35;}.info{background:rgba(255,107,53,0.1);padding:20px;border-radius:8px;margin:20px 0;}.btn{background:linear-gradient(45deg,#ff6b35,#ff8c42);color:#fff;border:none;padding:15px 0;width:100%;border-radius:8px;font-size:1.1rem;margin-top:30px;cursor:pointer;font-weight:bold;}.msg{margin-top:20px;text-align:center;}</style></head>
    <body><div class="container"><h2>🎓 Teacher Registration</h2>
    <div class="info">
        <p>Teacher registration is now managed exclusively by administrators.</p>
        <p>If you're interested in becoming a teacher at Vibes University, please contact our admin team.</p>
    </div>
    <a href="{{url_for('teacher_auth_bp.teacher_login')}}" class="btn">Login as Teacher</a>
    <div style="margin-top:20px;text-align:center;">
    <p><a href="/" style="color:#ff6b35;">← Back to Home</a></p>
    </div></div></body></html>
    ''')

@teacher_auth_bp.route('/login', methods=['GET', 'POST'])
@csrf_protect
def teacher_login():
    """Teacher login page."""
    csrf_token = generate_csrf_token()
    message = ''
    if request.method == 'POST':
        # Validate CSRF token
        if not validate_csrf_token():
            message = 'Invalid request.'
        else:
            email = request.form.get('email')
            password = request.form.get('password')
            
            # Validate inputs
            if not email or not validate_email(email):
                message = 'Valid email is required.'
            elif not password:
                message = 'Password is required.'
            else:
                conn = None
                try:
                    conn = get_db_connection()
                    # Check if user exists and is a teacher
                    user = conn.execute('SELECT u.*, t.specialization FROM users u LEFT JOIN teachers t ON u.id = t.user_id WHERE u.email = ? AND u.role = ?', 
                                      (email, 'teacher')).fetchone()
                    
                    if not user or not check_password_hash(user['password_hash'], password):
                        message = 'Invalid credentials.'
                        log_warning(security_logger, "Teacher login failed - invalid credentials", email=email)
                    else:
                        # Set session
                        session['teacher_logged_in'] = True
                        session['teacher_id'] = user['id']
                        session['teacher_email'] = user['email']
                        session['teacher_name'] = user['full_name']
                        session['teacher_specialization'] = user['specialization']
                        
                        log_info(security_logger, "Teacher login successful", teacher_id=user['id'], email=email)
                        if conn:
                            return_db_connection(conn)
                        return redirect(url_for('teacher_auth_bp.teacher_dashboard'))
                except Exception as e:
                    log_error(app_logger, "Teacher login failed with exception", error=str(e))
                    message = 'Login failed. Please try again.'
                finally:
                    if conn:
                        return_db_connection(conn)
    
    return render_template_string('''
    <html><head><title>Teacher Login - Vibes University</title>
    <style>body{font-family:Arial,sans-serif;background:#111;color:#fff;}.container{max-width:500px;margin:60px auto;background:#222;padding:40px;border-radius:15px;box-shadow:0 8px 32px #0008;}h2{color:#ff6b35;}label{display:block;margin-top:20px;}input,select{width:100%;padding:10px;margin-top:5px;border-radius:8px;border:none;background:#333;color:#fff;}.btn{background:linear-gradient(45deg,#ff6b35,#ff8c42);color:#fff;border:none;padding:15px 0;width:100%;border-radius:8px;font-size:1.1rem;margin-top:30px;cursor:pointer;font-weight:bold;}.msg{margin-top:20px;text-align:center;}.error{color:#f44336;background:rgba(244,67,54,0.1);padding:10px;border-radius:5px;}.success{color:#4CAF50;background:rgba(76,175,80,0.1);padding:10px;border-radius:5px;}</style></head>
    <body><div class="container"><h2>🎓 Teacher Login</h2>
    <form method="post">
    <input type="hidden" name="csrf_token" value="{{csrf_token}}">
    <label for="email">Email</label><input type="email" name="email" id="email" required>
    <label for="password">Password</label><input type="password" name="password" id="password" required>
    <button class="btn" type="submit">Login as Teacher</button></form>
    {% if message %}<div class="msg {% if 'successful' in message %}success{% else %}error{% endif %}">{{message}}</div>{% endif %}
    <div style="margin-top:20px;text-align:center;">
    <p>Teacher registration is managed by administrators.<br>Contact admin team to become a teacher.</p>
    <p><a href="/" style="color:#ff6b35;">← Back to Home</a></p>
    </div></div></body></html>
    ''', message=message, csrf_token=csrf_token)

@teacher_auth_bp.route('/dashboard')
def teacher_dashboard():
    """Teacher dashboard."""
    # Check if teacher is logged in
    if not session.get('teacher_logged_in'):
        return redirect(url_for('teacher_auth_bp.teacher_login'))
    
    teacher_name = session.get('teacher_name', 'Teacher')
    
    return render_template('teacher_dashboard.html', teacher_name=teacher_name)

@teacher_auth_bp.route('/logout')
def teacher_logout():
    """Teacher logout."""
    session.pop('teacher_logged_in', None)
    session.pop('teacher_id', None)
    session.pop('teacher_email', None)
    session.pop('teacher_name', None)
    session.pop('teacher_specialization', None)
    log_info(security_logger, "Teacher logout successful")
    return redirect(url_for('teacher_auth_bp.teacher_login'))