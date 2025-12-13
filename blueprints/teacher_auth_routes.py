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

@teacher_auth_bp.route('/register', methods=['GET', 'POST'])
@csrf_protect
def teacher_register():
    """Teacher registration page."""
    csrf_token = generate_csrf_token()
    message = ''
    if request.method == 'POST':
        # Validate CSRF token
        if not validate_csrf_token():
            message = 'Invalid request.'
        else:
            email = request.form.get('email')
            password = request.form.get('password')
            full_name = sanitize_input(request.form.get('full_name'))
            phone = request.form.get('phone')
            specialization = sanitize_input(request.form.get('specialization', ''))
            
            # Validate inputs
            if not email or not validate_email(email):
                message = 'Valid email is required.'
            elif not password or len(password) < 6:
                message = 'Password must be at least 6 characters.'
            elif not full_name:
                message = 'Full name is required.'
            elif not phone or not validate_phone(phone):
                message = 'Valid phone number is required.'
            else:
                conn = None
                try:
                    conn = get_db_connection()
                    # Check if user already exists
                    existing_user = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
                    if existing_user:
                        message = 'User with this email already exists.'
                        log_warning(app_logger, "Teacher registration failed - user already exists", email=email)
                    else:
                        # Create user with teacher role
                        password_hash = generate_password_hash(password)
                        cursor = conn.cursor()
                        cursor.execute('INSERT INTO users (email, password_hash, full_name, phone, role) VALUES (?, ?, ?, ?, ?)',
                                       (email, password_hash, full_name, phone, 'teacher'))
                        user_id = cursor.lastrowid
                        
                        # Create teacher profile
                        cursor.execute('INSERT INTO teachers (user_id, specialization) VALUES (?, ?)',
                                       (user_id, specialization))
                        
                        conn.commit()
                        log_info(app_logger, "Teacher registered successfully", user_id=user_id, email=email)
                        message = 'Registration successful! You can now log in.'
                except Exception as e:
                    log_error(app_logger, "Teacher registration failed with exception", error=str(e))
                    message = 'Registration failed. Please try again.'
                finally:
                    if conn:
                        return_db_connection(conn)
    
    return render_template_string('''
    <html><head><title>Teacher Registration - Vibes University</title>
    <style>body{font-family:Arial,sans-serif;background:#111;color:#fff;}.container{max-width:500px;margin:60px auto;background:#222;padding:40px;border-radius:15px;box-shadow:0 8px 32px #0008;}h2{color:#ff6b35;}label{display:block;margin-top:20px;}input,select{width:100%;padding:10px;margin-top:5px;border-radius:8px;border:none;background:#333;color:#fff;}.btn{background:linear-gradient(45deg,#ff6b35,#ff8c42);color:#fff;border:none;padding:15px 0;width:100%;border-radius:8px;font-size:1.1rem;margin-top:30px;cursor:pointer;font-weight:bold;}.msg{margin-top:20px;text-align:center;}.error{color:#f44336;background:rgba(244,67,54,0.1);padding:10px;border-radius:5px;}.success{color:#4CAF50;background:rgba(76,175,80,0.1);padding:10px;border-radius:5px;}</style></head>
    <body><div class="container"><h2>🎓 Teacher Registration</h2>
    <form method="post">
    <input type="hidden" name="csrf_token" value="{{csrf_token}}">
    <label for="full_name">Full Name</label><input type="text" name="full_name" id="full_name" required>
    <label for="email">Email</label><input type="email" name="email" id="email" required>
    <label for="phone">Phone</label><input type="text" name="phone" id="phone" required>
    <label for="specialization">Specialization</label><input type="text" name="specialization" id="specialization">
    <label for="password">Password</label><input type="password" name="password" id="password" required>
    <button class="btn" type="submit">Register as Teacher</button></form>
    {% if message %}<div class="msg {% if 'successful' in message %}success{% else %}error{% endif %}">{{message}}</div>{% endif %}
    <div style="margin-top:20px;text-align:center;">
    <p>Already have an account? <a href="{{url_for('teacher_auth_bp.teacher_login')}}" style="color:#ff6b35;">Login here</a></p>
    <p><a href="/" style="color:#ff6b35;">← Back to Home</a></p>
    </div></div></body></html>
    ''', message=message, csrf_token=csrf_token)

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
    <p>Don't have an account? <a href="{{url_for('teacher_auth_bp.teacher_register')}}" style="color:#ff6b35;">Register here</a></p>
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