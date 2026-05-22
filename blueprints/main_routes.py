from flask import Blueprint, render_template, render_template_string, redirect, url_for, session, jsonify, request
import os
from datetime import datetime
import json
import sqlite3
from werkzeug.security import check_password_hash

# Import utilities
from utils.db_utils import get_db_connection, return_db_connection
from utils.logging_utils import app_logger, db_logger, security_logger, payment_logger, log_info, log_error, log_warning
# Import security utilities
from utils.security_utils import validate_email, validate_phone, sanitize_input, get_env_variable
# Import CSRF protection
from utils.security_middleware import generate_csrf_token, csrf_protect, validate_csrf_token
from utils.rate_limiter import rate_limit

main_bp = Blueprint('main_bp', __name__)

@main_bp.route('/api/contact', methods=['POST'])
@rate_limit('api')
def handle_contact_form():
    """Handle contact form submissions."""
    data = request.get_json()
    if not data or not data.get('name') or not data.get('email') or not data.get('message'):
        return jsonify({'success': False, 'error': 'All fields are required.'}), 400

    name = sanitize_input(data['name'])
    email = sanitize_input(data['email'])
    message = sanitize_input(data['message'])

    if not validate_email(email):
        return jsonify({'success': False, 'error': 'Invalid email address.'}), 400

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO contact_messages (name, email, message) VALUES (?, ?, ?)',
                       (name, email, message))
        conn.commit()
        log_info(app_logger, "Contact message received", name=name, email=email)
        return jsonify({'success': True, 'message': 'Thank you! Your message has been sent.'})
    except Exception as e:
        log_error(app_logger, "Contact form error", error=str(e))
        return jsonify({'success': False, 'error': 'An internal error occurred. Please try again later.'}), 500
    finally:
        if conn:
            return_db_connection(conn)

@main_bp.route('/')
def home():
    """Serve the main landing page"""
    conn = None
    try:
        conn = get_db_connection()
        # Get latest 3 blogs for the landing page section
        latest_blogs = conn.execute('SELECT * FROM blogs ORDER BY created_at DESC LIMIT 3').fetchall()
        return render_template('index.html', latest_blogs=latest_blogs)
    except Exception as e:
        log_error(app_logger, "Failed to load home page", error=str(e))
        return render_template('index.html', latest_blogs=[])
    finally:
        if conn:
            return_db_connection(conn)

@main_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

@main_bp.route('/student/login', methods=['GET', 'POST'])
@csrf_protect
def student_login():
    """Render student login page and handle actual authentication."""
    csrf_token = generate_csrf_token()
    message = ''
    if request.method == 'POST':
        if not validate_csrf_token():
            message = 'Invalid request.'
        else:
            email = request.form.get('email')
            password = request.form.get('password')

            if not email or not validate_email(email):
                message = 'Valid email is required.'
            elif not password:
                message = 'Password is required.'
            else:
                conn = None
                try:
                    conn = get_db_connection()
                    # Check if user exists and is a student
                    # Note: We also allow teachers to login here but redirect appropriately if needed
                    # However, for now, we follow the student flow
                    user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()

                    if not user or not check_password_hash(user['password_hash'], password):
                        message = 'Invalid credentials.'
                        log_warning(security_logger, "Student login failed - invalid credentials", email=email)
                    else:
                        # Check if user has a completed enrollment
                        enrollment = conn.execute("SELECT e.*, u.email, u.full_name FROM enrollments e JOIN users u ON e.user_id = u.id WHERE e.user_id = ? AND e.payment_status = 'completed' LIMIT 1", (user['id'],)).fetchone()

                        if not enrollment:
                            message = 'No active enrollment found. Please complete your payment first.'
                        else:
                            # Set session
                            session['enrollment'] = dict(enrollment)
                            log_info(security_logger, "Student login successful", user_id=user['id'], email=email)
                            return redirect(url_for('main_bp.dashboard'))
                except Exception as e:
                    log_error(app_logger, "Student login failed with exception", error=str(e))
                    message = 'Login failed. Please try again.'
                finally:
                    if conn:
                        return_db_connection(conn)

    return render_template('student_login.html', message=message, csrf_token=csrf_token)

@main_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main_bp.home'))

@main_bp.route('/dashboard')
def dashboard():
    if not session.get('enrollment'):
        return redirect(url_for('main_bp.student_login'))
    enrollment = session['enrollment']
    user_id = enrollment['user_id']
    conn = None
    try:
        conn = get_db_connection()
        announcements = conn.execute("SELECT * FROM announcements WHERE is_active = 1 AND (expires_at IS NULL OR expires_at > datetime('now')) AND (target_audience = 'all' OR target_audience = ?) ORDER BY priority DESC, created_at DESC", (enrollment['course_type'],)).fetchall()
        course_info = conn.execute('SELECT id FROM courses WHERE name = ?', (enrollment['course_type'],)).fetchone()
        lessons, completed_ids, progress_percent = [], set(), 0
        if course_info:
            target_course_id = course_info['id']
            lessons = conn.execute("SELECT l.id, m.name as module_name, l.lesson FROM lessons l JOIN modules m ON l.module_id = m.id WHERE l.course_id = ? ORDER BY m.order_index, l.order_index", (target_course_id,)).fetchall()
            completed_data = conn.execute("SELECT lesson_id FROM course_progress WHERE user_id = ? AND course_id = ? AND completed = 1", (user_id, target_course_id)).fetchall()
            completed_ids = set([str(row['lesson_id']) for row in completed_data])
            progress_percent = int((len(completed_ids) / len(lessons)) * 100) if lessons else 0
        return render_template('student_dashboard.html', enrollment=enrollment, announcements=announcements, lessons=lessons, completed_ids=completed_ids, progress_percent=progress_percent)
    except Exception as e:
        log_error(app_logger, "Dashboard error", error=str(e))
        return "Error loading dashboard", 500
    finally:
        if conn: return_db_connection(conn)

@main_bp.route('/pay', methods=['GET', 'POST'])
def pay():
    plans = { 'course': {'name': 'Course Access', 'price': 100000}, 'online': {'name': 'Online Mentorship', 'price': 400000}, 'vip': {'name': 'VIP Physical Class', 'price': 2000000} }
    selected_plan_key = request.args.get('plan', 'course')
    plan = plans.get(selected_plan_key, plans['course'])
    message = ''
    if request.method == 'POST':
        name = sanitize_input(request.form.get('name'))
        email = request.form.get('email')
        phone = request.form.get('phone')
        plan_key_from_form = request.form.get('plan')

        if not email or not validate_email(email):
            message = 'Valid email is required.'
        elif not phone or not validate_phone(phone):
            message = 'Valid phone number is required.'
        elif not name:
            message = 'Name is required.'
        else:
            plan_for_payment = plans.get(plan_key_from_form, plans['course'])
            price = plan_for_payment['price']

            conn = None
            try:
                conn = get_db_connection()
                user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
                user_id = 0
                if not user:
                    from werkzeug.security import generate_password_hash
                    password_hash = generate_password_hash(os.urandom(16).hex())
                    cursor = conn.cursor()
                    cursor.execute('INSERT INTO users (email, password_hash, full_name, phone) VALUES (?, ?, ?, ?)',
                                   (email, password_hash, name, phone))
                    user_id = cursor.lastrowid
                    conn.commit()
                else:
                    user_id = user['id']

                # Payment Initiation (Integrated Flow)
                payment_reference = f"VU_{user_id}_{int(datetime.now().timestamp())}"

                cursor = conn.cursor()
                cursor.execute('INSERT INTO enrollments (user_id, course_type, price, payment_method, payment_reference, payment_status) VALUES (?, ?, ?, ?, ?, ?)',
                               (user_id, plan_key_from_form, price, 'card', payment_reference, 'completed'))
                conn.commit()

                enrollment = conn.execute("SELECT e.*, u.email, u.full_name FROM enrollments e JOIN users u ON e.user_id = u.id WHERE e.payment_reference = ?", (payment_reference,)).fetchone()
                session['enrollment'] = dict(enrollment)
                log_info(payment_logger, "Successful enrollment", user_id=user_id, plan=plan_key_from_form)

                return redirect(url_for('main_bp.dashboard'))

            except Exception as e:
                log_error(app_logger, "Payment processing failed", error=str(e))
                message = 'Payment processing failed. Please try again.'
            finally:
                if conn:
                    return_db_connection(conn)

    return render_template('payment.html',
                           plans=plans,
                           selected_plan_key=selected_plan_key,
                           message=message)

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
            return render_template('demo_payment.html',
                                   csrf_token=csrf_token,
                                   error="Invalid email format. Please try again.")
        
        # Validate phone format
        if not validate_phone(phone):
            csrf_token = generate_csrf_token()
            return render_template('demo_payment.html',
                                   csrf_token=csrf_token,
                                   error="Invalid phone number format. Please try again.")
        
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
        return redirect(url_for('main_bp.dashboard'))
    
    csrf_token = generate_csrf_token()
    return render_template('demo_payment.html', csrf_token=csrf_token)