from flask import Blueprint, render_template, render_template_string, redirect, url_for, session, jsonify, request
import os
from datetime import datetime
import json
import sqlite3

# Import utilities
from utils.db_utils import get_db_connection, return_db_connection
from utils.logging_utils import app_logger, db_logger, security_logger, payment_logger, log_info, log_error, log_warning
# Import security utilities
from utils.security_utils import validate_email, validate_phone, sanitize_input, get_env_variable
# Import CSRF protection
from utils.security_middleware import generate_csrf_token, csrf_protect

main_bp = Blueprint('main_bp', __name__)

@main_bp.route('/')
def home():
    """Serve the main course platform page"""
    try:
        # Use current directory instead of hardcoded Linux path
        # Adjust path since this file is in 'blueprints' subdirectory
        # os.path.abspath(__file__) is /path/to/repo/blueprints/main_routes.py
        # os.path.dirname(...) is /path/to/repo/blueprints
        # .replace(...) gives /path/to/repo
        base_dir = os.path.dirname(os.path.abspath(__file__)).replace('/blueprints', '').replace('\\blueprints', '')
        index_path = os.path.join(base_dir, 'index.html')
        with open(index_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return jsonify({'error': 'Platform not found'}), 404
    except Exception as e:
        return jsonify({'error': f'Error loading platform: {str(e)}'}), 500

@main_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

@main_bp.route('/student/login', methods=['GET', 'POST'])
def student_login():
    """Render student login page and handle login."""
    message = ''
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        # This is a placeholder for actual login logic
        message = f"Login attempt with {email}"
        # In a real app, you would verify credentials and manage session
        # For now, just show a message.

    return render_template('student_login.html', message=message)

@main_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main_bp.home'))

@main_bp.route('/demo-payment', methods=['GET', 'POST'])
@csrf_protect
def demo_payment():
    if request.method == 'POST':
        name = sanitize_input(request.form.get('name'))
        email = request.form.get('email')
        phone = request.form.get('phone')
        plan_key = request.form.get('plan', 'course')
        
        # Validate email format
        if not validate_email(email):
            csrf_token = generate_csrf_token()
            return render_template_string('''
            <html><head><title>Demo Payment - Vibes University</title><style>body{font-family:Arial,sans-serif;background:#111;color:#fff;}.container{max-width:500px;margin:60px auto;background:#222;padding:40px;border-radius:15px;box-shadow:0 8px 32px #0008;}h2{color:#ff6b35;}label{display:block;margin-top:20px;}input,select{width:100%;padding:10px;margin-top:5px;border-radius:8px;border:none;background:#333;color:#fff;}.btn{background:linear-gradient(45deg,#ff6b35,#ff8c42);color:#fff;border:none;padding:15px 0;width:100%;border-radius:8px;font-size:1.1rem;margin-top:30px;cursor:pointer;font-weight:bold;}.demo-notice{background:#333;color:#ff6b35;padding:15px;border-radius:8px;margin-top:20px;text-align:center;border:1px solid #ff6b35;}.error{color:#f44336;background:rgba(244,67,54,0.1);padding:10px;border-radius:5px;margin:10px 0;}</style></head>
            <body><div class="container"><h2>🎯 Demo Payment</h2><div class="demo-notice"><strong>Testing Mode:</strong> Creates a demo enrollment and redirects to dashboard.</div>
            <div class="error">Invalid email format. Please try again.</div>
            <form method="post"><input type="hidden" name="csrf_token" value="{{csrf_token}}"><label for="plan">Select Plan</label><select name="plan" id="plan"><option value="course">Course Access (₦100,000)</option><option value="online">Online Mentorship (₦400,000)</option><option value="vip">VIP Physical Class (₦2,000,000)</option></select>
            <label for="name">Full Name</label><input type="text" name="name" id="name" required><label for="email">Email</label><input type="email" name="email" id="email" required><label for="phone">Phone</label><input type="text" name="phone" id="phone" required>
            <button class="btn" type="submit">🚀 Access Student Dashboard</button></form></div></body></html>
            ''', csrf_token=csrf_token)
        
        # Validate phone format
        if not validate_phone(phone):
            csrf_token = generate_csrf_token()
            return render_template_string('''
            <html><head><title>Demo Payment - Vibes University</title><style>body{font-family:Arial,sans-serif;background:#111;color:#fff;}.container{max-width:500px;margin:60px auto;background:#222;padding:40px;border-radius:15px;box-shadow:0 8px 32px #0008;}h2{color:#ff6b35;}label{display:block;margin-top:20px;}input,select{width:100%;padding:10px;margin-top:5px;border-radius:8px;border:none;background:#333;color:#fff;}.btn{background:linear-gradient(45deg,#ff6b35,#ff8c42);color:#fff;border:none;padding:15px 0;width:100%;border-radius:8px;font-size:1.1rem;margin-top:30px;cursor:pointer;font-weight:bold;}.demo-notice{background:#333;color:#ff6b35;padding:15px;border-radius:8px;margin-top:20px;text-align:center;border:1px solid #ff6b35;}.error{color:#f44336;background:rgba(244,67,54,0.1);padding:10px;border-radius:5px;margin:10px 0;}</style></head>
            <body><div class="container"><h2>🎯 Demo Payment</h2><div class="demo-notice"><strong>Testing Mode:</strong> Creates a demo enrollment and redirects to dashboard.</div>
            <div class="error">Invalid phone number format. Please try again.</div>
            <form method="post"><input type="hidden" name="csrf_token" value="{{csrf_token}}"><label for="plan">Select Plan</label><select name="plan" id="plan"><option value="course">Course Access (₦100,000)</option><option value="online">Online Mentorship (₦400,000)</option><option value="vip">VIP Physical Class (₦2,000,000)</option></select>
            <label for="name">Full Name</label><input type="text" name="name" id="name" required><label for="email">Email</label><input type="email" name="email" id="email" required><label for="phone">Phone</label><input type="text" name="phone" id="phone" required>
            <button class="btn" type="submit">🚀 Access Student Dashboard</button></form></div></body></html>
            ''', csrf_token=csrf_token)
        
        log_info(payment_logger, "Demo payment initiated", email=email, plan=plan_key)
        
        conn = None
        try:
            conn = get_db_connection()
            user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
            user_id = 0
            if not user:
                from werkzeug.security import generate_password_hash
                import secrets
                password_hash = generate_password_hash(secrets.token_hex(8))
                cursor = conn.cursor()
                cursor.execute('INSERT INTO users (email, password_hash, full_name, phone) VALUES (?, ?, ?, ?)', (email, password_hash, name, phone))
                user_id = cursor.lastrowid
                conn.commit()
                log_info(app_logger, "New user created via demo payment", user_id=user_id, email=email)
            else:
                user_id = user['id']
                log_info(app_logger, "Existing user accessed via demo payment", user_id=user_id, email=email)
            
            plans = { 'course': {'name': 'Course Access', 'price': 100000}, 'online': {'name': 'Online Mentorship', 'price': 400000}, 'vip': {'name': 'VIP Physical Class', 'price': 2000000} }
            plan_details = plans.get(plan_key, plans['course'])
            
            cursor = conn.cursor()
            payment_reference = f'DEMO_{user_id}_{int(datetime.now().timestamp())}'
            cursor.execute("INSERT INTO enrollments (user_id, course_type, price, payment_method, payment_status, payment_reference) VALUES (?, ?, ?, ?, ?, ?)",
                           (user_id, plan_key, plan_details['price'], 'demo', 'completed', payment_reference))
            enrollment_id = cursor.lastrowid
            conn.commit()
            enrollment_for_session = conn.execute("SELECT e.*, u.email, u.full_name FROM enrollments e JOIN users u ON e.user_id = u.id WHERE e.id = ?", (enrollment_id,)).fetchone()
        except Exception as e:
            if conn:
                return_db_connection(conn)
            return jsonify({'error': f'Database error: {str(e)}'}), 500
        finally:
            if conn:
                return_db_connection(conn)
        
        session['enrollment'] = dict(enrollment_for_session)
        log_info(payment_logger, "Demo payment completed", enrollment_id=enrollment_id, user_id=user_id, course_type=plan_key, price=plan_details['price'])
        return redirect(url_for('dashboard'))
    
    csrf_token = generate_csrf_token()
    return render_template_string('''
    <html><head><title>Demo Payment - Vibes University</title><style>body{font-family:Arial,sans-serif;background:#111;color:#fff;}.container{max-width:500px;margin:60px auto;background:#222;padding:40px;border-radius:15px;box-shadow:0 8px 32px #0008;}h2{color:#ff6b35;}label{display:block;margin-top:20px;}input,select{width:100%;padding:10px;margin-top:5px;border-radius:8px;border:none;background:#333;color:#fff;}.btn{background:linear-gradient(45deg,#ff6b35,#ff8c42);color:#fff;border:none;padding:15px 0;width:100%;border-radius:8px;font-size:1.1rem;margin-top:30px;cursor:pointer;font-weight:bold;}.demo-notice{background:#333;color:#ff6b35;padding:15px;border-radius:8px;margin-top:20px;text-align:center;border:1px solid #ff6b35;}</style></head>
    <body><div class="container"><h2>🎯 Demo Payment</h2><div class="demo-notice"><strong>Testing Mode:</strong> Creates a demo enrollment and redirects to dashboard.</div>
    <form method="post"><input type="hidden" name="csrf_token" value="{{csrf_token}}"><label for="plan">Select Plan</label><select name="plan" id="plan"><option value="course">Course Access (₦100,000)</option><option value="online">Online Mentorship (₦400,000)</option><option value="vip">VIP Physical Class (₦2,000,000)</option></select>
    <label for="name">Full Name</label><input type="text" name="name" id="name" required><label for="email">Email</label><input type="email" name="email" id="email" required><label for="phone">Phone</label><input type="text" name="phone" id="phone" required>
    <button class="btn" type="submit">🚀 Access Student Dashboard</button></form></div></body></html>
    ''', csrf_token=csrf_token)