from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session
from flask_cors import CORS
import os
import json
import sqlite3
from datetime import datetime
import hashlib
import secrets
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import markdown
import re

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Import security utilities
from utils.security_utils import hash_password, verify_password, validate_email, validate_phone, sanitize_input, get_env_variable
# Import security middleware
from utils.security_middleware import SecurityMiddleware

# Import utilities
from utils.db_utils import db_manager, get_db_connection, return_db_connection, get_db_cursor
from utils.logging_utils import app_logger, db_logger, security_logger, payment_logger, log_info, log_error, log_warning
from utils.rate_limiter import rate_limit

# Import and register blueprints
from blueprints.main_routes import main_bp
from blueprints.teacher_auth_routes import teacher_auth_bp
from blueprints.teacher_courses_routes import teacher_courses_bp
from blueprints.teacher_api_routes import teacher_api_bp

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize security middleware
security_middleware = SecurityMiddleware(app)

app.register_blueprint(main_bp)
app.register_blueprint(teacher_auth_bp)
app.register_blueprint(teacher_courses_bp)
app.register_blueprint(teacher_api_bp)

# Configuration
app.config['SECRET_KEY'] = get_env_variable('SECRET_KEY', 'vibes-university-secret-key')

# Payment Gateway Configuration
PAYSTACK_SECRET_KEY = get_env_variable('PAYSTACK_SECRET_KEY', 'sk_test_your_paystack_secret_key')
FLUTTERWAVE_SECRET_KEY = get_env_variable('FLUTTERWAVE_SECRET_KEY', 'FLWSECK_TEST-your_flutterwave_secret_key')

app.secret_key = app.config['SECRET_KEY']

# Admin config (for demo, use env var or DB in production)
ADMIN_PASSWORD = get_env_variable('ADMIN_PASSWORD', 'vibesadmin123')
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'courses')
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv', 'pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'txt', 'jpg', 'jpeg', 'png', 'gif', 'svg', 'zip', 'rar', '7z', 'mp3', 'wav', 'aac', 'ogg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_icon(filename):
    """Get appropriate icon for file type"""
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    icons = {
        'mp4': '🎥', 'avi': '🎥', 'mov': '🎥', 'wmv': '🎥', 'flv': '🎥', 'webm': '🎥', 'mkv': '🎥',
        'pdf': '📄', 'doc': '📝', 'docx': '📝', 'ppt': '📊', 'pptx': '📊', 'xls': '📊', 'xlsx': '📊', 'txt': '📄',
        'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️', 'gif': '🖼️', 'svg': '🖼️',
        'zip': '📦', 'rar': '📦', '7z': '📦',
        'mp3': '🎵', 'wav': '🎵', 'aac': '🎵', 'ogg': '🎵'
    }
    return icons.get(ext, '📎')

def init_db():
    """Initialize the database with required tables"""
    db_manager.initialize_database()

def get_db_connection():
    return db_manager.get_connection()

@app.route('/api/register', methods=['POST'])
@rate_limit('auth')
def register():
    try:
        data = request.get_json()
        required_fields = ['email', 'password', 'full_name', 'phone']
        for field in required_fields:
            if not data.get(field):
                log_warning(app_logger, "Registration failed - missing field", missing_field=field)
                return jsonify({'error': f'{field} is required'}), 400
        
        # Validate email format
        if not validate_email(data['email']):
            log_warning(app_logger, "Registration failed - invalid email format", email=data['email'])
            return jsonify({'error': 'Invalid email format'}), 400
        
        # Validate phone format
        if not validate_phone(data['phone']):
            log_warning(app_logger, "Registration failed - invalid phone format", phone=data['phone'])
            return jsonify({'error': 'Invalid phone number format'}), 400
        
        # Sanitize inputs
        full_name = sanitize_input(data['full_name'])
        
        conn = None
        try:
            conn = get_db_connection()
            existing_user = conn.execute('SELECT id FROM users WHERE email = ?', (data['email'],)).fetchone()
            if existing_user:
                log_info(app_logger, "Registration failed - user already exists", email=data['email'])
                return jsonify({'error': 'User already exists'}), 400
            
            password_hash = generate_password_hash(data['password'])
            cursor = conn.cursor()
            cursor.execute('INSERT INTO users (email, password_hash, full_name, phone) VALUES (?, ?, ?, ?)',
                           (data['email'], password_hash, full_name, data['phone']))
            user_id = cursor.lastrowid
            conn.commit()
            log_info(app_logger, "User registered successfully", user_id=user_id, email=data['email'])
            return jsonify({'success': True, 'message': 'User registered successfully', 'user_id': user_id})
        except Exception as e:
            log_error(app_logger, "Registration failed with exception", error=str(e))
            return jsonify({'error': str(e)}), 500
        finally:
            if conn:
                return_db_connection(conn)
    except Exception as e:
        log_error(app_logger, "Registration failed with exception", error=str(e))
        return jsonify({'error': str(e)}), 500

@app.route('/api/login', methods=['POST'])
@rate_limit('auth')
def login():
    try:
        data = request.get_json()
        if not data.get('email') or not data.get('password'):
            log_warning(app_logger, "Login failed - missing credentials")
            return jsonify({'error': 'Email and password are required'}), 400
        
        # Validate email format
        if not validate_email(data['email']):
            log_warning(app_logger, "Login failed - invalid email format", email=data['email'])
            return jsonify({'error': 'Invalid email format'}), 400
        
        conn = None
        try:
            conn = get_db_connection()
            user = conn.execute('SELECT * FROM users WHERE email = ?', (data['email'],)).fetchone()
            
            if not user or not check_password_hash(user['password_hash'], data['password']):
                log_info(app_logger, "Login failed - invalid credentials", email=data.get('email'))
                return jsonify({'error': 'Invalid credentials'}), 401
        except Exception as e:
            log_error(app_logger, "Login failed with exception", error=str(e))
            return jsonify({'error': str(e)}), 500
        finally:
            if conn:
                return_db_connection(conn)
        
        log_info(app_logger, "User logged in successfully", user_id=user['id'], email=user['email'])
        return jsonify({'success': True, 'user': {'id': user['id'], 'email': user['email'], 'full_name': user['full_name'], 'phone': user['phone']}})
    except Exception as e:
        log_error(app_logger, "Login failed with exception", error=str(e))
        return jsonify({'error': str(e)}), 500

@app.route('/api/initiate-payment', methods=['POST'])
@rate_limit('api')
def initiate_payment():
    try:
        data = request.get_json()
        required_fields = ['user_id', 'course_type', 'price', 'payment_method']
        for field in required_fields:
            if not data.get(field):
                log_warning(payment_logger, "Payment initiation failed - missing field", missing_field=field)
                return jsonify({'error': f'{field} is required'}), 400
        
        payment_reference = f"VU_{data['user_id']}_{int(datetime.now().timestamp())}"
        
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO enrollments (user_id, course_type, price, payment_method, payment_reference) VALUES (?, ?, ?, ?, ?)',
                           (data['user_id'], data['course_type'], data['price'], data['payment_method'], payment_reference))
            enrollment_id = cursor.lastrowid
            conn.commit()
        except Exception as e:
            log_error(payment_logger, "Payment initiation failed with exception", error=str(e))
            return jsonify({'error': str(e)}), 500
        finally:
            if conn:
                return_db_connection(conn)
        
        log_info(payment_logger, "Enrollment created", enrollment_id=enrollment_id, user_id=data['user_id'], course_type=data['course_type'], price=data['price'])
        
        payment_url = ""
        if data['payment_method'] == 'card':
            payment_url = initiate_paystack_payment(data, payment_reference)
        elif data['payment_method'] == 'bank':
            payment_url = initiate_flutterwave_payment(data, payment_reference)
        elif data['payment_method'] == 'crypto':
            payment_url = initiate_crypto_payment(data, payment_reference)
        else:
            log_warning(payment_logger, "Payment initiation failed - invalid payment method", payment_method=data['payment_method'])
            return jsonify({'error': 'Invalid payment method'}), 400
        
        log_info(payment_logger, "Payment initiated successfully", enrollment_id=enrollment_id, payment_reference=payment_reference, payment_method=data['payment_method'])
        return jsonify({'success': True, 'payment_reference': payment_reference, 'payment_url': payment_url, 'enrollment_id': enrollment_id})
    except Exception as e:
        log_error(payment_logger, "Payment initiation failed with exception", error=str(e))
        return jsonify({'error': str(e)}), 500

def initiate_paystack_payment(data, reference):
    try:
        return f"https://checkout.paystack.com/demo?reference={reference}"
    except Exception as e:
        print(f"Paystack error: {e}")
        return f"https://checkout.paystack.com/demo?reference={reference}"

def initiate_flutterwave_payment(data, reference):
    try:
        return f"https://checkout.flutterwave.com/demo?reference={reference}"
    except Exception as e:
        print(f"Flutterwave error: {e}")
        return f"https://checkout.flutterwave.com/demo?reference={reference}"

def initiate_crypto_payment(data, reference):
    try:
        return f"https://vibesuniversity.com/crypto-payment?reference={reference}"
    except Exception as e:
        print(f"Crypto payment error: {e}")
        return f"https://vibesuniversity.com/crypto-payment?reference={reference}"

@app.route('/api/verify-payment', methods=['POST'])
@rate_limit('api')
def verify_payment():
    try:
        data = request.get_json()
        reference = data.get('reference')
        if not reference: 
            log_warning(payment_logger, "Payment verification failed - missing reference")
            return jsonify({'error': 'Payment reference is required'}), 400
        
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE enrollments SET payment_status = 'completed' WHERE payment_reference = ?", (reference,))
            enrollment = conn.execute("SELECT e.*, u.email, u.full_name FROM enrollments e JOIN users u ON e.user_id = u.id WHERE e.payment_reference = ?", (reference,)).fetchone()
            conn.commit()
        except Exception as e:
            log_error(payment_logger, "Payment verification failed with exception", error=str(e))
            return jsonify({'error': str(e)}), 500
        finally:
            if conn:
                return_db_connection(conn)
        
        if enrollment:
            send_course_access(enrollment)
            log_info(payment_logger, "Payment verified successfully", enrollment_id=enrollment['id'], user_id=enrollment['user_id'], course_type=enrollment['course_type'])
            return jsonify({'success': True, 'message': 'Payment verified successfully', 'enrollment': dict(enrollment)})
        else:
            log_warning(payment_logger, "Payment verification failed - enrollment not found", reference=reference)
            return jsonify({'error': 'Enrollment not found'}), 404
    except Exception as e:
        log_error(payment_logger, "Payment verification failed with exception", error=str(e))
        return jsonify({'error': str(e)}), 500

def send_course_access(enrollment):
    print(f"Sending course access to {enrollment['email']} for {enrollment['course_type']}")
    return True

@app.route('/api/courses', methods=['GET'])
def get_courses():
    conn = None
    try:
        conn = get_db_connection()
        courses_data = conn.execute("SELECT id, name, description, course_settings FROM courses ORDER BY created_at DESC").fetchall()
        
        output_courses = []
        for course_row in courses_data:
            course_dict = dict(course_row)
            try:
                course_dict['course_settings'] = json.loads(course_row['course_settings']) if course_row['course_settings'] else {}
            except:
                course_dict['course_settings'] = course_row['course_settings'] if course_row['course_settings'] else {}
            output_courses.append(course_dict)
        return jsonify({'courses': output_courses})
    except Exception as e:
        log_error(db_logger, "Failed to retrieve courses", error=str(e))
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            return_db_connection(conn)


@app.route('/api/user-progress/<int:user_id>', methods=['GET'])
def get_user_progress(user_id):
    # Check if user is authenticated
    enrollment = session.get('enrollment')
    if not enrollment:
        log_warning(security_logger, "Unauthorized access attempt to user progress", user_id=user_id)
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Check if user is requesting their own data
    if enrollment.get('user_id') != user_id:
        log_warning(security_logger, "Unauthorized access attempt to another user's progress", requester_id=enrollment.get('user_id'), target_id=user_id)
        return jsonify({'error': 'Not authorized to access this data'}), 403
    
    conn = None
    try:
        conn = get_db_connection()
        enrollments = conn.execute("SELECT * FROM enrollments WHERE user_id = ? AND payment_status = 'completed'", (user_id,)).fetchall()
        progress = conn.execute("SELECT * FROM course_progress WHERE user_id = ?", (user_id,)).fetchall()
        log_info(app_logger, "User progress retrieved successfully", user_id=user_id)
        return jsonify({'enrollments': [dict(row) for row in enrollments], 'progress': [dict(row) for row in progress]})
    except Exception as e:
        log_error(app_logger, "Failed to retrieve user progress", user_id=user_id, error=str(e))
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/update-progress', methods=['POST'])
def update_progress():
    try:
        data = request.get_json()
        required = ['user_id', 'course_id', 'lesson_id']
        for field in required:
            if not data.get(field):
                log_warning(app_logger, "Update progress failed - missing field", missing_field=field)
                return jsonify({'error': f'{field} is required'}), 400
        
        # Validate that IDs are integers
        try:
            user_id = int(data['user_id'])
            course_id = int(data['course_id'])
            lesson_id = int(data['lesson_id'])
        except (ValueError, TypeError):
            log_warning(app_logger, "Update progress failed - invalid ID format")
            return jsonify({'error': 'Invalid ID format'}), 400
        
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            existing = conn.execute("SELECT id FROM course_progress WHERE user_id = ? AND course_id = ? AND lesson_id = ?",
                                    (user_id, course_id, lesson_id)).fetchone()
            if existing:
                cursor.execute("UPDATE course_progress SET completed = 1, completed_at = CURRENT_TIMESTAMP WHERE id = ?", (existing['id'],))
            else:
                cursor.execute("INSERT INTO course_progress (user_id, course_id, lesson_id, completed, completed_at) VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)",
                               (user_id, course_id, lesson_id))
            conn.commit()
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            if conn:
                return_db_connection(conn)
        log_info(app_logger, "Progress updated successfully", user_id=user_id, course_id=course_id, lesson_id=lesson_id)
        return jsonify({'success': True, 'message': 'Progress updated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    conn = None
    try:
        conn = get_db_connection()
        user_count = conn.execute('SELECT COUNT(*) as count FROM users').fetchone()['count']
        enrollment_count = conn.execute("SELECT COUNT(*) as count FROM enrollments WHERE payment_status = 'completed'").fetchone()['count']
        total_revenue = conn.execute("SELECT SUM(price) as total FROM enrollments WHERE payment_status = 'completed'").fetchone()['total'] or 0
        return jsonify({'users': user_count, 'enrollments': enrollment_count, 'revenue': total_revenue, 'success_rate': '97%', 'average_income': '₦1,200,000'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/testimonials', methods=['GET'])
def get_testimonials():
    testimonials = [ {'name': 'Chioma Okafor', 'age': 24, 'location': 'Lagos', 'income': '₦800,000/month', 'story': 'I was broke 3 months ago...', 'course': 'AI Marketing Mastery', 'timeframe': '3 months'}, {'name': 'Emeka Nwankwo', 'age': 22, 'location': 'Abuja', 'income': '₦2,500,000/month', 'story': 'Quit university...', 'course': 'AI Coding & Development', 'timeframe': '4 months'}, {'name': 'Fatima Abdullahi', 'age': 26, 'location': 'Kano', 'income': '₦1,200,000/month', 'story': 'Financial freedom at 26...', 'course': 'AI Content Creation', 'timeframe': '5 months'}, {'name': 'David Ogundimu', 'age': 23, 'location': 'Port Harcourt', 'income': '₦3,000,000/month', 'story': 'From ₦0 to ₦3M monthly...', 'course': 'AI E-commerce Automation', 'timeframe': '4 months'} ]
    return jsonify({'testimonials': testimonials})

@app.route('/pay', methods=['GET', 'POST'])
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
        
        # Validate inputs
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
                    password_hash = generate_password_hash(secrets.token_hex(8))
                    cursor = conn.cursor()
                    cursor.execute('INSERT INTO users (email, password_hash, full_name, phone) VALUES (?, ?, ?, ?)',
                                   (email, password_hash, name, phone))
                    user_id = cursor.lastrowid
                    conn.commit()
                    log_info(app_logger, "New user created via payment", user_id=user_id, email=email)
                else:
                    user_id = user['id']
                    log_info(app_logger, "Existing user accessed via payment", user_id=user_id, email=email)
            except Exception as e:
                log_error(app_logger, "Payment processing failed", error=str(e))
                message = 'Payment processing failed. Please try again.'
            finally:
                if conn:
                    return_db_connection(conn)
            
            payment_data = { 'user_id': user_id, 'course_type': plan_key_from_form, 'price': price, 'payment_method': 'card', 'email': email }
            
            with app.test_request_context():
                with app.test_client() as client:
                    resp = client.post(url_for('initiate_payment'), json=payment_data)
                    resp_json = resp.get_json()
            
            if resp_json and resp_json.get('success'):
                session['pending_reference'] = resp_json['payment_reference']
                session['user_id'] = user_id
                return redirect(resp_json['payment_url'])
            else:
                message = resp_json.get('error', 'Payment initiation failed. Please try again.')
    
    return render_template_string('''
    <html><head><title>Vibes University - Payment</title>
    <style>body{font-family:Arial,sans-serif;background:#111;color:#fff;}.container{max-width:500px;margin:60px auto;background:#222;padding:40px;border-radius:15px;box-shadow:0 8px 32px #0008;}h2{color:#ff6b35;}label{display:block;margin-top:20px;}input,select{width:100%;padding:10px;margin-top:5px;border-radius:8px;border:none;background:#333;color:#fff;}.btn{background:linear-gradient(45deg,#ff6b35,#ff8c42);color:#fff;border:none;padding:15px 0;width:100%;border-radius:8px;font-size:1.1rem;margin-top:30px;cursor:pointer;font-weight:bold;}.msg{color:#0f0;margin-top:20px;text-align:center;}.demo-notice{background:#333;color:#ff6b35;padding:15px;border-radius:8px;margin-top:20px;text-align:center;border:1px solid #ff6b35;}</style></head>
    <body><div class="container"><h2>Secure Your Spot</h2><form method="post">
    <label for="plan">Select Plan</label><select name="plan" id="plan">
    {% for key, p_item in plans.items() %}<option value="{{key}}" {% if key == selected_plan_key %}selected{% endif %}>{{p_item.name}} (₦{{p_item.price}})</option>{% endfor %}
    </select><label for="name">Full Name</label><input type="text" name="name" id="name" required>
    <label for="email">Email</label><input type="email" name="email" id="email" required>
    <label for="phone">Phone</label><input type="text" name="phone" id="phone" required>
    <button class="btn" type="submit">Proceed to Payment</button></form>
    {% if message %}<div class="msg" style="color: #f44336; background: rgba(244,67,54,0.1);">{{message}}</div>{% endif %}
    <div class="demo-notice"><strong>Demo Mode:</strong> This is a demo payment system.</div>
    </div></body></html>
    ''', plans=plans, selected_plan_key=selected_plan_key, message=message)


@app.route('/payment/callback')
def payment_callback():
    reference = request.args.get('reference') or session.get('pending_reference')
    if not reference: 
        log_warning(payment_logger, "Payment callback failed - missing reference")
        return "Missing payment reference.", 400
    
    # Sanitize reference to prevent injection
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', reference):
        log_warning(payment_logger, "Payment callback failed - invalid reference format")
        return "Invalid payment reference format.", 400

    with app.test_request_context():
        with app.test_client() as client:
            resp = client.post(url_for('verify_payment'), json={'reference': reference})
            resp_json = resp.get_json()
    if resp_json and resp_json.get('success'):
        session['enrollment'] = resp_json['enrollment']
        log_info(payment_logger, "Payment callback successful", reference=reference)
        return redirect(url_for('dashboard'))
    else:
        error_msg = resp_json.get('error', 'Unknown error')
        log_warning(payment_logger, "Payment callback failed", reference=reference, error=error_msg)
        return f"Payment verification failed: {error_msg}", 400

@app.route('/dashboard')
def dashboard():
    if not session.get('enrollment'):
        return redirect(url_for('student_login'))
    enrollment = session['enrollment']
    user_id = enrollment['user_id']
    conn = None
    try:
        conn = get_db_connection()

        announcements = conn.execute("SELECT * FROM announcements WHERE is_active = 1 AND (expires_at IS NULL OR expires_at > datetime('now')) AND (target_audience = 'all' OR target_audience = ?) ORDER BY priority DESC, created_at DESC", (enrollment['course_type'],)).fetchall()

        target_course_name = enrollment['course_type']
        course_info = conn.execute('SELECT id FROM courses WHERE name = ?', (target_course_name,)).fetchone()

        detailed_lessons_for_template = []
        total_lessons = 0
        completed_ids = set()
        progress_percent = 0

        if course_info:
            target_course_id = course_info['id']
            lessons_data_raw = conn.execute("SELECT l.id, m.name as module_name, l.lesson, COALESCE(l.order_index, 1) as order_index FROM lessons l JOIN modules m ON l.module_id = m.id WHERE l.course_id = ? ORDER BY m.order_index, l.order_index", (target_course_id,)).fetchall()
            detailed_lessons_for_template = [dict(l) for l in lessons_data_raw]
            total_lessons = len(detailed_lessons_for_template)

            if total_lessons > 0:
                completed_data = conn.execute("SELECT lesson_id FROM course_progress WHERE user_id = ? AND course_id = ? AND completed = 1", (user_id, target_course_id)).fetchall()
                completed_ids = set([str(row['lesson_id']) for row in completed_data])
                completed_count = len(completed_ids)
                progress_percent = int((completed_count / total_lessons) * 100) if total_lessons else 0
    except Exception as e:
        log_error(app_logger, "Failed to retrieve dashboard data", error=str(e))
        return "Error loading dashboard", 500
    finally:
        if conn:
            return_db_connection(conn)

    return render_template_string('''
    <html><head><title>Student Dashboard</title>
    <style>body{font-family:Arial,sans-serif;background:#111;color:#fff;margin:0;padding:20px;}.header{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;}.header h1{color:#ff6b35;margin:0;}.announcements{background:#222;border-left:5px solid #ff6b35;padding:20px;border-radius:10px;margin-bottom:30px;}.announcement-title{color:#ff6b35;font-weight:bold;font-size:18px;}.announcement-meta{color:#ccc;font-size:12px;margin-bottom:8px;}.announcement-message{background:#333;padding:12px;border-radius:6px;margin-bottom:10px;}.progress-section{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;}.progress-bar-bg{background:#333;border-radius:8px;height:30px;width:100%;margin-bottom:10px;}.progress-bar{background:#4CAF50;height:30px;border-radius:8px;text-align:center;color:#fff;font-weight:bold;line-height:30px;}.lesson-list{margin-top:20px;}.lesson-item{padding:10px;border-bottom:1px solid #444;display:flex;align-items:center;}.lesson-completed{color:#4CAF50;margin-right:10px;}.lesson-pending{color:#ff9800;margin-right:10px;}</style></head>
    <body><div class="header"><h1>🎓 Welcome, {{enrollment['full_name']}}</h1><p>Course: <b>{{enrollment['course_type']|title}}</b></p></div>
    {% if announcements %}<div class="announcements"><h2>📢 Announcements</h2>
    {% for a in announcements %}<div class="announcement-title">{{a['title']}}</div><div class="announcement-meta">{{a['created_at']}} | {{a['priority']|title}}</div><div class="announcement-message">{{a['message']}}</div>{% endfor %}
    </div>{% endif %}<div class="progress-section"><h2>📈 Course Progress</h2>
    <div class="progress-bar-bg"><div class="progress-bar" style="width:{{progress_percent}}%;">{{progress_percent}}%</div></div>
    <div class="lesson-list">
    {% for lesson_item in lessons %}
        <div class="lesson-item">
        {% if lesson_item['id']|string in completed_ids %}<span class="lesson-completed">✔️</span>{% else %}<span class="lesson-pending">⏳</span>{% endif %}
        {{lesson_item['module_name']}} - {{lesson_item['lesson']}}
        <a href="{{ url_for('view_lesson', lesson_id=lesson_item.id) }}" style="margin-left:auto; color:#ff6b35; text-decoration:none;">View Lesson</a>
        </div>
    {% endfor %}</div></div></body></html>
    ''', enrollment=enrollment, announcements=announcements, lessons=detailed_lessons_for_template, completed_ids=completed_ids, progress_percent=progress_percent)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    csrf_token = generate_csrf_token()
    message = ''
    if request.method == 'POST':
        # Validate CSRF token
        if not validate_csrf_token():
            message = 'Invalid request.'
        else:
            password = request.form.get('password')
            if password == ADMIN_PASSWORD:
                session['admin_logged_in'] = True
                log_info(security_logger, "Admin login successful")
                return redirect(url_for('admin_dashboard'))
            else:
                message = 'Invalid password.'
                log_warning(security_logger, "Admin login failed - invalid password")
    return render_template_string('''
    <html><head><title>Admin Login</title></head><body style="background:#111;color:#fff;font-family:Arial,sans-serif;text-align:center;padding:60px;"><h2>Admin Login</h2><form method="post"><input type="hidden" name="csrf_token" value="{{csrf_token}}"><input type="password" name="password" placeholder="Admin Password" required style="padding:10px;border-radius:8px;"><button type="submit" style="padding:10px 20px;border-radius:8px;background:#ff6b35;color:#fff;font-weight:bold;">Login</button></form>{% if message %}<div style="color:#f00;margin-top:20px;">{{message}}</div>{% endif %}</body></html>
    ''', message=message, csrf_token=csrf_token)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    message = request.args.get('message', '')
    conn = None
    try:
        conn = get_db_connection()
        total_users = conn.execute('SELECT COUNT(*) as count FROM users').fetchone()['count']
        total_enrollments = conn.execute('SELECT COUNT(*) as count FROM enrollments').fetchone()['count']
        completed_payments = conn.execute("SELECT COUNT(*) as count FROM enrollments WHERE payment_status = 'completed'").fetchone()['count']
        total_revenue = conn.execute("SELECT SUM(price) as total FROM enrollments WHERE payment_status = 'completed'").fetchone()['total'] or 0
        total_lessons_stat = conn.execute('SELECT COUNT(*) as count FROM lessons').fetchone()['count']
        
        recent_enrollments = conn.execute("SELECT e.*, u.full_name, u.email FROM enrollments e JOIN users u ON e.user_id = u.id ORDER BY e.enrolled_at DESC LIMIT 10").fetchall()
        course_stats = conn.execute("SELECT course_type, COUNT(*) as count, SUM(price) as revenue FROM enrollments WHERE payment_status = 'completed' GROUP BY course_type").fetchall()
    except Exception as e:
        log_error(db_logger, "Failed to retrieve admin dashboard data", error=str(e))
        return "Error loading dashboard", 500
    finally:
        if conn:
            return_db_connection(conn)
    
    return render_template_string('''
    <html><head><title>Admin Dashboard - Vibes University</title>
    <style>body{font-family:Arial,sans-serif;background:#111;color:#fff;margin:0;padding:20px;}.header{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;display:flex;justify-content:space-between;align-items:center;}.header h1{color:#ff6b35;margin:0;}.logout-btn{background:#ff6b35;color:#fff;padding:10px 20px;border:none;border-radius:8px;text-decoration:none;font-weight:bold;}.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:20px;margin-bottom:30px;}.stat-card{background:#222;padding:20px;border-radius:10px;text-align:center;border-left:4px solid #ff6b35;}.stat-number{font-size:2rem;font-weight:bold;color:#ff6b35;}.stat-label{color:#ccc;margin-top:5px;}.section{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;}.section h3{color:#ff6b35;margin-top:0;}.table{width:100%;border-collapse:collapse;margin-top:15px;}.table th,.table td{padding:12px;text-align:left;border-bottom:1px solid #444;}.table th{background:#333;color:#ff6b35;}.table tr:hover{background:#333;}.success-msg{background:#4CAF50;color:#fff;padding:15px;border-radius:8px;margin-bottom:20px;}.course-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:15px;}.course-stat{background:#333;padding:15px;border-radius:8px;text-align:center;}</style></head>
    <body><div class="header"><h1>🎓 Vibes University Admin Dashboard</h1>
    <div style="display:flex;gap:10px;"><a href="{{url_for('admin_users')}}" style="background:#333;color:#fff;padding:8px 15px;border-radius:5px;text-decoration:none;font-size:14px;">👥 Users</a><a href="{{url_for('admin_analytics')}}" style="background:#333;color:#fff;padding:8px 15px;border-radius:5px;text-decoration:none;font-size:14px;">📊 Analytics</a><a href="{{url_for('admin_settings')}}" style="background:#333;color:#fff;padding:8px 15px;border-radius:5px;text-decoration:none;font-size:14px;">⚙️ Settings</a><a href="{{url_for('admin_announcements')}}" style="background:#ff6b35;color:#fff;padding:8px 15px;border-radius:5px;text-decoration:none;font-size:14px;">📢 Announcements</a><a href="{{url_for('admin_course_studio_page')}}" style="background:#4CAF50;color:#fff;padding:8px 15px;border-radius:5px;text-decoration:none;font-size:14px;">🚀 Course Studio</a><a href="{{url_for('admin_preview_course', course_type='course')}}" style="background:#2196F3;color:#fff;padding:8px 15px;border-radius:5px;text-decoration:none;font-size:14px;">👁️ Preview Course (Legacy)</a><a href="/demo-payment" style="background:#4CAF50;color:#fff;padding:8px 15px;border-radius:5px;text-decoration:none;font-size:14px;">🎯 Test Dashboard</a><a href="{{url_for('admin_logout')}}" class="logout-btn">Logout</a></div></div>
    {% if message %}<div class="success-msg">{{message}}</div>{% endif %}
    <div class="stats-grid"><div class="stat-card"><div class="stat-number">{{total_users}}</div><div class="stat-label">Total Users</div></div><div class="stat-card"><div class="stat-number">{{total_enrollments}}</div><div class="stat-label">Total Enrollments</div></div><div class="stat-card"><div class="stat-number">{{completed_payments}}</div><div class="stat-label">Completed Payments</div></div><div class="stat-card"><div class="stat-number">₦{{total_revenue}}</div><div class="stat-label">Total Revenue</div></div><div class="stat-card"><div class="stat-number">{{total_lessons_stat}}</div><div class="stat-label">Total Lessons</div></div></div>
    <div class="section"><h3>📊 Course Statistics</h3><div class="course-stats">
    {% for stat in course_stats %}<div class="course-stat"><div style="font-weight:bold;color:#ff6b35;">{{stat['course_type']|title}}</div><div>{{stat['count']}} students</div><div>₦{{stat['revenue']}}</div></div>{% endfor %}
    </div></div><div class="section"><h3>📋 Recent Enrollments</h3><table class="table"><tr><th>Student</th><th>Email</th><th>Course</th><th>Amount</th><th>Status</th><th>Date</th></tr>
    {% for enrollment in recent_enrollments %}<tr><td>{{enrollment['full_name']}}</td><td>{{enrollment['email']}}</td><td>{{enrollment['course_type']|title}}</td><td>₦{{enrollment['price']}}</td><td><span style="color:{{'#4CAF50' if enrollment['payment_status']=='completed' else '#ff9800'}};">{{enrollment['payment_status']|title}}</span></td><td>{{enrollment['enrolled_at']}}</td></tr>{% endfor %}
    </table></div></body></html>
    ''', message=message, total_users=total_users, total_enrollments=total_enrollments, completed_payments=completed_payments, total_revenue=total_revenue, total_lessons_stat=total_lessons_stat, recent_enrollments=recent_enrollments, course_stats=course_stats)

@app.route('/courses')
def student_courses():
    enrollment = session.get('enrollment')
    if not enrollment:
        return redirect(url_for('pay'))
    
    conn = None
    try:
        conn = get_db_connection()
        target_course_name = enrollment['course_type']
        course_details = conn.execute('SELECT id FROM courses WHERE name = ?', (target_course_name,)).fetchone()

        lessons = []
        modules = {}

        if course_details:
            target_course_id = course_details['id']
            lessons_data = conn.execute('''
                SELECT l.id, l.course_id, l.module_id, m.name as module_name, l.lesson, l.description, l.file_path, l.content_type, l.element_properties,
                       COALESCE(l.order_index, 1) as order_index
                FROM lessons l JOIN modules m ON l.module_id = m.id
                WHERE l.course_id = ?
                ORDER BY m.order_index, l.order_index, l.lesson
            ''', (target_course_id,)).fetchall()

            for lesson_row in lessons_data:
                lesson_dict = dict(lesson_row)
                try:
                    lesson_dict['element_properties'] = json.loads(lesson_row['element_properties']) if lesson_row['element_properties'] else {}
                except (json.JSONDecodeError, TypeError):
                    lesson_dict['element_properties'] = {}
                lessons.append(lesson_dict)

                module_name_from_join = lesson_dict['module_name']
                if module_name_from_join not in modules:
                    modules[module_name_from_join] = []
                modules[module_name_from_join].append(lesson_dict)
        
        progress_data = conn.execute("SELECT course_id, lesson_id, completed FROM course_progress WHERE user_id = ?", (enrollment['user_id'],)).fetchall()
        progress_lookup = {}
        for p_row in progress_data:
            key = f"{p_row['course_id']}_{p_row['lesson_id']}"
            progress_lookup[key] = p_row['completed']
    except Exception as e:
        log_error(db_logger, "Failed to retrieve student courses data", error=str(e))
        return "Error loading courses", 500
    finally:
        if conn:
            return_db_connection(conn)
    
    completed_count_for_this_course = 0
    if course_details:
        for lesson_item in lessons:
            progress_key = f"{course_details['id']}_{lesson_item['id']}"
            if progress_lookup.get(progress_key):
                completed_count_for_this_course +=1

    total_lessons_for_this_course = len(lessons)
    overall_progress_percent = int(completed_count_for_this_course / total_lessons_for_this_course * 100) if total_lessons_for_this_course > 0 else 0

    return render_template_string('''
    <html><head><title>My Courses - Vibes University</title>
    <style>body{font-family:Arial,sans-serif;background:#111;color:#fff;margin:0;padding:20px;line-height:1.6;}.header{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;}.welcome{color:#ff6b35;font-size:24px;margin-bottom:10px;}.course-info{color:#ccc;}.modules{display:grid;gap:20px;}.module-card{background:#222;border-radius:10px;padding:20px;border-left:4px solid #ff6b35;}.module-title{color:#ff6b35;font-size:20px;margin-bottom:15px;}.lessons{display:grid;gap:10px;}.lesson-item{background:#333;padding:15px;border-radius:8px;display:flex;justify-content:space-between;align-items:center;transition:all .3s;}.lesson-item:hover{background:#444;transform:translateX(5px);}.lesson-info{flex:1;}.lesson-title{color:#fff;font-weight:bold;margin-bottom:5px;}.lesson-desc{color:#ccc;font-size:14px;}.lesson-status{padding:5px 10px;border-radius:15px;font-size:12px;font-weight:bold;margin-left:15px;}.completed{background:#4CAF50;color:#fff;}.pending{background:#ff9800;color:#fff;}.file-icon{margin-right:8px;}.nav-bar{background:#222;padding:15px;border-radius:8px;margin-bottom:20px;}.nav-bar a{color:#ff6b35;text-decoration:none;margin-right:20px;}.progress-bar{background:#333;height:8px;border-radius:4px;margin:10px 0;overflow:hidden;}.progress-fill{background:linear-gradient(90deg,#ff6b35,#ff8c42);height:100%;transition:width .3s;}</style></head>
    <body><div class="nav-bar"><a href="{{url_for('dashboard')}}">← Dashboard</a><a href="{{url_for('student_courses')}}">My Courses</a><a href="{{url_for('logout')}}">Logout</a></div>
    <div class="header"><div class="welcome">Welcome back, {{enrollment['full_name']}}!</div>
    <div class="course-info">You're enrolled in: <strong>{{enrollment['course_type']|title}} Course</strong></div>
    <div class="progress-bar"><div class="progress-fill" style="width: {{overall_progress_percent}}%"></div></div>
    <div style="color:#ccc;font-size:14px;">{{completed_count_for_this_course}} of {{total_lessons_for_this_course}} lessons completed</div></div>
    <div class="modules">
    {% for module_name, module_lessons in modules.items() %}<div class="module-card"><div class="module-title">{{module_name}}</div><div class="lessons">
    {% for lesson_item in module_lessons %}
    {% set lesson_progress_key = (course_details.id if course_details else '') ~ '_' ~ lesson_item.id|string %}
    {% set is_completed = progress_lookup.get(lesson_progress_key, False) %}<div class="lesson-item"><div class="lesson-info">
    <div class="lesson-title">{{get_file_icon((lesson_item['file_path'] or '').split('/')[-1])}} {{lesson_item['lesson']}}</div>
    {% if lesson_item['description'] and lesson_item['content_type'] not in ['text', 'markdown']%}<div class="lesson-desc">{{lesson_item['description']}}</div>{% endif %}</div>
    <div class="lesson-status {{'completed' if is_completed else 'pending'}}">{% if is_completed %}✅ Completed{% else %}<a href="{{url_for('view_lesson',lesson_id=lesson_item['id'])}}" style="color:inherit;text-decoration:none;">▶️ Start Lesson</a>{% endif %}</div></div>{% endfor %}</div></div>{% endfor %}</div>
    {% if not modules %}<div style="text-align:center;padding:60px;color:#ccc;"><h3>No lessons available yet</h3><p>Your course content is being prepared. Check back soon!</p></div>{% endif %}</body></html>
    ''', enrollment=enrollment, modules=modules, lessons=lessons,
         progress_lookup=progress_lookup, get_file_icon=get_file_icon, course_details=course_details, completed_count_for_this_course=completed_count_for_this_course, total_lessons_for_this_course=total_lessons_for_this_course, overall_progress_percent=overall_progress_percent)

@app.route('/lesson/<int:lesson_id>')
def view_lesson(lesson_id):
    enrollment = session.get('enrollment')
    if not enrollment: return redirect(url_for('pay'))
    
    conn = None
    try:
        conn = get_db_connection()
        lesson_data_row = conn.execute("SELECT l.*, m.name as module_name, c.name as course_name FROM lessons l JOIN modules m ON l.module_id = m.id JOIN courses c ON l.course_id = c.id WHERE l.id = ?", (lesson_id,)).fetchone()
        
        if not lesson_data_row:
            return "Lesson not found", 404
        
        lesson = dict(lesson_data_row)
        try:
            lesson['element_properties'] = json.loads(lesson_data_row['element_properties']) if lesson_data_row['element_properties'] else {}
        except (json.JSONDecodeError, TypeError):
            lesson['element_properties'] = {}

        enrolled_course_name_from_session = enrollment['course_type']
        enrolled_course_details = conn.execute('SELECT id FROM courses WHERE name = ?', (enrolled_course_name_from_session,)).fetchone()

        if not enrolled_course_details or lesson['course_id'] != enrolled_course_details['id']:
            return "Access denied to this lesson.", 403

        all_lessons_raw = conn.execute("SELECT id, lesson, module_id, COALESCE(order_index, 1) as order_index FROM lessons WHERE course_id = ? ORDER BY module_id, order_index, lesson", (lesson['course_id'],)).fetchall()
        all_lessons = [dict(l) for l in all_lessons_raw]
        current_index = next((i for i, l_item in enumerate(all_lessons) if l_item['id'] == lesson_id), None)
        next_l = all_lessons[current_index + 1] if current_index is not None and current_index + 1 < len(all_lessons) else None
        prev_l = all_lessons[current_index - 1] if current_index is not None and current_index > 0 else None
    except Exception as e:
        log_error(db_logger, "Failed to retrieve lesson data", error=str(e))
        return "Error loading lesson", 500
    finally:
        if conn:
            return_db_connection(conn)
    
    content_type = lesson.get('content_type', 'file')
    element_props = lesson.get('element_properties', {})
    lesson_render_content = '<p>No content available for this lesson.</p>'

    if content_type == 'text' or content_type == 'markdown':
        md_content = element_props.get('markdown_content', lesson.get('description', ''))
        lesson_render_content = render_markdown_content(md_content if md_content else 'No text content provided.')
    elif content_type == 'video':
        video_url_prop = element_props.get('url')
        file_path = lesson.get('file_path')
        if video_url_prop and video_url_prop.strip():
             if "youtube.com/watch?v=" in video_url_prop or "youtu.be/" in video_url_prop:
                video_id = video_url_prop.split("v=")[-1].split("&")[0].split("youtu.be/")[-1].split("?")[0]
                lesson_render_content = f'''<div style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%;"><iframe src="https://www.youtube.com/embed/{video_id}" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: 0;" allowfullscreen></iframe></div>'''
             else: lesson_render_content = f'''<div><video controls width="100%"><source src="{video_url_prop}">Not supported.</video></div>'''
        elif file_path:
            file_url = url_for('static', filename=file_path.split('static/')[-1])
            lesson_render_content = f'''<div><video controls width="100%"><source src="{file_url}" type="video/{file_path.split('.')[-1].lower()}">Not supported.</video></div>'''
        else: lesson_render_content = '<p>Video content not available.</p>'
    elif content_type == 'quiz':
        quiz_question = element_props.get('question', 'N/A')
        # Ensure options is a list before join
        options_list = element_props.get('options', [])
        if not isinstance(options_list, list): options_list = []
        options_html = "".join([f"<div class='quiz-option-student' data-index='{i}' style='padding:8px; margin:5px 0; border:1px solid #555; border-radius:4px; cursor:pointer;'>{opt}</div>" for i, opt in enumerate(options_list)])
        lesson_render_content = f'''
            <div class='quiz-container' id="quiz-container-{lesson.id}">
                <h4>{quiz_question}</h4>
                <div id="quiz-options-list-{lesson.id}">{options_html}</div>
                <button onclick='submitStudentQuiz({lesson.id})' style='margin-top:10px; padding:8px 15px; background:#ff6b35; border:none; color:white; border-radius:4px;'>Submit Answer</button>
                <div id="quiz-feedback-{lesson.id}" style="margin-top:10px;"></div>
            </div>''' # Removed script tag from here
    elif content_type == 'download' and lesson.get('file_path'):
        file_url = url_for('static', filename=lesson['file_path'].split('static/')[-1])
        filename = lesson['file_path'].split('/')[-1]
        lesson_render_content = f'''<div class="file-download"><h3>{get_file_icon(filename)} {filename}</h3><a href="{file_url}" class="download-btn" download>Download File</a></div>'''
    elif lesson.get('file_path'):
         file_url = url_for('static', filename=lesson['file_path'].split('static/')[-1])
         filename = lesson['file_path'].split('/')[-1]
         if filename.split('.')[-1].lower() in ['jpg','png','gif','svg']: html_content = f"<img src='{file_url}' style='max-width:100%;'>"
         else: html_content = f"<a href='{file_url}' download class='download-btn'>Download {filename}</a>"
         lesson_render_content = html_content

    return render_template_string('''
    <html><head><title>{{lesson['lesson']}} - Vibes University</title>
    <style>body{font-family:Arial,sans-serif;background:#111;color:#fff;margin:0;padding:20px;}.header{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;}.lesson-title{color:#ff6b35;font-size:24px;margin-bottom:10px;}.lesson-meta{color:#ccc;margin-bottom:20px;}.content{background:#222;border-radius:10px;padding:30px;margin-bottom:30px;}.video-container iframe,.video-container video{width:100%;border-radius:8px;}.file-download{background:#333;padding:20px;border-radius:8px;text-align:center;border:2px dashed #ff6b35;}.download-btn{background:#ff6b35;color:#fff;padding:15px 30px;border:none;border-radius:8px;font-size:16px;font-weight:bold;text-decoration:none;display:inline-block;margin-top:10px;}.navigation{display:flex;justify-content:space-between;margin-top:30px;}.nav-btn{background:#333;color:#fff;padding:12px 20px;border:none;border-radius:8px;text-decoration:none;}.nav-btn:disabled{background:#666;}.back-link{color:#ff6b35;text-decoration:none;margin-bottom:20px;display:inline-block;}.quiz-option-student.selected{background-color:rgba(255,107,53,0.3); border-color:#ff6b35;}</style></head>
    <body><a href="{{url_for('student_courses')}}" class="back-link">← Back to Courses</a>
    <div class="header"><div class="lesson-title">{{lesson['lesson']}}</div><div class="lesson-meta">Course: {{lesson.course_name|title}} | Module: {{lesson.module_name|title}} {% if lesson['order_index'] %}| Order: {{lesson['order_index']}}{% endif %}</div></div>
    <div class="content">{{lesson_render_content|safe}}</div>
    <div class="navigation">
    {% if prev_l %}<a href="{{url_for('view_lesson',lesson_id=prev_l.id)}}" class="nav-btn">← Previous: {{prev_l.lesson}}</a>{% else %}<button class="nav-btn" disabled>← Previous</button>{% endif %}
    <a href="{{url_for('student_courses')}}" class="nav-btn">Back to Courses</a>
    {% if next_l %}<a href="{{url_for('view_lesson',lesson_id=next_l.id)}}" class="nav-btn">Next: {{next_l.lesson}} →</a>{% else %}<button class="nav-btn" disabled>Next →</button>{% endif %}
    </div><script>
        function markCompleted() {
            fetch('/api/mark-completed', { method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ user_id: {{enrollment['user_id']}}, course_id: {{lesson['course_id']}}, lesson_id: {{lesson['id']}} })
            }).then(r => r.json()).then(d => { if(d.success) console.log('Lesson marked completed'); });
        }
        document.querySelectorAll('video').forEach(v => v.addEventListener('ended', markCompleted));
        document.querySelectorAll('.download-btn[download]').forEach(b => b.addEventListener('click', markCompleted));
        {% if lesson['content_type'] == 'markdown' or lesson['content_type'] == 'text' %} setTimeout(markCompleted, 30000); {% endif %}

        {% if lesson['content_type'] == 'quiz' %}
        document.querySelectorAll('#quiz-options-list-{{lesson.id}} .quiz-option-student').forEach(opt => {
            opt.addEventListener('click', function() {
                document.querySelectorAll('#quiz-options-list-{{lesson.id}} .quiz-option-student').forEach(o => o.classList.remove('selected'));
                this.classList.add('selected');
            });
        });
        function submitStudentQuiz(lessonId) {
            const optionsContainer = document.getElementById('quiz-options-list-' + lessonId);
            if (!optionsContainer) return; // Guard if element not found
            const options = optionsContainer.querySelectorAll('.quiz-option-student');
            let selectedAnswerIndex = -1;
            options.forEach((opt, index) => {
                if (opt.classList.contains('selected')) {
                    selectedAnswerIndex = index;
                }
                opt.style.pointerEvents = 'none';
                opt.style.opacity = '0.7';
            });
            if (selectedAnswerIndex === -1) {
                alert("Please select an answer.");
                options.forEach(opt => { opt.style.pointerEvents = 'auto'; opt.style.opacity = '1';});
                return;
            }
            fetch(`/api/student/submit-quiz/${lessonId}`, {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ answer_index: selectedAnswerIndex })
            })
            .then(response => response.json())
            .then(data => {
                const feedbackEl = document.getElementById('quiz-feedback-' + lessonId);
                if (feedbackEl) { // Guard if element not found
                    if (data.success) {
                        feedbackEl.textContent = data.is_correct ? "Correct!" : "Incorrect.";
                        feedbackEl.style.color = data.is_correct ? 'lightgreen' : 'salmon';
                        if (data.is_correct) markCompleted();
                    } else {
                        feedbackEl.textContent = "Error: " + data.error;
                        feedbackEl.style.color = 'salmon';
                        options.forEach(opt => { opt.style.pointerEvents = 'auto'; opt.style.opacity = '1';});
                    }
                }
            }).catch(error => {
                console.error("Quiz submission error:", error);
                const feedbackEl = document.getElementById('quiz-feedback-' + lessonId);
                if (feedbackEl) feedbackEl.textContent = "Network error.";
                options.forEach(opt => { opt.style.pointerEvents = 'auto'; opt.style.opacity = '1';});
            });
        }
        {% endif %}
    </script></body></html>
    ''', lesson=lesson, enrollment=enrollment, next_lesson=next_l, prev_lesson=prev_l, lesson_render_content=lesson_render_content)


@app.route('/api/mark-completed', methods=['POST'])
def mark_lesson_completed():
    enrollment = session.get('enrollment')
    if not enrollment: return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    user_id, course_id, lesson_id = data.get('user_id'), data.get('course_id'), data.get('lesson_id')
    
    if not all([user_id, course_id, lesson_id]): return jsonify({'error': 'Missing required fields'}), 400
    if user_id != enrollment['user_id']: return jsonify({'error': 'Unauthorized user ID mismatch'}), 403
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        existing = conn.execute("SELECT id FROM course_progress WHERE user_id = ? AND course_id = ? AND lesson_id = ?", (user_id, course_id, lesson_id)).fetchone()
        if existing:
            cursor.execute("UPDATE course_progress SET completed = 1, completed_at = CURRENT_TIMESTAMP WHERE id = ?", (existing['id'],))
        else:
            cursor.execute("INSERT INTO course_progress (user_id, course_id, lesson_id, completed, completed_at) VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)", (user_id, course_id, lesson_id))
        conn.commit()
        return jsonify({'success': True, 'message': 'Lesson marked as completed'})
    except Exception as e:
        log_error(db_logger, "Failed to mark lesson as completed", error=str(e))
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/demo-payment', methods=['GET', 'POST'])
def demo_payment():
    if request.method == 'POST':
        name, email, phone, plan_key = request.form.get('name'), request.form.get('email'), request.form.get('phone'), request.form.get('plan', 'course')
        conn = None
        try:
            conn = get_db_connection()
            user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
            user_id = 0
            if not user:
                password_hash = generate_password_hash(secrets.token_hex(8))
                cursor = conn.cursor()
                cursor.execute('INSERT INTO users (email, password_hash, full_name, phone) VALUES (?, ?, ?, ?)', (email, password_hash, name, phone))
                user_id = cursor.lastrowid
                conn.commit()
            else: user_id = user['id']
            
            plans = { 'course': {'name': 'Course Access', 'price': 100000}, 'online': {'name': 'Online Mentorship', 'price': 400000}, 'vip': {'name': 'VIP Physical Class', 'price': 2000000} }
            plan_details = plans.get(plan_key, plans['course'])
            
            cursor = conn.cursor()
            cursor.execute("INSERT INTO enrollments (user_id, course_type, price, payment_method, payment_status, payment_reference) VALUES (?, ?, ?, ?, ?, ?)",
                           (user_id, plan_key, plan_details['price'], 'demo', 'completed', f'DEMO_{user_id}_{int(datetime.now().timestamp())}'))
            enrollment_id = cursor.lastrowid
            conn.commit()
            enrollment_for_session = conn.execute("SELECT e.*, u.email, u.full_name FROM enrollments e JOIN users u ON e.user_id = u.id WHERE e.id = ?", (enrollment_id,)).fetchone()
            session['enrollment'] = dict(enrollment_for_session)
            return redirect(url_for('dashboard'))
        except Exception as e:
            log_error(payment_logger, "Demo payment failed", error=str(e))
            return "Error processing demo payment", 500
        finally:
            if conn:
                return_db_connection(conn)
        session['enrollment'] = dict(enrollment_for_session)
        return redirect(url_for('dashboard'))
    
    return render_template_string('''
    <html><head><title>Demo Payment - Vibes University</title><style>body{font-family:Arial,sans-serif;background:#111;color:#fff;}.container{max-width:500px;margin:60px auto;background:#222;padding:40px;border-radius:15px;box-shadow:0 8px 32px #0008;}h2{color:#ff6b35;}label{display:block;margin-top:20px;}input,select{width:100%;padding:10px;margin-top:5px;border-radius:8px;border:none;background:#333;color:#fff;}.btn{background:linear-gradient(45deg,#ff6b35,#ff8c42);color:#fff;border:none;padding:15px 0;width:100%;border-radius:8px;font-size:1.1rem;margin-top:30px;cursor:pointer;font-weight:bold;}.demo-notice{background:#333;color:#ff6b35;padding:15px;border-radius:8px;margin-top:20px;text-align:center;border:1px solid #ff6b35;}</style></head>
    <body><div class="container"><h2>🎯 Demo Payment</h2><div class="demo-notice"><strong>Testing Mode:</strong> Creates a demo enrollment and redirects to dashboard.</div>
    <form method="post"><label for="plan">Select Plan</label><select name="plan" id="plan"><option value="course">Course Access (₦100,000)</option><option value="online">Online Mentorship (₦400,000)</option><option value="vip">VIP Physical Class (₦2,000,000)</option></select>
    <label for="name">Full Name</label><input type="text" name="name" id="name" required><label for="email">Email</label><input type="email" name="email" id="email" required><label for="phone">Phone</label><input type="text" name="phone" id="phone" required>
    <button class="btn" type="submit">🚀 Access Student Dashboard</button></form></div></body></html>
    ''')

@app.route('/admin/users')
def admin_users():
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    conn = None
    try:
        conn = get_db_connection()
        users = conn.execute("SELECT u.*, COUNT(e.id) as enrollment_count, SUM(CASE WHEN e.payment_status = 'completed' THEN 1 ELSE 0 END) as completed_enrollments, SUM(CASE WHEN e.payment_status = 'completed' THEN e.price ELSE 0 END) as total_spent FROM users u LEFT JOIN enrollments e ON u.id = e.user_id GROUP BY u.id ORDER BY u.created_at DESC").fetchall()
    except Exception as e:
        log_error(db_logger, "Failed to retrieve admin users data", error=str(e))
        return "Error loading users", 500
    finally:
        if conn:
            return_db_connection(conn)
    return render_template_string('''
    <html><head><title>User Management</title><style>body{font-family:Arial,sans-serif;background:#111;color:#fff;margin:0;padding:20px;}.header{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;display:flex;justify-content:space-between;align-items:center;}h1{color:#ff6b35;margin:0;}.back-btn{background:#ff6b35;color:#fff;padding:10px 20px;border:none;border-radius:8px;text-decoration:none;font-weight:bold;}.table{width:100%;border-collapse:collapse;background:#222;border-radius:10px;overflow:hidden;}.table th,.table td{padding:15px;text-align:left;border-bottom:1px solid #444;}.table th{background:#333;color:#ff6b35;font-weight:bold;}.table tr:hover{background:#333;}.status-active{color:#4CAF50;}.status-inactive{color:#f44336;}.user-email{color:#ff6b35;}</style></head>
    <body><div class="header"><h1>👥 User Management</h1><a href="{{url_for('admin_dashboard')}}" class="back-btn">← Dashboard</a></div>
    <table class="table"><tr><th>Name</th><th>Email</th><th>Phone</th><th>Enrollments</th><th>Completed</th><th>Total Spent</th><th>Joined</th><th>Status</th></tr>
    {% for user in users %}<tr><td>{{user['full_name']}}</td><td class="user-email">{{user['email']}}</td><td>{{user['phone']}}</td><td>{{user['enrollment_count']}}</td><td>{{user['completed_enrollments']}}</td><td>₦{{user['total_spent'] or 0}}</td><td>{{user['created_at']}}</td><td class="{{'status-active' if user['is_active'] else 'status-inactive'}}">{{'Active' if user['is_active'] else 'Inactive'}}</td></tr>{% endfor %}
    </table></body></html>
    ''', users=users)

@app.route('/admin/analytics')
def admin_analytics():
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    conn = None
    try:
        conn = get_db_connection()
        monthly_revenue = conn.execute("SELECT strftime('%Y-%m',enrolled_at) as month, SUM(price) as revenue, COUNT(*) as enrollments FROM enrollments WHERE payment_status='completed' GROUP BY 1 ORDER BY 1 DESC LIMIT 12").fetchall()
        course_performance = conn.execute("SELECT course_type, COUNT(*) as total_enrollments, SUM(CASE WHEN payment_status='completed' THEN 1 ELSE 0 END) as completed_enrollments, SUM(CASE WHEN payment_status='completed' THEN price ELSE 0 END) as revenue, AVG(CASE WHEN payment_status='completed' THEN price ELSE NULL END) as avg_revenue FROM enrollments GROUP BY 1").fetchall()
        lesson_stats = conn.execute("SELECT c.name as course_name, m.name as module_name, l.lesson, COUNT(cp.id) as completions FROM lessons l JOIN modules m ON l.module_id=m.id JOIN courses c ON l.course_id=c.id LEFT JOIN course_progress cp ON l.id=cp.lesson_id AND cp.completed=1 GROUP BY l.id,c.name,m.name,l.lesson ORDER BY completions DESC LIMIT 10").fetchall()
    except Exception as e:
        log_error(db_logger, "Failed to retrieve admin analytics data", error=str(e))
        return "Error loading analytics", 500
    finally:
        if conn:
            return_db_connection(conn)
    return render_template_string('''
    <html><head><title>Analytics</title><style>body{font-family:Arial,sans-serif;background:#111;color:#fff;margin:0;padding:20px;}.header{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;display:flex;justify-content:space-between;align-items:center;}h1{color:#ff6b35;margin:0;}.back-btn{background:#ff6b35;color:#fff;padding:10px 20px;border:none;border-radius:8px;text-decoration:none;font-weight:bold;}.section{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;}h3{color:#ff6b35;margin-top:0;}.table{width:100%;border-collapse:collapse;margin-top:15px;}.table th,.table td{padding:12px;text-align:left;border-bottom:1px solid #444;}.table th{background:#333;color:#ff6b35;}.table tr:hover{background:#333;}</style></head>
    <body><div class="header"><h1>📊 Analytics Dashboard</h1><a href="{{url_for('admin_dashboard')}}" class="back-btn">← Dashboard</a></div>
    <div class="section"><h3>💰 Monthly Revenue</h3><table class="table"><tr><th>Month</th><th>Revenue</th><th>Enrollments</th></tr>{% for r in monthly_revenue %}<tr><td>{{r.month}}</td><td>₦{{r.revenue}}</td><td>{{r.enrollments}}</td></tr>{% endfor %}</table></div>
    <div class="section"><h3>🎯 Course Performance</h3><table class="table"><tr><th>Course</th><th>Total</th><th>Completed</th><th>Revenue</th><th>Avg Rev.</th></tr>{% for c_perf in course_performance %}<tr><td>{{c_perf.course_type|title}}</td><td>{{c_perf.total_enrollments}}</td><td>{{c_perf.completed_enrollments}}</td><td>₦{{c_perf.revenue}}</td><td>₦{{c_perf.avg_revenue or 0}}</td></tr>{% endfor %}</table></div>
    <div class="section"><h3>📚 Top Lessons</h3><table class="table"><tr><th>Course</th><th>Module</th><th>Lesson</th><th>Completions</th></tr>{% for l_stat in lesson_stats %}<tr><td>{{l_stat.course_name|title}}</td><td>{{l_stat.module_name}}</td><td>{{l_stat.lesson}}</td><td>{{l_stat.completions}}</td></tr>{% endfor %}</table></div>
    </body></html>
    ''', monthly_revenue=monthly_revenue, course_performance=course_performance, lesson_stats=lesson_stats)

@app.route('/admin/settings', methods=['GET', 'POST'])
def admin_settings():
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    message = ''
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        if new_password:
            message = 'Admin password update simulated (not persistent for this demo environment).'
        else:
            message = 'No new password provided.'

    return render_template_string('''
    <html><head><title>Settings</title><style>body{font-family:Arial,sans-serif;background:#111;color:#fff;margin:0;padding:20px;}.header{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;display:flex;justify-content:space-between;align-items:center;}h1{color:#ff6b35;margin:0;}.back-btn{background:#ff6b35;color:#fff;padding:10px 20px;border:none;border-radius:8px;text-decoration:none;font-weight:bold;}.section{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;}h3{color:#ff6b35;margin-top:0;}.form-group{margin-bottom:15px;}.form-group label{display:block;margin-bottom:5px;color:#ccc;}.form-group input{width:100%;padding:10px;border-radius:8px;border:none;background:#444;color:#fff;}.save-btn{background:#4CAF50;color:#fff;padding:12px 30px;border:none;border-radius:8px;font-weight:bold;cursor:pointer;}.success-msg{padding:15px;border-radius:8px;margin-bottom:20px; background-color: #333; color: #4CAF50; border: 1px solid #4CAF50;}</style></head>
    <body><div class="header"><h1>⚙️ System Settings</h1><a href="{{url_for('admin_dashboard')}}" class="back-btn">← Dashboard</a></div>
    {% if message %}<div class="success-msg">{{message}}</div>{% endif %}
    <div class="section"><h3>🔐 Security Settings</h3><form method="post">
    <div class="form-group"><label>New Admin Password:</label><input type="password" name="new_password" placeholder="Enter new admin password"></div>
    <button type="submit" class="save-btn">💾 Save Changes</button></form></div>
    <div class="section"><h3>🔗 Quick Links</h3><p><a href="{{url_for('admin_users')}}" style="color:#ff6b35;">👥 Manage Users</a></p><p><a href="{{url_for('admin_analytics')}}" style="color:#ff6b35;">📊 View Analytics</a></p><p><a href="{{url_for('demo_payment')}}" style="color:#ff6b35;">🎯 Test Student Dashboard</a></p></div>
    </body></html>
    ''', message=message)

@app.route('/admin/announcements', methods=['GET', 'POST'])
def admin_announcements():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    message = ''
    conn = None
    try:
        conn = get_db_connection()

        if request.method == 'POST':
            title = request.form.get('title')
            msg_content = request.form.get('message_content')
            priority = request.form.get('priority', 'normal')
            target_audience = request.form.get('target_audience', 'all')
            expires_at_str = request.form.get('expires_at')
            is_active = request.form.get('is_active', '1') # Assuming '1' for active

            if title and msg_content:
                try:
                    cursor = conn.cursor()
                    # For now, only insert, no edit logic in this placeholder
                    cursor.execute("""
                        INSERT INTO announcements (title, message, priority, target_audience, is_active, expires_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (title, msg_content, priority, target_audience, 1 if is_active == '1' else 0, expires_at_str if expires_at_str else None))
                    conn.commit()
                    message = f"Announcement '{title}' created successfully."
                except Exception as e:
                    message = f"Error creating announcement: {str(e)}"
            else:
                message = "Title and Message are required for an announcement."

        announcements_data = conn.execute("SELECT * FROM announcements ORDER BY created_at DESC").fetchall()
    except Exception as e:
        log_error(db_logger, "Failed to retrieve admin announcements data", error=str(e))
        return "Error loading announcements", 500
    finally:
        if conn:
            return_db_connection(conn)

    return render_template_string('''
    <html><head><title>Admin - Announcements</title>
    <style>body{font-family:Arial,sans-serif;background:#111;color:#fff;margin:0;padding:20px;}.header{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;display:flex;justify-content:space-between;align-items:center;}h1{color:#ff6b35;margin:0;}.back-btn{background:#ff6b35;color:#fff;padding:10px 20px;border:none;border-radius:8px;text-decoration:none;font-weight:bold;}.section{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;}h3{color:#ff6b35;margin-top:0;}.form-group{margin-bottom:15px;}.form-group label{display:block;margin-bottom:5px;color:#ccc;}.form-group input, .form-group textarea, .form-group select{width:100%;padding:10px;border-radius:8px;border:none;background:#444;color:#fff;box-sizing: border-box;}.save-btn{background:#4CAF50;color:#fff;padding:12px 30px;border:none;border-radius:8px;font-weight:bold;cursor:pointer;}.success-msg{padding:15px;border-radius:8px;margin-bottom:20px; background-color: #333; color: #4CAF50; border: 1px solid #4CAF50;}.error-msg{padding:15px;border-radius:8px;margin-bottom:20px; background-color: #333; color: #f44336; border: 1px solid #f44336;}.table{width:100%;border-collapse:collapse;margin-top:15px;}.table th,.table td{padding:12px;text-align:left;border-bottom:1px solid #444;}.table th{background:#333;color:#ff6b35;}</style></head>
    <body><div class="header"><h1>📢 Manage Announcements</h1><a href="{{url_for('admin_dashboard')}}" class="back-btn">← Dashboard</a></div>
    {% if message and 'Error' not in message %}<div class="success-msg">{{message}}</div>{% elif message and 'Error' in message %}<div class="error-msg">{{message}}</div>{% endif %}
    <div class="section"><h3>Create Announcement</h3><form method="post">
        <div class="form-group"><label for="title">Title:</label><input type="text" id="title" name="title" required></div>
        <div class="form-group"><label for="message_content">Message:</label><textarea id="message_content" name="message_content" rows="4" required></textarea></div>
        <div class="form-group"><label for="priority">Priority:</label><select id="priority" name="priority"><option value="normal">Normal</option><option value="high">High</option></select></div>
        <div class="form-group"><label for="target_audience">Target Audience (e.g., all, course_name):</label><input type="text" id="target_audience" name="target_audience" value="all"></div>
        <div class="form-group"><label for="expires_at">Expires At (YYYY-MM-DD HH:MM:SS, optional):</label><input type="text" id="expires_at" name="expires_at" placeholder="YYYY-MM-DD HH:MM:SS"></div>
        <button type="submit" class="save-btn">Create Announcement</button>
    </form></div>
    <div class="section"><h3>Existing Announcements</h3>
    {% if announcements_data %}
    <table class="table"><tr><th>Title</th><th>Message</th><th>Priority</th><th>Target</th><th>Active</th><th>Created</th><th>Expires</th><!--<th>Actions</th>--></tr>
    {% for ann in announcements_data %}
    <tr><td>{{ann.title}}</td><td>{{ann.message[:80] + ('...' if ann.message|length > 80 else '') }}</td><td>{{ann.priority}}</td><td>{{ann.target_audience}}</td><td>{{'Yes' if ann.is_active else 'No'}}</td><td>{{ann.created_at.split('.')[0]}}</td><td>{{ann.expires_at.split('.')[0] if ann.expires_at else 'N/A'}}</td><!--<td>Edit | Delete</td>--></tr>
    {% endfor %}
    </table>
    {% else %}<p>No announcements found.</p>{% endif %}
    </div></body></html>
    ''', message=message, announcements_data=announcements_data)

@app.route('/admin/preview/<course_type>')
def admin_preview_course(course_type):
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    conn = None
    try:
        conn = get_db_connection()
        target_course = conn.execute("SELECT * FROM courses WHERE name = ?", (course_type,)).fetchone()
        
        modules_list = []
        lessons_list = []
        course_name_for_template = course_type
        
        if target_course:
            course_id = target_course['id']
            course_name_for_template = target_course['name']
            modules_list_raw = conn.execute("SELECT * FROM modules WHERE course_id = ? ORDER BY order_index", (course_id,)).fetchall()
            modules_list = [dict(m) for m in modules_list_raw]

            lessons_list_raw = conn.execute("SELECT l.*, m.name as module_name FROM lessons l JOIN modules m ON l.module_id = m.id WHERE l.course_id = ? ORDER BY m.order_index, l.order_index", (course_id,)).fetchall()
            lessons_list = [dict(l) for l in lessons_list_raw]
    except Exception as e:
        log_error(db_logger, "Failed to retrieve admin preview course data", error=str(e))
        return "Error loading course preview", 500
    finally:
        if conn:
            return_db_connection(conn)
    
    return render_template_string('''
    <html><head><title>Course Preview - {{course_name|title}}</title>
    <style>body{font-family:Arial,sans-serif;background:#111;color:#fff;margin:0;padding:20px;}.header{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;}.preview-title{color:#ff6b35;font-size:24px;margin-bottom:10px;}.course-info{color:#ccc;margin-bottom:20px;}.modules{display:grid;gap:20px;}.module-card{background:#222;border-radius:10px;padding:20px;border-left:4px solid #ff6b35;}.module-title{color:#ff6b35;font-size:20px;margin-bottom:15px;}.lessons{display:grid;gap:10px;}.lesson-item{background:#333;padding:15px;border-radius:8px;display:flex;justify-content:space-between;align-items:center;}.lesson-info{flex:1;}.lesson-title{color:#fff;font-weight:bold;margin-bottom:5px;}.lesson-desc{color:#ccc;font-size:14px;}.lesson-status a{color:inherit;text-decoration:none;background:#666;color:#ccc;padding:5px 10px;border-radius:15px;font-size:12px;font-weight:bold;margin-left:15px;}.nav-bar{background:#222;padding:15px;border-radius:8px;margin-bottom:20px;}.nav-bar a{color:#ff6b35;text-decoration:none;margin-right:20px;}.preview-notice{background:#333;color:#ff6b35;padding:15px;border-radius:8px;margin-bottom:20px;border:1px solid #ff6b35;}.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:15px;margin-bottom:20px;}.stat-card{background:#333;padding:15px;border-radius:8px;text-align:center;}.stat-number{font-size:1.5rem;font-weight:bold;color:#ff6b35;}</style></head>
    <body><div class="nav-bar"><a href="{{url_for('admin_dashboard')}}">← Admin Dashboard</a>
    <a href="{{url_for('admin_preview_course',course_type='AI Marketing Mastery')}}">AI Marketing Mastery</a> <a href="{{url_for('admin_preview_course',course_type='AI Coding & Development')}}">AI Coding</a></div>
    <div class="preview-notice"><strong>👁️ Admin Preview:</strong> {{course_name|title}}</div>
    <div class="header"><div class="preview-title">{{course_name|title}} Course Preview</div><div class="stats"><div class="stat-card"><div class="stat-number">{{modules_list|length}}</div><div>Modules</div></div><div class="stat-card"><div class="stat-number">{{lessons_list|length}}</div><div>Total Lessons</div></div></div></div>
    <div class="modules">{% for module_item in modules_list %}<div class="module-card"><div class="module-title">{{module_item.name}}</div><div class="lessons">
    {% for lesson_item in lessons_list %}{% if lesson_item.module_id == module_item.id %}<div class="lesson-item"><div class="lesson-info">
    <div class="lesson-title">{{get_file_icon((lesson_item.file_path or '').split('/')[-1])}} {{lesson_item.lesson}}</div>
    {% if lesson_item.description %}<div class="lesson-desc">{{lesson_item.description}}</div>{% endif %}</div>
    <div class="lesson-status"><a href="{{url_for('admin_preview_lesson',lesson_id=lesson_item.id)}}">👁️ Preview</a></div></div>{% endif %}{% endfor %}</div></div>{% endfor %}</div>
    {% if not modules_list %}<div style="text-align:center;padding:60px;color:#ccc;"><h3>No modules/lessons for {{course_name|title}} course.</h3><a href="{{url_for('admin_dashboard')}}" style="color:#ff6b35;">Go to Admin Dashboard</a></div>{% endif %}</body></html>
    ''', course_name=course_name_for_template, modules_list=modules_list, lessons_list=lessons_list, get_file_icon=get_file_icon)

@app.route('/admin/preview/lesson/<int:lesson_id>')
def admin_preview_lesson(lesson_id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    conn = None
    try:
        conn = get_db_connection()
        lesson_data = conn.execute("SELECT l.*, m.name as module_name, c.name as course_name FROM lessons l JOIN modules m ON l.module_id = m.id JOIN courses c ON l.course_id = c.id WHERE l.id = ?", (lesson_id,)).fetchone()
        if not lesson_data: return "Lesson not found", 404

        lesson = dict(lesson_data)
        try: lesson['element_properties'] = json.loads(lesson_data['element_properties']) if lesson_data['element_properties'] else {}
        except: lesson['element_properties'] = {}

        all_lessons_raw = conn.execute("SELECT id,lesson,module_id FROM lessons WHERE course_id=? ORDER BY module_id,order_index,lesson", (lesson['course_id'],)).fetchall()
        all_lessons = [dict(l) for l in all_lessons_raw]
        current_index = next((i for i, l_item in enumerate(all_lessons) if l_item['id'] == lesson_id), None)
        next_l = all_lessons[current_index + 1] if current_index is not None and current_index + 1 < len(all_lessons) else None
        prev_l = all_lessons[current_index - 1] if current_index is not None and current_index > 0 else None
    except Exception as e:
        log_error(db_logger, "Failed to retrieve admin preview lesson data", error=str(e))
        return "Error loading lesson preview", 500
    finally:
        if conn:
            return_db_connection(conn)

    content_type, props = lesson.get('content_type','file'), lesson.get('element_properties',{})
    lesson_render_content = "<p>No content.</p>"
    if content_type in ['text','markdown']: lesson_render_content = render_markdown_content(props.get('markdown_content', lesson.get('description','')))
    elif content_type == 'video':
        url, fp = props.get('url'), lesson.get('file_path')
        if url: html_content = f"<iframe src='{url.replace('watch?v=', 'embed/')}' width='100%' height='450' frameborder='0' allowfullscreen></iframe>" if 'youtube.com' in url or 'youtu.be' in url else f"<video controls width='100%' src='{url}'></video>"
        elif fp: html_content = f"<video controls width='100%' src='{url_for('static', filename=fp.split('static/')[-1])}'></video>"
        lesson_render_content = html_content if 'html_content' in locals() else "<p>Video content not available.</p>"
    elif content_type == 'quiz': lesson_render_content = f"<h4>{props.get('question','N/A')}</h4><ul>{''.join(f'<li>{o}</li>' for o in props.get('options',[]))}</ul>"
    elif content_type == 'download' and lesson.get('file_path'):
        fp_url = url_for('static', filename=lesson['file_path'].split('static/')[-1])
        lesson_render_content = f"<a href='{fp_url}' download class='download-btn'>Download {lesson['file_path'].split('/')[-1]}</a>"
    elif lesson.get('file_path'):
         fp_url = url_for('static', filename=lesson['file_path'].split('static/')[-1])
         filename = lesson['file_path'].split('/')[-1]
         if filename.split('.')[-1].lower() in ['jpg','png','gif','svg']: html_content = f"<img src='{fp_url}' style='max-width:100%;'>"
         else: html_content = f"<a href='{fp_url}' download class='download-btn'>Download {filename}</a>"
         lesson_render_content = html_content

    return render_template_string('''
    <html><head><title>{{lesson.lesson}} - Preview</title>
    <style>body{font-family:Arial,sans-serif;background:#111;color:#fff;margin:0;padding:20px;}.header{background:#222;padding:20px;border-radius:10px;margin-bottom:20px;}.lesson-title{color:#ff6b35;font-size:22px;}.lesson-meta{color:#ccc;font-size:0.9em;}.content{background:#222;padding:20px;border-radius:10px;}.navigation{display:flex;justify-content:space-between;margin-top:20px;}.nav-btn{background:#333;color:#fff;padding:10px 15px;border-radius:5px;text-decoration:none;}.nav-btn:disabled{background:#555;color:#888;}.back-link{color:#ff6b35;}</style></head>
    <body><a href="{{url_for('admin_preview_course', course_type=lesson.course_name)}}" class="back-link">← {{lesson.course_name}}</a>
    <div class="header"><h1 class="lesson-title">{{lesson.lesson}}</h1><p class="lesson-meta">Module: {{lesson.module_name}}</p></div>
    <div class="content">{{lesson_render_content|safe}}</div>
    <div class="navigation">
    {% if prev_l %}<a href="{{url_for('admin_preview_lesson',lesson_id=prev_l.id)}}" class="nav-btn">← Prev: {{prev_l.lesson}}</a>{% else %}<button class="nav-btn" disabled>← Prev</button>{% endif %}
    <a href="{{url_for('admin_preview_course', course_type=lesson.course_name)}}" class="nav-btn">Back to Course</a>
    {% if next_l %}<a href="{{url_for('admin_preview_lesson',lesson_id=next_l.id)}}" class="nav-btn">Next: {{next_l.lesson}} →</a>{% else %}<button class="nav-btn" disabled>Next →</button>{% endif %}
    </div></body></html>
    ''', lesson=lesson, prev_l=prev_l, next_l=next_l, html_content=lesson_render_content)

# --- Module Management APIs ---
@app.route('/api/admin/courses/<int:course_id>/modules', methods=['POST'])
def api_admin_create_module(course_id):
    if not session.get('admin_logged_in'): return jsonify({'error': 'Not authorized'}), 401
    data = request.get_json()
    if not data or not data.get('name'): return jsonify({'error': 'Missing module name'}), 400
    name, description, order_index = data['name'], data.get('description',''), data.get('order_index',1)
    conn = None
    try:
        conn = get_db_connection()
        if not conn.execute("SELECT id FROM courses WHERE id = ?", (course_id,)).fetchone():
            return jsonify({'error': 'Course not found'}), 404
        cursor = conn.cursor()
        cursor.execute('INSERT INTO modules (course_id,name,description,order_index) VALUES (?,?,?,?)', (course_id,name,description,order_index))
        module_id = cursor.lastrowid
        conn.commit()
        return jsonify({'message': 'Module created', 'module_id': module_id}), 201
    except Exception as e:
        log_error(db_logger, "Failed to create module", error=str(e))
        return jsonify({'error': f'DB error: {str(e)}'}), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/admin/courses/<int:course_id>/modules', methods=['GET'])
def api_admin_get_modules(course_id):
    if not session.get('admin_logged_in'): return jsonify({'error': 'Not authorized'}), 401
    conn = None
    try:
        conn = get_db_connection()
        if not conn.execute("SELECT id FROM courses WHERE id = ?", (course_id,)).fetchone():
            return jsonify({'error': 'Course not found'}), 404
        modules_data = conn.execute("SELECT id,name,description,order_index FROM modules WHERE course_id=? ORDER BY order_index", (course_id,)).fetchall()
        return jsonify([dict(row) for row in modules_data])
    except Exception as e:
        log_error(db_logger, "Failed to retrieve modules", error=str(e))
        return jsonify({'error': f'DB error: {str(e)}'}), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/admin/modules/<int:module_id>', methods=['PUT'])
def api_admin_update_module(module_id):
    if not session.get('admin_logged_in'): return jsonify({'error': 'Not authorized'}), 401
    data = request.get_json();
    if not data: return jsonify({'error': 'No data'}), 400

    fields, params_list = [], []
    if 'name' in data: fields.append("name=?"); params_list.append(data['name'])
    if 'description' in data: fields.append("description=?"); params_list.append(data['description'])
    if 'order_index' in data: fields.append("order_index=?"); params_list.append(data['order_index'])
    if not fields: return jsonify({'message': 'No fields to update'}), 200

    params_list.append(module_id)
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"UPDATE modules SET {','.join(fields)} WHERE id=?", tuple(params_list))
        updated_rows = cursor.rowcount
        conn.commit()
        return jsonify({'message':'Module updated'}) if updated_rows > 0 else jsonify({'error':'Module not found or no change'}),404
    except Exception as e:
        log_error(db_logger, "Failed to update module", error=str(e))
        return jsonify({'error': f'DB error: {str(e)}'}), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/admin/modules/<int:module_id>', methods=['DELETE'])
def api_admin_delete_module(module_id):
    if not session.get('admin_logged_in'): return jsonify({'error': 'Not authorized'}), 401
    conn = None
    try:
        conn = get_db_connection()
        if conn.execute("SELECT COUNT(id) FROM lessons WHERE module_id=?",(module_id,)).fetchone()['count'] > 0:
            return jsonify({'error': 'Module has lessons. Delete them first.'}), 400
        cursor = conn.cursor()
        cursor.execute("DELETE FROM modules WHERE id=?", (module_id,))
        deleted_rows = cursor.rowcount
        conn.commit()
        return jsonify({'message':'Module deleted'}) if deleted_rows > 0 else jsonify({'error':'Module not found'}),404
    except Exception as e:
        log_error(db_logger, "Failed to delete module", error=str(e))
        return jsonify({'error': f'DB error: {str(e)}'}), 500
    finally:
        if conn:
            return_db_connection(conn)
# --- End of Module Management APIs ---

@app.route('/api/admin/courses/<int:course_id>/lessons', methods=['POST'])
def api_admin_create_lesson_in_course(course_id):
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Not authorized'}), 401

    conn = None
    try:
        conn = get_db_connection()
        # Verify course exists
        course = conn.execute('SELECT id, name FROM courses WHERE id = ?', (course_id,)).fetchone()
        if not course:
            return jsonify({'error': 'Course not found'}), 404

        form_data = request.form # For multipart/form-data

        lesson_title = form_data.get('lesson_title')
        module_id_str = form_data.get('module_id')
        content_type = form_data.get('content_type')
        order_index_str = form_data.get('order_index')
        element_properties_json = form_data.get('element_properties') # Should be a JSON string

        if not all([lesson_title, module_id_str, content_type, order_index_str, element_properties_json]):
            return jsonify({'error': 'Missing required fields: lesson_title, module_id, content_type, order_index, element_properties'}), 400

        try:
            module_id = int(module_id_str)
            order_index = int(order_index_str)
            element_properties = json.loads(element_properties_json) # Parse the JSON string
        except ValueError:
            return jsonify({'error': 'Invalid module_id or order_index format'}), 400
        except json.JSONDecodeError:
            return jsonify({'error': 'Invalid JSON format for element_properties'}), 400

        # Verify module belongs to the course
        module = conn.execute('SELECT id, name FROM modules WHERE id = ? AND course_id = ?', (module_id, course_id)).fetchone()
        if not module:
            return jsonify({'error': 'Module not found or does not belong to this course'}), 400

        file_path_to_save = None
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                course_name_for_path = secure_filename(course['name'])
                module_name_for_path = secure_filename(module['name'])

                lesson_upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], course_name_for_path, module_name_for_path)
                os.makedirs(lesson_upload_dir, exist_ok=True)

                name_part, ext_part = os.path.splitext(filename)
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
                unique_filename = f"{name_part}_{timestamp}{ext_part}"

                file_path_to_save = os.path.join(lesson_upload_dir, unique_filename)
                file.save(file_path_to_save)
            elif file and file.filename and not allowed_file(file.filename):
                 return jsonify({'error': f'Uploaded file type not allowed for {file.filename}'}), 400

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO lessons (course_id, module_id, lesson, content_type, order_index, element_properties, file_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (course_id, module_id, lesson_title, content_type, order_index, json.dumps(element_properties), file_path_to_save))
        new_lesson_id = cursor.lastrowid
        conn.commit()

        return jsonify({
            'message': 'Lesson element created successfully',
            'lesson': {
                'id': new_lesson_id,
                'lesson': lesson_title,
                'module_id': module_id,
                'content_type': content_type,
                'order_index': order_index,
                'element_properties': element_properties,
                'file_path': file_path_to_save
            }
        }), 201

    except Exception as e:
        # It's good practice to log the actual exception
        log_error(app_logger, f"Error creating lesson for course {course_id}", error=str(e), course_id=course_id)
        return jsonify({'error': f'An internal server error occurred.'}), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/student/submit-quiz/<int:lesson_id>', methods=['POST'])
def api_student_submit_quiz(lesson_id):
    # OLD: if not session.get('admin_logged_in'): return jsonify({'error': 'Not authorized'}), 401
    enrollment = session.get('enrollment')
    if not enrollment:
        return jsonify({'error': 'Not authenticated or not enrolled'}), 401

    data = request.get_json()
    if not data or 'answer_index' not in data:
        return jsonify({'error': 'Missing answer_index'}), 400

    conn = None
    try:
        conn = get_db_connection()
        lesson = conn.execute('SELECT id, course_id, element_properties FROM lessons WHERE id = ? AND content_type = ?', (lesson_id, 'quiz')).fetchone()
        if not lesson:
            return jsonify({'error': 'Quiz lesson not found'}), 404

        # Authorization: Check if the student's enrollment matches the lesson's course
        enrolled_course_name = enrollment.get('course_type')
        if not enrolled_course_name:
            return jsonify({'error': 'Enrollment course type not found in session'}), 403

        course_of_lesson = conn.execute('SELECT name FROM courses WHERE id = ?', (lesson['course_id'],)).fetchone()
        if not course_of_lesson or course_of_lesson['name'] != enrolled_course_name:
            return jsonify({'error': 'Not authorized to submit quiz for this course'}), 403

        user_id = enrollment['user_id']

        props = json.loads(lesson['element_properties']) if lesson['element_properties'] else {}
        correct_answer_index = props.get('correct_answer_index')
        submitted_answer_index = data['answer_index']

        is_correct = (correct_answer_index is not None and int(submitted_answer_index) == int(correct_answer_index))
        score = 100 if is_correct else 0

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO quiz_attempts (user_id, lesson_id, course_id, submitted_answers, is_correct, score)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, lesson_id, lesson['course_id'], json.dumps({'answer_index': submitted_answer_index}), is_correct, score))
        conn.commit()

        return jsonify({'success': True, 'is_correct': is_correct, 'score': score, 'message': 'Quiz submitted successfully'})

    except Exception as e:
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/admin/lessons/<int:lesson_id>', methods=['PUT'])
def api_admin_update_lesson(lesson_id):
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Not authorized'}), 401

    conn = None
    new_file_uploaded_path = None

    try:
        conn = get_db_connection()
        existing_lesson = conn.execute('SELECT * FROM lessons WHERE id = ?', (lesson_id,)).fetchone()
        if not existing_lesson:
            return jsonify({'error': 'Lesson not found'}), 404

        fields_to_update = []
        params = []
        form_data_dict = {} # To store parsed data from JSON or Form

        content_type_from_request = request.content_type.split(';')[0].strip()

        if content_type_from_request == 'application/json':
            form_data_dict = request.get_json()
            if not form_data_dict:
                return jsonify({'error': 'Invalid JSON data'}), 400
        elif content_type_from_request == 'multipart/form-data':
            form_data_dict = request.form.to_dict() # Convert ImmutableMultiDict to mutable dict
        else:
            return jsonify({'error': f'Unsupported Content-Type: {request.content_type}'}), 415

        # Populate fields_to_update and params based on 'form_data_dict'
        if 'lesson_title' in form_data_dict:
            fields_to_update.append("lesson = ?")
            params.append(form_data_dict['lesson_title'])
        if 'module_id' in form_data_dict:
            try:
                module_id = int(form_data_dict['module_id'])
                module_check = conn.execute("SELECT id FROM modules WHERE id = ? AND course_id = ?",
                                            (module_id, existing_lesson['course_id'])).fetchone()
                if not module_check:
                    raise ValueError("Module ID not found or does not belong to the course.")
                fields_to_update.append("module_id = ?")
                params.append(module_id)
            except ValueError as ve:
                return jsonify({'error': f'Invalid module_id: {str(ve)}'}), 400

        if 'element_properties' in form_data_dict:
            props_data = form_data_dict['element_properties']
            if isinstance(props_data, str):
                try:
                    json.loads(props_data)
                    fields_to_update.append("element_properties = ?")
                    params.append(props_data)
                except json.JSONDecodeError:
                    return jsonify({'error': 'Invalid JSON for element_properties'}), 400
            elif isinstance(props_data, dict):
                fields_to_update.append("element_properties = ?")
                params.append(json.dumps(props_data))


        if 'order_index' in form_data_dict:
            fields_to_update.append("order_index = ?")
            params.append(form_data_dict['order_index'])

        # File handling for multipart/form-data
        if content_type_from_request == 'multipart/form-data':
            if 'file' in request.files:
                file = request.files['file']
                if file and file.filename:
                    if allowed_file(file.filename):
                        if existing_lesson['file_path'] and os.path.exists(existing_lesson['file_path']):
                            os.remove(existing_lesson['file_path'])

                        filename = secure_filename(file.filename)
                        current_course_id = existing_lesson['course_id']

                        module_id_for_path_str = form_data_dict.get('module_id', str(existing_lesson['module_id']))
                        module_id_for_path = int(module_id_for_path_str)

                        module_info = conn.execute("SELECT name FROM modules WHERE id = ? AND course_id = ?",
                                                    (module_id_for_path, current_course_id)).fetchone()
                        if not module_info:
                                return jsonify({'error': f'Error determining module for file path: Module ID {module_id_for_path} not found for course.'}), 400
                        current_module_name_for_path = secure_filename(module_info['name'])

                        course_name_for_path_row = conn.execute('SELECT name FROM courses WHERE id = ?', (current_course_id,)).fetchone()
                        if not course_name_for_path_row:
                            return jsonify({'error': 'Associated course not found for file path construction.'}), 500
                        course_name_for_path = secure_filename(course_name_for_path_row['name'])

                        lesson_upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], course_name_for_path, current_module_name_for_path)
                        os.makedirs(lesson_upload_dir, exist_ok=True)
                        new_file_uploaded_path = os.path.join(lesson_upload_dir, filename)
                        file.save(new_file_uploaded_path)

                        path_updated = False
                        for i, field_sql in enumerate(fields_to_update):
                            if "file_path = ?" in field_sql:
                                params[i] = new_file_uploaded_path
                                path_updated = True; break
                        if not path_updated:
                            fields_to_update.append("file_path = ?"); params.append(new_file_uploaded_path)

                        # If a new file is uploaded, this specific clear_file flag (from this form submission) is irrelevant for *this* update.
                        # The action of uploading a new file implies replacing the old one.
                        if 'clear_file' in form_data_dict: # Using 'clear_file' as sent by JS FormData
                             form_data_dict.pop('clear_file', None)


                    else:
                        return jsonify({'error': f'New file type not allowed for {file.filename}'}), 400

            if form_data_dict.get('clear_file') == 'true' and not new_file_uploaded_path:
                if existing_lesson['file_path'] and os.path.exists(existing_lesson['file_path']):
                    try: os.remove(existing_lesson['file_path'])
                    except OSError as e: print(f"Error deleting old file {existing_lesson['file_path']}: {e}")

                path_updated = False
                for i, field_sql in enumerate(fields_to_update):
                    if "file_path = ?" in field_sql:
                        params[i] = None; path_updated = True; break
                if not path_updated:
                    fields_to_update.append("file_path = ?"); params.append(None)

        if not fields_to_update :
             # Check if the only operation was clearing a file that actually existed
            was_file_cleared_operation = form_data_dict.get('clear_file') == 'true' and existing_lesson['file_path'] and not new_file_uploaded_path
            if not was_file_cleared_operation : # If no other fields and no actual file clearing happened
                return jsonify({'message': 'No fields or file operations to update'}), 200

        params.append(lesson_id)
        cursor = conn.cursor()
        query = f"UPDATE lessons SET {', '.join(fields_to_update)} WHERE id = ?"
        cursor.execute(query, tuple(params))
        conn.commit()
        return jsonify({'message': 'Lesson element updated successfully'})
    except Exception as e:
        return jsonify({'error': f'Database operation failed: {str(e)}'}), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/admin/lessons/<int:lesson_id>', methods=['DELETE'])
def api_admin_delete_lesson(lesson_id):
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Not authorized'}), 401

    conn = None
    try:
        conn = get_db_connection()
        lesson = conn.execute('SELECT file_path FROM lessons WHERE id = ?', (lesson_id,)).fetchone()

        if not lesson:
            return jsonify({'error': 'Lesson not found'}), 404

        if lesson['file_path'] and os.path.exists(lesson['file_path']):
            os.remove(lesson['file_path'])

        cursor = conn.cursor()
        cursor.execute("DELETE FROM lessons WHERE id = ?", (lesson_id,))
        conn.commit()
        return jsonify({'message': 'Lesson element deleted successfully'})
    except Exception as e:
        return jsonify({'error': f'Database operation failed or file deletion failed: {str(e)}'}), 500
    finally:
        if conn:
            return_db_connection(conn)

    return jsonify({'message': 'Lesson element deleted successfully'})

@app.route('/admin/course-studio')
def admin_course_studio_page():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Vibes University - Course Design Studio</title>
        <link rel="stylesheet" href="https://unpkg.com/easymde/dist/easymde.min.css">
        <script src="https://unpkg.com/easymde/dist/easymde.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #1a1a2e; color: white; margin: 0; padding: 0; display: flex; flex-direction: column; height: 100vh; }
            .header-bar { background: rgba(255,255,255,0.1); padding: 1rem 2rem; color: #ff6b35; border-bottom: 1px solid #ff6b35;}
            .studio-container { display: grid; grid-template-columns: 280px 1fr 320px; flex-grow: 1; gap: 1rem; padding: 1rem; overflow: hidden; }
            .panel { background: rgba(255,255,255,0.05); border-radius: 10px; padding: 1.5rem; border: 1px solid rgba(255,107,53,0.2); overflow-y: auto; }
            .panel-title { color: #ff6b35; font-size: 1.2rem; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 1px solid rgba(255,107,53,0.3); }
            .main-canvas-area { display: flex; flex-direction: column; }
            .tabs { display: flex; margin-bottom: 1rem; border-bottom: 1px solid rgba(255,107,53,0.3); }
            .tab { padding: 0.8rem 1rem; background: none; border: none; color: #ccc; cursor: pointer; border-bottom: 2px solid transparent; }
            .tab.active { color: #ff6b35; border-bottom-color: #ff6b35; }
            .tab-content { display: none; flex-grow: 1; overflow-y: auto; }
            .tab-content.active { display: block; }
            .course-canvas { min-height: 400px; background: rgba(0,0,0,0.1); border: 2px dashed rgba(255,107,53,0.3); border-radius: 8px; padding: 1rem; position: relative; }
            .lesson-drop-indicator { height: 2px; background-color: #ff6b35; margin: 2px 0; width: 100%; }
            .module-drop-indicator { height:10px; background:rgba(255,107,53,0.5); margin: 5px 0; border-radius: 3px;}
            .drop-target-highlight { background-color: rgba(255,107,53,0.1); }
            .dragging-item { box-shadow: 0 0 15px rgba(255, 107, 53, 0.7); border-color: rgba(255, 107, 53, 0.7) !important; }

            button, input, select, textarea { background-color: rgba(255,255,255,0.1); border: 1px solid rgba(255,107,53,0.3); color: white; padding: 0.5em; border-radius: 5px; margin-bottom: 0.5em; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
            button { cursor: pointer; background-color: #ff6b35; }
            .element-btn { display: block; width: 100%; margin-bottom: 0.5rem; background: linear-gradient(45deg, #ff6b35, #f7931e); }
            .form-group { margin-bottom: 1rem; }
            .form-group label { display: block; color: #ffaf87; margin-bottom: .3rem; font-size:0.9em; }
            .btn-primary { background: linear-gradient(45deg, #ff6b35, #f7931e); color: white; padding: 0.8rem 1.5rem; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; width: 100%; margin-top: 1rem; transition: all 0.3s; }
            .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(255, 107, 53, 0.3); }
            .EasyMDEContainer .CodeMirror { background: rgba(255,255,255,0.05); border-color: rgba(255,107,53,0.3); color:white; }
            .editor-toolbar a { color: #ccc !important; }
            .editor-toolbar a.active, .editor-toolbar a:hover { background: rgba(255,107,53,0.3) !important; border-color: #ff6b35 !important; }
            .CodeMirror-cursor { border-left: 1px solid white !important; }
            #course-preview-canvas .module-preview-item { margin-top:20px; padding:15px; background:rgba(255,255,255,0.03); border-radius:5px; border-left: 3px solid #ff8c42; }
            #course-preview-canvas .module-preview-item h3 { color:#ff8c42; margin-bottom:10px; font-size:1.4em;}
            #course-preview-canvas .lesson-preview-item { margin-bottom:15px; padding:10px; background:rgba(255,255,255,0.04); border-radius:5px; }
            #course-preview-canvas .lesson-preview-item h4 { color:#e0e0e0; font-size:1.1em; margin-bottom:8px;}
            #course-preview-canvas .quiz-option { padding:8px; margin:5px 0; border:1px solid #555; border-radius:4px; }
            #course-preview-canvas .download-btn { opacity:0.7; cursor:not-allowed; padding:8px 12px; background:#555; border:none; color:#ccc; }
            #course-preview-canvas .video-container-preview iframe, #course-preview-canvas .video-container-preview video {max-width:100%; border-radius:5px;}
            #course-preview-canvas .markdown-content img {max-width:100%; height:auto; border-radius:5px; margin:10px 0;}
        </style>
    </head>
    <body>
        <div class="header-bar"><h1>🎓 Course Design Studio</h1></div>
        <div class="studio-container">
            <div class="panel" id="left-panel">
                <div class="panel-title">📚 Courses</div>
                <div id="course-list-section"><button id="new-course-btn">New Course</button><ul id="course-list" style="list-style:none; padding-left:0;"></ul></div>
                <hr style="margin: 1rem 0; border-color: rgba(255,107,53,0.2);">
                <div class="panel-title">📦 Modules</div>
                <div id="module-management-section"><button id="add-new-module-btn" style="width:100%; margin-bottom:10px;">Add New Module</button></div>
                <hr style="margin: 1rem 0; border-color: rgba(255,107,53,0.2);">
                <div class="panel-title">➕ Add Element</div>
                <div id="element-palette">
                    <button class="element-btn" data-type="text">📝 Text Content</button>
                    <button class="element-btn" data-type="video">🎥 Video Lesson</button>
                    <button class="element-btn" data-type="quiz">❓ Interactive Quiz</button>
                    <button class="element-btn" data-type="download">📁 Downloadable Resource</button>
                </div>
                <hr style="margin: 1rem 0; border-color: rgba(255,107,53,0.2);">
                <div class="panel-title">🚀 Templates</div>
                <div id="template-palette">
                    <button class="element-btn template-btn" data-template-name="marketing-module">📈 Marketing Module</button>
                    <button class="element-btn template-btn" data-template-name="coding-module">💻 Coding Module</button>
                    <button class="element-btn template-btn" data-template-name="income-module">💰 Income Generation</button>
                </div>
            </div>
            <div class="panel main-canvas-area" id="center-panel">
                <div class="tabs">
                    <button class="tab active" data-tab="design">🎨 Design</button>
                    <button class="tab" data-tab="preview">👁️ Preview</button>
                    <button class="tab" data-tab="settings">⚙️ Settings</button>
                </div>
                <div id="design-tab" class="tab-content active">
                    <div class="panel-title" id="current-course-title">Select or Create a Course</div>
                    <div class="course-canvas" id="course-canvas-main"><p style="text-align:center; color:#777; margin-top:50px;">Select a course to start designing, or create a new one.</p></div>
                </div>
                <div id="preview-tab" class="tab-content">
                    <div class="panel-title">Course Preview</div>
                    <div class="course-canvas" id="course-preview-canvas"><p style="text-align:center; color:#777; margin-top:50px;">Select a course and switch to this tab to see its preview.</p></div>
                </div>
                <div id="settings-tab" class="tab-content">
                    <div class="panel-title">Course Settings</div>
                    <form id="course-settings-form">
                        <div class="form-group"><label for="setting-course-title">Course Title:</label><input type="text" id="setting-course-title" name="name" style="width:95%;"></div>
                        <div class="form-group"><label for="setting-course-description">Description:</label><textarea id="setting-course-description" name="description" rows="4" style="width:95%;"></textarea></div>
                        <div class="form-group"><label for="setting-course-difficulty">Difficulty:</label><select id="setting-course-difficulty" name="difficulty" style="width:95%;"><option value="Beginner">Beginner</option><option value="Intermediate" selected>Intermediate</option><option value="Advanced">Advanced</option></select></div>
                        <div class="form-group"><label for="setting-course-duration">Estimated Duration (e.g., 8 weeks):</label><input type="text" id="setting-course-duration" name="duration" style="width:95%;"></div>
                        <div class="form-group"><label for="setting-course-income">Income Potential (e.g., ₦500K-₦2M):</label><input type="text" id="setting-course-income" name="income_potential" style="width:95%;"></div>
                        <button type="button" id="save-course-settings-btn" class="btn-primary">Save Settings</button>
                    </form>
                </div>
            </div>
            <div class="panel" id="right-panel">
                <div class="panel-title">⚙️ Element Properties</div>
                <div id="properties-editor"><p style="text-align:center; color:#777; margin-top:30px;">Select a lesson element on the canvas to edit its properties.</p></div>
            </div>
        </div>
        <script>
            // --- Basic Modal Structure & Control ---
            const modalContainer = document.createElement('div');
            modalContainer.id = 'form-modal-container';
            Object.assign(modalContainer.style, { display: 'none', position: 'fixed', left: '0', top: '0', width: '100%', height: '100%', backgroundColor: 'rgba(0,0,0,0.7)', zIndex: '1000', justifyContent: 'center', alignItems: 'center', padding: '20px' });
            modalContainer.innerHTML = `<div id="modal-content-box" style="background: #2c2c3e;padding:25px;border-radius:10px;min-width:300px;max-width:600px;box-shadow:0 5px 25px rgba(0,0,0,0.3);display:flex;flex-direction:column;max-height:90vh;"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;flex-shrink:0;"><h3 id="modal-title" style="color:#ff6b35;margin:0;">Modal Title</h3><button id="modal-close-btn" style="background:transparent;border:none;color:white;font-size:1.8rem;cursor:pointer;line-height:1;">&times;</button></div><div id="modal-form-content" style="overflow-y:auto;"></div></div>`;
            document.body.appendChild(modalContainer);
            const modalFormContentEl = document.getElementById('modal-form-content');
            const modalTitleEl = document.getElementById('modal-title');
            document.getElementById('modal-close-btn').onclick = () => closeModal();
            modalContainer.addEventListener('click', function(event) { if (event.target === modalContainer) closeModal(); });
            let currentSubmitCallback = null;
            function openModal(title, formHTML, submitCallback) {
                modalTitleEl.textContent = title;
                modalFormContentEl.innerHTML = formHTML;
                currentSubmitCallback = submitCallback;
                const formInModal = modalFormContentEl.querySelector('form');
                if (formInModal) { formInModal.onsubmit = async (e) => { e.preventDefault(); if(currentSubmitCallback) await currentSubmitCallback(new FormData(formInModal), closeModal); }; }
                modalContainer.style.display = 'flex';
            }
            function closeModal() { modalContainer.style.display = 'none'; modalFormContentEl.innerHTML = ''; currentSubmitCallback = null; }
            // --- End Basic Modal Structure & Control ---

            // --- Template Data ---
            const courseTemplates = {
                "marketing-module": [ { type: 'video', title: 'Intro to AI Marketing', props: { url: '', duration: '10 mins'} }, { type: 'text', title: 'Key Marketing Concepts with AI', props: { markdown_content: '# Key Concepts\\n\\n- AI Persona Generation\\n- Predictive Analytics\\n- Automated Content Creation'} }, { type: 'quiz', title: 'Marketing Basics Quiz', props: { question: 'What is ROI?', options: ['Return on Investment', 'Rate of Inflation', 'Risk of Incarceration'], correct_answer_index: 0 } } ],
                "coding-module": [ { type: 'text', title: 'Setting Up Your Dev Environment', props: { markdown_content: '# Setup Guide\\n\\n1. Install Python\\n2. Install VS Code\\n3. Get API Keys'} }, { type: 'video', title: 'Your First AI "Hello World"', props: { url: '', duration: '15 mins'} } ],
                "income-module": [ { type: 'video', title: 'Monetization Strategies with AI', props: {url: '', duration: '20 mins'} }, { type: 'download', title: 'AI Income Cheatsheet', props: {} }, { type: 'text', title: 'Case Study: AI Freelancing Success', props: { markdown_content: '# Case Study\\n\\nLearn how John Doe makes ₦1M monthly...'}} ]
            };
            // --- End Template Data ---

            function displaySelectedFileName(inputElement, displayElementId) {
                const displayElement = document.getElementById(displayElementId);
                if (displayElement) {
                    if (inputElement.files && inputElement.files.length > 0) {
                        displayElement.textContent = `Selected: ${inputElement.files[0].name}`;
                    } else {
                        displayElement.textContent = '';
                    }
                }
            }

            document.querySelectorAll('.tab').forEach(tab => {
                tab.addEventListener('click', function() {
                    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                    document.querySelectorAll('.tab-content').forEach(tc => tc.classList.remove('active'));

                    this.classList.add('active');
                    const activeTabContent = document.getElementById(this.dataset.tab + '-tab');
                    activeTabContent.classList.add('active');

                    if (this.dataset.tab === 'settings' && currentCourseData) {
                        populateCourseSettingsForm(currentCourseData);
                    } else if (this.dataset.tab === 'preview') {
                        const previewCanvas = activeTabContent.querySelector('.course-canvas') || activeTabContent;
                        if (currentCourseData) {
                            renderCoursePreview(currentCourseData, previewCanvas);
                        } else {
                            previewCanvas.innerHTML = '<p style="padding:20px; text-align:center;">Please select a course to preview.</p>';
                        }
                    }
                });
            });

            function renderCoursePreview(courseData, previewAreaElement) {
                previewAreaElement.innerHTML = '';
                let previewHTML = `<div style="padding:10px; font-size:0.9em; line-height:1.6;">`;
                previewHTML += `<div style="border-bottom: 2px solid #ff6b35; margin-bottom:20px; padding-bottom:15px;">`;
                previewHTML += `<h1 style="color:#ff6b35; text-align:left; margin-bottom:5px; font-size:1.8em;">${courseData.name || 'Course Title'}</h1>`;
                previewHTML += `<p style="color:#ccc; margin-bottom:10px; font-size:0.95em;">${courseData.description || 'No course description.'}</p>`;
                if(courseData.course_settings) {
                    previewHTML += `<p style="font-size:0.8em; color:#aaa;">`;
                    if(courseData.course_settings.difficulty) previewHTML += `Difficulty: ${courseData.course_settings.difficulty} | `;
                    if(courseData.course_settings.duration) previewHTML += `Est. Duration: ${courseData.course_settings.duration}`;
                    if(courseData.course_settings.income_potential) previewHTML += ` | Income: ${courseData.course_settings.income_potential}`;
                    previewHTML += `</p>`;
                }
                previewHTML += `</div>`;

                if (courseData.modules && courseData.modules.length > 0) {
                    const sortedModules = [...courseData.modules].sort((a,b) => a.order_index - b.order_index);
                    sortedModules.forEach(module => {
                        previewHTML += `<div class="module-preview-item"><h3>${module.name}</h3>`;
                        const lessonsInModule = (courseData.lessons || []).filter(l => l.module_id === module.id).sort((a,b) => a.order_index - b.order_index);
                        if (lessonsInModule.length > 0) {
                            previewHTML += '<ul style="list-style:none; padding-left:0;">';
                            lessonsInModule.forEach(lesson => {
                                previewHTML += `<li class="lesson-preview-item"><h4>${lesson.lesson} <span style="font-size:0.8em; color:#aaa;">(${lesson.content_type})</span></h4>`;
                                const props = lesson.element_properties || {};
                                switch(lesson.content_type) {
                                    case 'text': case 'markdown':
                                        const mdContent = props.markdown_content || lesson.description || '';
                                        try { previewHTML += marked.parse(mdContent || ''); } catch(e){ previewHTML += `<pre style="color:red">Error rendering markdown: ${e.message}</pre>`}
                                        break;
                                    case 'video':
                                        if (props.url && props.url.trim()) {
                                            if (props.url.includes("youtube.com/watch?v=") || props.url.includes("youtu.be/")) {
                                                const videoId = props.url.includes("youtu.be/") ? props.url.split("youtu.be/")[1].split("?")[0] : props.url.split("v=")[1].split("&")[0];
                                                previewHTML += `<div class="video-container-preview" style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%; background:#000; border-radius:5px;"><iframe src="https://www.youtube.com/embed/${videoId}" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: 0;" allowfullscreen></iframe></div>`;
                                            } else { previewHTML += `<div class="video-container-preview"><video controls width="100%"><source src="${props.url}">Not supported.</video></div>`; }
                                        } else if (lesson.file_path) {
                                            const videoFileUrl = "{{ url_for('static', filename='placeholder.mp4') }}".replace('placeholder.mp4', (lesson.file_path.startsWith('static/') ? lesson.file_path.substring(7) : lesson.file_path).replace(/\\\\/g, '/'));
                                            previewHTML += `<div class="video-container-preview"><p style="color:#aaa;"><i>Video File: ${lesson.file_path.split('/').pop()}</i></p><video controls width="100%"><source src="${videoFileUrl}" type="video/${lesson.file_path.split('.').pop()}">Not supported.</video></div>`;
                                        } else { previewHTML += `<p style="color:#aaa;"><i>Video content not configured.</i></p>`; }
                                        if(props.duration) previewHTML += `<p style="font-size:0.8em; color:#aaa; margin-top:5px;">Duration: ${props.duration}</p>`;
                                        break;
                                    case 'quiz':
                                        previewHTML += `<div style="border:1px solid #444; padding:10px; border-radius:4px;"><strong>Quiz:</strong> ${props.question || 'N/A'}`;
                                        if (props.options && props.options.length > 0) {
                                            previewHTML += `<ul style="margin-top:5px; padding-left:20px;">`;
                                            props.options.forEach(opt => previewHTML += `<li>${opt}</li>`);
                                            previewHTML += `</ul>`;
                                        } previewHTML += `</div>`; break;
                                    case 'download':
                                        if (lesson.file_path) {
                                            const downloadFileUrl = "{{ url_for('static', filename='placeholder.zip') }}".replace('placeholder.zip', (lesson.file_path.startsWith('static/') ? lesson.file_path.substring(7) : lesson.file_path).replace(/\\\\/g, '/'));
                                            previewHTML += `<p><a href="${downloadFileUrl}" download class="download-btn" style="opacity:1; cursor:pointer; background-color:#ff6b35;">Download: ${lesson.file_path.split('/').pop()}</a></p>`;
                                        } else { previewHTML += `<p style="color:#aaa;"><i>Downloadable file not configured.</i></p>`; }
                                        break;
                                    default: previewHTML += `<p style="color:#aaa;"><i>Preview for '${lesson.content_type}' not fully implemented.</i></p>`;
                                }
                                previewHTML += `</li>`;
                            });
                            previewHTML += '</ul>';
                        } else { previewHTML += '<p style="margin-left:20px; font-style:italic; color:#aaa;">No lessons in this module.</p>'; }
                        previewHTML += `</div>`;
                    });
                } else { previewHTML += '<p style="font-style:italic; color:#aaa; text-align:center; margin-top:20px;">This course has no modules defined yet.</p>';}
                previewHTML += `</div>`;
                previewAreaElement.innerHTML = previewHTML;
            }

            let selectedCourseId = null;
            const courseListUl = document.getElementById('course-list');
            const newCourseBtn = document.getElementById('new-course-btn');
            const currentCourseTitleEl = document.getElementById('current-course-title');
            const courseSettingsForm = document.getElementById('course-settings-form');
            const settingCourseTitleInput = document.getElementById('setting-course-title');
            const settingCourseDescriptionInput = document.getElementById('setting-course-description');
            const settingCourseDifficultyInput = document.getElementById('setting-course-difficulty');
            const settingCourseDurationInput = document.getElementById('setting-course-duration');
            const settingCourseIncomeInput = document.getElementById('setting-course-income');
            const saveCourseSettingsBtn = document.getElementById('save-course-settings-btn');

            async function fetchCourses() {
                try {
                    const response = await fetch('/api/admin/courses');
                    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                    const courses = await response.json();
                    renderCourseList(courses);
                } catch (error) { console.error("Failed to fetch courses:", error); courseListUl.innerHTML = '<li>Error loading courses.</li>';}
            }

            function renderCourseList(courses) {
                courseListUl.innerHTML = '';
                if (courses.length === 0) { courseListUl.innerHTML = '<li>No courses yet. Create one!</li>'; return; }
                courses.forEach(course => {
                    const li = document.createElement('li');
                    li.textContent = course.name;
                    li.style.cursor = 'pointer'; li.style.padding = '5px 0'; li.dataset.courseId = course.id;
                    li.addEventListener('click', () => loadCourse(course.id, course.name));
                    courseListUl.appendChild(li);
                });
            }

            let currentCourseData = null;

            async function loadCourse(courseId, courseName) {
                selectedCourseId = courseId; window.selectedCourseId = courseId;
                currentCourseTitleEl.textContent = `Editing: ${courseName}`;
                document.getElementById('course-canvas-main').innerHTML = '<p>Loading course content...</p>';
                propertiesEditor.innerHTML = '<p style="text-align:center; color:#777; margin-top:30px;">Select an element to edit its properties.</p>';
                if (easyMDEInstance) { easyMDEInstance.toTextArea(); easyMDEInstance = null; }
                try {
                    const courseResponse = await fetch(`/api/admin/courses/${courseId}`);
                    if (!courseResponse.ok) throw new Error(`HTTP error! status: ${courseResponse.status} (fetching course)`);
                    currentCourseData = await courseResponse.json();
                    renderCourseContent(currentCourseData.lessons || [], currentCourseData.modules || []);
                    if (document.querySelector('.tab[data-tab="settings"]').classList.contains('active')) populateCourseSettingsForm(currentCourseData);
                    if (document.querySelector('.tab[data-tab="preview"]').classList.contains('active')) renderCoursePreview(currentCourseData, document.getElementById('course-preview-canvas'));
                } catch (error) {
                    console.error(`Failed to load course content for ${courseName}:`, error);
                    document.getElementById('course-canvas-main').innerHTML = `<p>Error loading content for ${courseName}: ${error.message}</p>`;
                    currentCourseData = null;
                }
            }

            function renderCourseContent(lessons, modules) {
                const canvas = document.getElementById('course-canvas-main');
                canvas.innerHTML = '';
                if (!modules || modules.length === 0) { canvas.innerHTML = '<p style="text-align:center; color:#777; margin-top:30px;">This course has no modules. <br><button onclick="document.getElementById(\'add-new-module-btn\').click();" style="margin-top:10px;">Add First Module</button></p>'; return; }
                const sortedModules = [...modules].sort((a,b) => a.order_index - b.order_index);
                sortedModules.forEach(module => {
                    const moduleDiv = document.createElement('div');
                    Object.assign(moduleDiv, { className: 'module-container', dataset: { moduleId: module.id, moduleOrderIndex: module.order_index }, draggable: true, style: "cursor:move; border:1px dashed #777; padding:15px; margin-bottom:15px; border-radius:5px;" });
                    moduleDiv.addEventListener('dragstart', (e) => { if (e.target === moduleDiv) { draggedModuleId = module.id; e.dataTransfer.setData('text/module-id', module.id); e.target.style.opacity = '0.5'; e.target.classList.add('dragging-item'); draggedLessonId = null; }});
                    moduleDiv.innerHTML = `<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                                               <h3 style="color:#ff8c42; margin-top:0; margin-bottom:0;">${module.name}</h3>
                                               <div>
                                                   <button class="edit-module-btn" data-module-id="${module.id}" data-module-name="${module.name}" data-module-desc="${module.description || ''}" data-module-order="${module.order_index}" style="font-size:0.8em; padding:3px 8px; margin-right: 5px;">Edit Module</button>
                                                   <button class="delete-module-btn" data-module-id="${module.id}" style="font-size:0.8em; padding:3px 8px; background-color:#d9534f;">Delete Module</button>
                                               </div>
                                           </div>`;
                    const lessonsInModule = (lessons || []).filter(l => l.module_id === module.id).sort((a,b) => a.order_index - b.order_index);
                    const lessonsContainer = document.createElement('div');
                    lessonsContainer.className = 'lessons-in-module-container';
                    if (lessonsInModule.length === 0) lessonsContainer.innerHTML = '<p style="font-style:italic; color:#aaa;">No lessons in this module yet.</p>';
                    lessonsInModule.forEach(lesson => {
                        const lessonDiv = document.createElement('div');
                        Object.assign(lessonDiv, { className: 'lesson-element-item', draggable: true, dataset: { lessonId: lesson.id, moduleId: module.id, originalOrder: lesson.order_index }, style: "border:1px solid #555; padding:8px; margin-bottom:5px; border-radius:4px; background-color:rgba(255,255,255,0.05); cursor:grab;" });
                        let lessonContentHTML = `<div style="display:flex; justify-content:space-between; align-items:center;"><span><strong>${lesson.lesson}</strong> <span style="font-size:0.8em; color:#ccc;">(${lesson.content_type})</span></span>`;
                        const controlsDiv = document.createElement('div'); controlsDiv.style.whiteSpace = 'nowrap';
                        const upButton = document.createElement('button'); Object.assign(upButton, { innerHTML: '&#x25B2;', title: "Move Up", style: "margin-left:10px; padding:2px 5px;", onclick: (e) => { e.stopPropagation(); moveLesson(lesson.id, 'up'); } });
                        const downButton = document.createElement('button'); Object.assign(downButton, { innerHTML: '&#x25BC;', title: "Move Down", style: "margin-left:5px; padding:2px 5px;", onclick: (e) => { e.stopPropagation(); moveLesson(lesson.id, 'down'); } });
                        controlsDiv.append(upButton, downButton);
                        lessonDiv.innerHTML = lessonContentHTML; lessonDiv.appendChild(controlsDiv);
                        lessonDiv.addEventListener('click', (e) => { if(!e.target.closest('button')) selectLessonElement(lesson); });
                        lessonDiv.addEventListener('dragstart', (e) => { e.stopPropagation(); draggedLessonId = lesson.id; draggedLessonOriginalModuleId = lesson.module_id; e.dataTransfer.setData('text/lesson-id', lesson.id); e.target.style.opacity = '0.5'; e.target.classList.add('dragging-item'); draggedModuleId = null; });
                        lessonsContainer.appendChild(lessonDiv);
                    });
                    moduleDiv.appendChild(lessonsContainer);
                    canvas.appendChild(moduleDiv);
                });
            }

            let currentSelectedLesson = null; let easyMDEInstance = null;
            const propertiesEditor = document.getElementById('properties-editor');

            function selectLessonElement(lessonData) {
                currentSelectedLesson = lessonData;
                if (easyMDEInstance) { easyMDEInstance.toTextArea(); easyMDEInstance = null; }
                document.querySelectorAll('.lesson-element-item').forEach(el => { el.style.backgroundColor = 'rgba(255,255,255,0.05)'; el.style.border = '1px solid #555'; });
                const selectedDiv = document.querySelector(`.lesson-element-item[data-lesson-id='${lessonData.id}']`);
                if(selectedDiv) { selectedDiv.style.backgroundColor = 'rgba(255,107,53,0.2)'; selectedDiv.style.border = '1px solid #ff6b35';}
                renderPropertiesForm(lessonData);
            }

            function renderPropertiesForm(lesson) {
                propertiesEditor.innerHTML = '';
                if (easyMDEInstance) { easyMDEInstance.toTextArea(); easyMDEInstance = null; }
                const form = document.createElement('form');
                Object.assign(form, { id: 'lesson-properties-form', style: "padding:5px;", onsubmit: (e) => { e.preventDefault(); handleUpdateLesson(); } });
                form.innerHTML = `<h4 style="margin-bottom:15px;">Edit: ${lesson.lesson}</h4><input type="hidden" name="lesson_id" value="${lesson.id}"><div class="form-group"><label for="prop-lesson-title">Lesson Title:</label><input type="text" id="prop-lesson-title" name="lesson_title" value="${lesson.lesson}" required style="width:95%;"></div>`;
                let moduleDropdownHTML = '<div class="form-group"><label for="prop-module-id">Module:</label><select id="prop-module-id" name="module_id" required style="width:95%;">';
                if (currentCourseData && currentCourseData.modules) currentCourseData.modules.forEach(mod => { moduleDropdownHTML += `<option value="${mod.id}" ${lesson.module_id === mod.id ? 'selected':''}>${mod.name}</option>`; });
                else moduleDropdownHTML += `<option value="${lesson.module_id}" selected>${lesson.module_name || 'Unknown'}</option>`;
                moduleDropdownHTML += '</select></div>'; form.innerHTML += moduleDropdownHTML;
                form.innerHTML += `<div class="form-group"><label for="prop-order-index">Order Index:</label><input type="number" id="prop-order-index" name="order_index" value="${lesson.order_index}" min="1" required style="width:95%;"></div><div class="form-group"><label>Content Type:</label><input type="text" value="${lesson.content_type}" readonly style="width:95%;background-color:#333;"><input type="hidden" name="content_type" value="${lesson.content_type}"></div>`;
                switch (lesson.content_type) {
                    case 'text': const tid = `easymde-editor-prop`; form.innerHTML += `<div class="form-group"><label for="${tid}">Markdown Content:</label><textarea id="${tid}" name="markdown_content_editor">${lesson.element_properties.markdown_content||''}</textarea></div>`; setTimeout(() => { if(document.getElementById(tid)) easyMDEInstance = new EasyMDE({element:document.getElementById(tid), spellChecker:false, status:false, initialValue:lesson.element_properties.markdown_content||'', toolbar:["bold","italic","heading","|","quote","unordered-list","ordered-list","|","link","image","|","preview","side-by-side","fullscreen"]});},0); break;
                    case 'video':
                        form.innerHTML += `<div class="form-group"><label for="prop-video-url">Video URL:</label><input id="prop-video-url" type="url" name="video_url" value="${lesson.element_properties.url||''}" style="width:95%;"></div><div class="form-group"><label for="prop-video-duration">Duration:</label><input id="prop-video-duration" type="text" name="video_duration" value="${lesson.element_properties.duration||''}" style="width:95%;"></div>`;
                        if(lesson.file_path) form.innerHTML += `<div class="form-group" id="current-video-file-display-${lesson.id}"><p style="font-size:0.85em;color:#ccc;">File: <strong>${lesson.file_path.split('/').pop()}</strong> <button type="button" class="clear-file-btn" data-lesson-id="${lesson.id}" data-for-input="prop-video-file" data-display-id="selected-video-file-name-${lesson.id}" data-label-id="prop-video-file-label-${lesson.id}" style="font-size:0.8em;padding:2px 5px;background-color:#777;margin-left:5px;">Clear</button></p></div>`;
                        form.innerHTML += `<div class="form-group"><label for="prop-video-file" id="prop-video-file-label-${lesson.id}">${lesson.file_path?'Replace':'Upload'} Video File:</label><input id="prop-video-file" type="file" name="file" accept="video/*" onchange="displaySelectedFileName(this,'selected-video-file-name-${lesson.id}')"></div><p id="selected-video-file-name-${lesson.id}" style="font-size:0.8em;color:#ffaf87;"></p>`;
                        break;
                    case 'quiz': form.innerHTML += `<div class="form-group"><label for="prop-quiz-question">Question:</label><textarea id="prop-quiz-question" name="quiz_question" rows="3" style="width:95%;">${lesson.element_properties.question||''}</textarea></div><div class="form-group"><label for="prop-quiz-options">Options (one/line):</label><textarea id="prop-quiz-options" name="quiz_options" rows="4" style="width:95%;">${(lesson.element_properties.options||[]).join('\\n')}</textarea></div><div class="form-group"><label for="prop-quiz-correct">Correct Index (0-based):</label><input id="prop-quiz-correct" type="number" name="quiz_correct_answer_index" value="${lesson.element_properties.correct_answer_index||0}" min="0" style="width:95%;"></div>`; break;
                    case 'download':
                        if(lesson.file_path) form.innerHTML += `<div class="form-group" id="current-download-file-display-${lesson.id}"><p style="font-size:0.85em;color:#ccc;">File: <strong>${lesson.file_path.split('/').pop()}</strong> <button type="button" class="clear-file-btn" data-lesson-id="${lesson.id}" data-for-input="prop-download-file" data-display-id="selected-download-file-name-${lesson.id}" data-label-id="prop-download-file-label-${lesson.id}" style="font-size:0.8em;padding:2px 5px;background-color:#777;margin-left:5px;">Clear</button></p></div>`;
                        form.innerHTML += `<div class="form-group"><label for="prop-download-file" id="prop-download-file-label-${lesson.id}">${lesson.file_path?'Replace':'Upload'} File:</label><input id="prop-download-file" type="file" name="file" onchange="displaySelectedFileName(this,'selected-download-file-name-${lesson.id}')"></div><p id="selected-download-file-name-${lesson.id}" style="font-size:0.8em;color:#ffaf87;"></p>`;
                        break;
                }
                form.innerHTML += '<button type="submit" class="btn-primary" style="margin-right:10px;width:auto;padding:0.6em 1.2em;">Update Lesson</button>';
                const deleteBtn = document.createElement('button'); Object.assign(deleteBtn, {type:'button', textContent:'Delete Lesson', className:'btn-primary', style:"background-color:#d9534f;width:auto;padding:0.6em 1.2em;", onclick:()=>handleDeleteLesson()}); form.appendChild(deleteBtn);
                propertiesEditor.appendChild(form);
            }

            async function handleDeleteLesson() {
                if (!currentSelectedLesson || !confirm(`Delete "${currentSelectedLesson.lesson}"?`)) return;
                try {
                    const response = await fetch(`/api/admin/lessons/${currentSelectedLesson.id}`,{method:'DELETE'});
                    if (!response.ok) throw new Error((await response.json()).error || 'Failed to delete');
                    alert('Lesson deleted!');
                    if(selectedCourseId && currentCourseData) loadCourse(selectedCourseId, currentCourseData.name);
                    propertiesEditor.innerHTML = '<p style="text-align:center; color:#777; margin-top:30px;">Select an element to edit.</p>';
                    currentSelectedLesson = null; if (easyMDEInstance){easyMDEInstance.toTextArea(); easyMDEInstance=null;}
                } catch (error) { console.error("Failed to delete lesson:",error); alert(`Error: ${error.message}`); }
            }

            async function handleUpdateLesson() {
                if (!currentSelectedLesson) return;
                const form = document.getElementById('lesson-properties-form');
                const formData = new FormData(form);
                if (form.querySelector('input[name="clear_file_flag"]')?.value === 'true') {
                    formData.append('clear_file', 'true');
                }

                let elementProps = {};
                switch (currentSelectedLesson.content_type) {
                    case 'text': elementProps.markdown_content = easyMDEInstance ? easyMDEInstance.value() : formData.get('markdown_content_editor'); break;
                    case 'video': elementProps.url = formData.get('video_url'); elementProps.duration = formData.get('video_duration'); break;
                    case 'quiz': elementProps.question = formData.get('quiz_question'); elementProps.options = formData.get('quiz_options').split('\\n').map(o=>o.trim()).filter(o=>o); elementProps.correct_answer_index = parseInt(formData.get('quiz_correct_answer_index')); break;
                }
                formData.append('element_properties', JSON.stringify(elementProps));
                ['markdown_content_editor','video_url','video_duration','quiz_question','quiz_options','quiz_correct_answer_index'].forEach(k=>formData.delete(k));
                try {
                    const response = await fetch(`/api/admin/lessons/${currentSelectedLesson.id}`, {method:'PUT', body:formData});
                    if (!response.ok) throw new Error((await response.json()).error || 'Failed to update');
                    alert('Lesson updated!');
                    if(selectedCourseId&&currentCourseData)loadCourse(selectedCourseId, currentCourseData.name);
                    propertiesEditor.innerHTML = '<p style="text-align:center; color:#777; margin-top:30px;">Select an element to edit.</p>';
                    currentSelectedLesson=null; if(easyMDEInstance){easyMDEInstance.toTextArea();easyMDEInstance=null;}
                } catch (error) { console.error("Failed to update lesson:", error); alert(`Error: ${error.message}`); }
            }

            function populateCourseSettingsForm(course) {
                settingCourseTitleInput.value = course.name || '';
                settingCourseDescriptionInput.value = course.description || '';
                const settings = course.course_settings || {};
                settingCourseDifficultyInput.value = settings.difficulty || 'Intermediate';
                settingCourseDurationInput.value = settings.duration || '';
                settingCourseIncomeInput.value = settings.income_potential || '';
            }

            async function loadCourseSettings(courseId) {
                if (!courseId) return;
                if (currentCourseData && currentCourseData.id === courseId) { populateCourseSettingsForm(currentCourseData); return; }
                try {
                    const response = await fetch(`/api/admin/courses/${courseId}`);
                    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                    populateCourseSettingsForm(await response.json());
                } catch (error) { console.error("Failed to load course settings:", error); alert("Error loading course settings.");}
            }

            newCourseBtn.addEventListener('click', () => {
                const formHTML = `<form id="new-course-modal-form" style="display:flex;flex-direction:column;gap:10px;"><div class="form-group"><label for="modal-course-name">Name:</label><input type="text" id="modal-course-name" name="name" r style="width:98%;"></div><div class="form-group"><label for="modal-course-description">Description:</label><textarea id="modal-course-description" name="description" rows="3" style="width:98%;"></textarea></div><div class="form-group"><label for="modal-course-difficulty">Difficulty:</label><select id="modal-course-difficulty" name="difficulty" style="width:98%;"><option value="Beginner">Beginner</option><option value="Intermediate" selected>Intermediate</option><option value="Advanced">Advanced</option></select></div><div class="form-group"><label for="modal-course-duration">Est. Duration:</label><input type="text" id="modal-course-duration" name="duration" style="width:98%;"></div><div class="form-group"><label for="modal-course-income">Income Potential:</label><input type="text" id="modal-course-income" name="income_potential" style="width:98%;"></div><button type="submit" class="btn-primary" style="width:100%;">Create Course</button></form>`;
                const submitNewCourse = async (formData, closeModalCallback) => {
                    const s = {difficulty:formData.get('difficulty'),duration:formData.get('duration'),income_potential:formData.get('income_potential')};
                    try {
                        const response = await fetch('/api/admin/courses',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:formData.get('name'),description:formData.get('description'),settings:s})});
                        if(!response.ok)throw new Error((await response.json()).error || 'Failed to create');
                        fetchCourses(); alert('Course created!'); if(closeModalCallback)closeModalCallback();
                    } catch (error) { console.error("Failed to create course:",error);alert(`Error: ${error.message}`);}
                };
                openModal("Create New Course", formHTML, submitNewCourse);
            });

            saveCourseSettingsBtn.addEventListener('click', async () => {
                if (!selectedCourseId) { alert("No course selected."); return; }
                const payload = {name:settingCourseTitleInput.value,description:settingCourseDescriptionInput.value,settings:{difficulty:settingCourseDifficultyInput.value,duration:settingCourseDurationInput.value,income_potential:settingCourseIncomeInput.value}};
                try {
                    const response = await fetch(`/api/admin/courses/${selectedCourseId}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
                    if(!response.ok) throw new Error((await response.json()).error || 'Failed to save');
                    alert('Settings saved!'); fetchCourses(); currentCourseTitleEl.textContent = `Editing: ${payload.name}`;
                    if(currentCourseData&&currentCourseData.id===selectedCourseId){currentCourseData.name=payload.name;currentCourseData.description=payload.description;currentCourseData.course_settings=payload.settings;}
                } catch (error) { console.error("Failed to save settings:",error);alert(`Error: ${error.message}`);}
            });

            const addNewModuleBtn = document.getElementById('add-new-module-btn');
            addNewModuleBtn.addEventListener('click', () => {
                if (!selectedCourseId) { alert("Select a course first."); return; }
                const order = (currentCourseData&&currentCourseData.modules)?currentCourseData.modules.length+1:1;
                const formHTML = `<form id="add-module-modal-form" style="display:flex;flex-direction:column;gap:10px;"><div class="form-group"><label for="modal-module-name">Name:</label><input type="text" id="modal-module-name" name="name" r style="width:98%;"></div><div class="form-group"><label for="modal-module-description">Description:</label><textarea id="modal-module-description" name="description" rows="3" style="width:98%;"></textarea></div><div class="form-group"><label for="modal-module-order">Order:</label><input type="number" id="modal-module-order" name="order_index" value="${order}" min="1" r style="width:98%;"></div><button type="submit" class="btn-primary" style="width:100%;">Create Module</button></form>`;
                const submitNewModule = async (formData, closeModalCallback) => {
                    try {
                        const response = await fetch(`/api/admin/courses/${selectedCourseId}/modules`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:formData.get('name'),description:formData.get('description'),order_index:parseInt(formData.get('order_index'))})});
                        if(!response.ok) throw new Error((await response.json()).error||'Failed to create');
                        alert('Module created!'); if(currentCourseData)loadCourse(selectedCourseId,currentCourseData.name); else fetchCourses();
                        if(closeModalCallback)closeModalCallback();
                    } catch (error) { console.error("Failed to create module:",error);alert(`Error: ${error.message}`);}
                };
                openModal("Add New Module", formHTML, submitNewModule);
            });

            const mainCanvas = document.getElementById('course-canvas-main');

            propertiesEditorEl.addEventListener('click', function(event) {
                if (event.target.classList.contains('clear-file-btn')) {
                    const button = event.target;
                    const fileInputId = button.dataset.forInput;
                    const displayId = button.dataset.displayId;
                    const labelId = button.dataset.labelId;

                    const fileInput = document.getElementById(fileInputId);
                    if (fileInput) fileInput.value = null;

                    const fileNameDisplay = document.getElementById(displayId);
                    if (fileNameDisplay) fileNameDisplay.textContent = '';

                    const form = button.closest('form');
                    if (form) {
                        let clearFlagInput = form.querySelector('input[name="clear_file_flag"]');
                        if (!clearFlagInput) {
                            clearFlagInput = document.createElement('input');
                            clearFlagInput.type = 'hidden';
                            clearFlagInput.name = 'clear_file_flag';
                            clearFlagInput.id = 'clear-file-flag-input';
                            form.appendChild(clearFlagInput);
                        }
                        clearFlagInput.value = 'true';
                    }

                    const parentP = button.closest('p');
                    if(parentP) parentP.style.display = 'none';

                    const label = document.getElementById(labelId);
                    if(label && label.textContent.includes('Replace')) label.textContent = label.textContent.replace('Replace', 'Upload');
                     else if(label && label.textContent.includes('Current')) label.textContent = label.textContent.replace('Current', 'Upload');


                } else if (event.target.classList.contains('edit-module-btn')) {
                     // Edit module buttons are on the canvas, not in properties editor. This part can be removed.
                }
            });

             mainCanvas.addEventListener('click', function(event) {
                if (event.target.classList.contains('edit-module-btn') && !event.target.closest('#properties-editor')) {
                    const button = event.target;
                    handleEditModuleClick(button.dataset.moduleId, button.dataset.moduleName, button.dataset.moduleDesc, button.dataset.moduleOrder);
                } else if (event.target.classList.contains('delete-module-btn')) {
                    const button = event.target;
                    const moduleId = button.dataset.moduleId;
                    const moduleContainer = button.closest('.module-container');
                    const moduleName = moduleContainer ? (moduleContainer.querySelector('h3')?.textContent || 'this module') : 'this module';

                    if (confirm(`Are you sure you want to delete the module "${moduleName}"? This action cannot be undone and will fail if the module contains lessons.`)) {
                        fetch(`/api/admin/modules/${moduleId}`, {
                            method: 'DELETE',
                            headers: {
                                'Content-Type': 'application/json'
                            }
                        })
                        .then(response => {
                            if (!response.ok) {
                                // Try to parse error JSON, otherwise use status text
                                return response.json().then(err => { throw new Error(err.error || `HTTP error! Status: ${response.status}`); })
                                                   .catch(() => { throw new Error(`HTTP error! Status: ${response.status}`); });
                            }
                            return response.json();
                        })
                        .then(data => {
                            alert(data.message || 'Module deleted successfully!');
                            if (selectedCourseId && currentCourseData) {
                                loadCourse(selectedCourseId, currentCourseData.name);
                            }
                        })
                        .catch(error => {
                            console.error('Failed to delete module:', error);
                            alert(`Error deleting module: ${error.message}`);
                        });
                    }
                }
            });


            let draggedLessonId = null; let draggedLessonOriginalModuleId = null; let draggedModuleId = null;

            mainCanvas.addEventListener('dragstart', function(event) {
                const target = event.target;
                if (target.classList.contains('lesson-element-item')) {
                    draggedLessonId = target.dataset.lessonId; draggedLessonOriginalModuleId = target.dataset.moduleId;
                    event.dataTransfer.setData('text/lesson-id', draggedLessonId);
                    target.style.opacity='0.5'; target.classList.add('dragging-item'); draggedModuleId=null;
                } else if (target.classList.contains('module-container')) {
                    draggedModuleId = target.dataset.moduleId; event.dataTransfer.setData('text/module-id', draggedModuleId);
                    target.style.opacity='0.5'; target.classList.add('dragging-item'); draggedLessonId=null;
                }
            });

            mainCanvas.addEventListener('dragend', function(event) {
                const target = event.target;
                if (target.classList.contains('lesson-element-item')||target.classList.contains('module-container')) {target.style.opacity='1';target.classList.remove('dragging-item');}
                draggedLessonId=null;draggedLessonOriginalModuleId=null;draggedModuleId=null;
                document.querySelectorAll('.drop-target-highlight,.lesson-drop-indicator,.module-drop-indicator').forEach(el=>el.remove());
            });

            mainCanvas.addEventListener('dragover', function(event) {
                event.preventDefault();
                document.querySelectorAll('.lesson-drop-indicator,.module-drop-indicator,.drop-target-highlight').forEach(el=>el.remove());
                if (draggedLessonId) {
                    const ctm = event.target.closest('.module-container');
                    if (ctm) {
                        ctm.classList.add('drop-target-highlight');
                        let lip = false;
                        const lis = Array.from(ctm.querySelectorAll('.lesson-element-item'));
                        for (const i of lis) { if (i.dataset.lessonId===draggedLessonId && i.style.opacity==='0.5') continue; const r=i.getBoundingClientRect(); if (event.clientY<r.top+r.height/2){i.insertAdjacentHTML('beforebegin','<div class="lesson-drop-indicator"></div>');lip=true;break;}}
                        if (!lip) (ctm.querySelector('.lessons-in-module-container')||ctm).insertAdjacentHTML('beforeend','<div class="lesson-drop-indicator"></div>');
                    }
                } else if (draggedModuleId) {
                    const mis = Array.from(mainCanvas.querySelectorAll('.module-container'));
                    let mip = false;
                    for (const i of mis) { if (i.dataset.moduleId===draggedModuleId && i.style.opacity==='0.5') continue; const r=i.getBoundingClientRect(); if (event.clientY<r.top+r.height/2){i.insertAdjacentHTML('beforebegin','<div class="module-drop-indicator"></div>');mip=true;break;}}
                    if (!mip) { let cpae=true; if(mis.length>0&&mis[mis.length-1].dataset.moduleId===draggedModuleId&&mis.length===1){} else if(mis.length>0&&mis[mis.length-1].dataset.moduleId===draggedModuleId)cpae=false; if(cpae||mis.length===0)mainCanvas.insertAdjacentHTML('beforeend','<div class="module-drop-indicator"></div>'); else if(mis.length===1&&mis[0].dataset.moduleId===draggedModuleId&&!mainCanvas.querySelector('.module-drop-indicator'))mainCanvas.insertAdjacentHTML('afterbegin','<div class="module-drop-indicator"></div>');}
                }
            });

            function removeModuleDropIndicators(){ document.querySelectorAll('.module-drop-indicator').forEach(el=>el.remove());}
            mainCanvas.addEventListener('dragleave', function(event) {});

            mainCanvas.addEventListener('drop', async function(event) {
                event.preventDefault();
                const activeLessonDropIndicator = mainCanvas.querySelector('.lesson-drop-indicator');
                const activeModuleDropIndicator = mainCanvas.querySelector('.module-drop-indicator');
                document.querySelectorAll('.drop-target-highlight').forEach(el=>el.classList.remove('drop-target-highlight'));
                if(activeLessonDropIndicator)activeLessonDropIndicator.remove(); if(activeModuleDropIndicator)activeModuleDropIndicator.remove();

                if (draggedLessonId && currentCourseData && currentCourseData.lessons) {
                    let tcfld = event.target.closest('.module-container');
                    if(!tcfld && activeLessonDropIndicator && activeLessonDropIndicator.parentElement.classList.contains('module-container')) tcfld=activeLessonDropIndicator.parentElement;
                    if(!tcfld && activeLessonDropIndicator && activeLessonDropIndicator.parentElement.classList.contains('lessons-in-module-container')) tcfld=activeLessonDropIndicator.parentElement.closest('.module-container');
                    if(!tcfld){console.log("LDrop:No valid module container.");draggedLessonId=null;draggedLessonOriginalModuleId=null;return;}
                    const tmi = parseInt(tcfld.dataset.moduleId); const ltu=[];
                    const dl = currentCourseData.lessons.find(l=>l.id==draggedLessonId);
                    if(!dl){console.error("Dragged lesson not found.");return;}
                    const omi = dl.module_id; dl.module_id = tmi;
                    let lintm = currentCourseData.lessons.filter(l=>l.module_id===tmi && l.id!=draggedLessonId).sort((a,b)=>a.order_index-b.order_index);
                    let iai = lintm.length;
                    if (activeLessonDropIndicator) { const ne=activeLessonDropIndicator.nextElementSibling; if (ne&&ne.classList.contains('lesson-element-item')){ const nei=ne.dataset.lessonId; const fi=lintm.findIndex(l=>l.id==nei); if(fi!==-1)iai=fi;}}
                    lintm.splice(iai,0,dl);
                    lintm.forEach((l,i)=>{const noi=i+1; if(l.order_index!==noi||l.module_id!==tmi){l.order_index=noi;l.module_id=tmi;ltu.push({id:l.id,order_index:l.order_index,module_id:l.module_id});}});
                    if(omi!==tmi){currentCourseData.lessons.filter(l=>l.module_id===omi&&l.id!=draggedLessonId).sort((a,b)=>a.order_index-b.order_index).forEach((l,i)=>{const noi=i+1;if(l.order_index!==noi){l.order_index=noi;constex=ltu.find(u=>u.id===l.id);if(ex)ex.order_index=noi;else ltu.push({id:l.id,order_index:noi,module_id:l.module_id});}});}
                    if(ltu.length>0){for(const lu of ltu){try{const ur=await fetch(`/api/admin/lessons/${lu.id}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({order_index:lu.order_index,module_id:lu.module_id})});if(!ur.ok)console.error(`Failed L${lu.id}`);}catch(e){console.error(`Error L${lu.id}`,e);}}}
                    if(selectedCourseId&&currentCourseData)loadCourse(selectedCourseId,currentCourseData.name);
                } else if (draggedModuleId && currentCourseData && currentCourseData.modules) {
                    const mtu=[]; let cmo=[...currentCourseData.modules].sort((a,b)=>a.order_index-b.order_index);
                    const dmd=cmo.find(m=>m.id==draggedModuleId);
                    if(!dmd){console.error("Dragged module not found");return;}
                    cmo=cmo.filter(m=>m.id!=draggedModuleId);
                    let iai=cmo.length; if(activeModuleDropIndicator){const ne=activeModuleDropIndicator.nextElementSibling; if(ne&&ne.classList.contains('module-container')){const nei=ne.dataset.moduleId;const fi=cmo.findIndex(m=>m.id==nei);if(fi!==-1)iai=fi;}else if(!activeModuleDropIndicator.previousElementSibling||(activeModuleDropIndicator.previousElementSibling&&!activeModuleDropIndicator.previousElementSibling.classList.contains('module-container')))iai=0;}
                    cmo.splice(iai,0,dmd);
                    cmo.forEach((m,i)=>{const noi=i+1;if(m.order_index!==noi){m.order_index=noi;mtu.push({id:m.id,order_index:m.order_index});}});
                    if(mtu.length>0){for(const mu of mtu){try{const ur=await fetch(`/api/admin/modules/${mu.id}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({order_index:mu.order_index})});if(!ur.ok)console.error(`Failed M${mu.id}`);}catch(e){console.error(`Error M${mu.id}`,e);}}}
                    if(selectedCourseId&&currentCourseData)loadCourse(selectedCourseId,currentCourseData.name);
                }
                draggedLessonId=null;draggedLessonOriginalModuleId=null;draggedModuleId=null;
            });

            const elementPalette = document.getElementById('element-palette');
            elementPalette.addEventListener('click', function(event) {
                if (event.target.classList.contains('element-btn') && !event.target.classList.contains('template-btn')) {
                    const elementType = event.target.dataset.type;
                    handleAddElementFromPalette(elementType);
                }
            });

            function handleAddElementFromPalette(elementType) {
                if (!selectedCourseId || !currentCourseData || !currentCourseData.modules || currentCourseData.modules.length === 0) {
                    alert("Please select a course and ensure it has at least one module before adding elements.");
                    return;
                }

                let defaultTitle = elementType.charAt(0).toUpperCase() + elementType.slice(1) + " Lesson";
                let typeSpecificFields = '';
                // Placeholder for type-specific fields - will be expanded later
                switch(elementType) {
                    case 'text': typeSpecificFields = `<div class="form-group"><label for="modal-lesson-markdown">Initial Markdown:</label><textarea id="modal-lesson-markdown" name="markdown_content" rows="3" style="width:98%;"></textarea></div>`; break;
                    case 'video': typeSpecificFields = `<div class="form-group"><label for="modal-lesson-video-url">Video URL (optional):</label><input type="url" id="modal-lesson-video-url" name="video_url" style="width:98%;"></div> <div class="form-group"><label for="modal-lesson-video-file">Upload Video File (optional):</label><input type="file" id="modal-lesson-video-file" name="file" accept="video/*" onchange="displaySelectedFileName(this, 'selected-new-video-file-name')"></div> <p id="selected-new-video-file-name" style="font-size:0.8em;color:#ffaf87;"></p>`; break;
                    case 'quiz': typeSpecificFields = `<div class="form-group"><label for="modal-lesson-quiz-question">Question:</label><input type="text" id="modal-lesson-quiz-question" name="quiz_question" style="width:98%;"></div> <div class="form-group"><label for="modal-lesson-quiz-options">Options (one per line):</label><textarea id="modal-lesson-quiz-options" name="quiz_options" rows="3" style="width:98%;"></textarea></div> <div class="form-group"><label for="modal-lesson-quiz-correct">Correct Option Index (0-based):</label><input type="number" id="modal-lesson-quiz-correct" name="quiz_correct_answer_index" value="0" min="0" style="width:98%;"></div>`; break;
                    case 'download': typeSpecificFields = `<div class="form-group"><label for="modal-lesson-download-file">Upload File:</label><input type="file" id="modal-lesson-download-file" name="file" onchange="displaySelectedFileName(this, 'selected-new-download-file-name')"></div> <p id="selected-new-download-file-name" style="font-size:0.8em;color:#ffaf87;"></p>`; break;
                }

                let moduleOptionsHTML = '';
                currentCourseData.modules.sort((a,b) => a.order_index - b.order_index).forEach(mod => {
                    moduleOptionsHTML += `<option value="${mod.id}">${mod.name}</option>`;
                });
                if (!moduleOptionsHTML) {
                    alert("No modules available in this course to add a lesson to.");
                    return;
                }

                const firstModuleId = currentCourseData.modules[0].id;
                const lessonsInFirstModule = currentCourseData.lessons ? currentCourseData.lessons.filter(l => l.module_id === firstModuleId) : [];
                const defaultOrderIndex = lessonsInFirstModule.length + 1;

                const formHTML = \`<form id="add-lesson-element-modal-form" style="display:flex;flex-direction:column;gap:10px;">
                    <input type="hidden" name="content_type" value="\${elementType}">
                    <div class="form-group"><label for="modal-lesson-title">Lesson Title:</label><input type="text" id="modal-lesson-title" name="lesson_title" value="\${defaultTitle}" r style="width:98%;"></div>
                    <div class="form-group"><label for="modal-lesson-module">Parent Module:</label><select id="modal-lesson-module" name="module_id" r style="width:98%;">\${moduleOptionsHTML}</select></div>
                    <div class="form-group"><label for="modal-lesson-order">Order Index:</label><input type="number" id="modal-lesson-order" name="order_index" value="\${defaultOrderIndex}" min="1" r style="width:98%;"></div>
                    \${typeSpecificFields}
                    <button type="submit" class="btn-primary" style="width:100%;">Add Lesson Element</button>
                </form>\`;

                const submitNewLessonElement = async (formData, closeModalCallback) => {
                    if (!selectedCourseId) { alert("Error: No course selected."); return; }

                    let elementProps = {};
                    const contentType = formData.get('content_type');
                    switch(contentType) {
                        case 'text': elementProps.markdown_content = formData.get('markdown_content'); break;
                        case 'video': elementProps.url = formData.get('video_url'); break;
                        case 'quiz':
                            elementProps.question = formData.get('quiz_question');
                            elementProps.options = formData.get('quiz_options') ? formData.get('quiz_options').split('\\n').map(o=>o.trim()).filter(o=>o) : [];
                            elementProps.correct_answer_index = formData.get('quiz_correct_answer_index') ? parseInt(formData.get('quiz_correct_answer_index')) : 0;
                            break;
                    }
                    ['markdown_content', 'video_url', 'quiz_question', 'quiz_options', 'quiz_correct_answer_index'].forEach(k => formData.delete(k));
                    formData.append('element_properties', JSON.stringify(elementProps));

                    try {
                        const response = await fetch(\`/api/admin/courses/\${selectedCourseId}/lessons\`, {
                            method: 'POST',
                            body: formData
                        });
                        if (!response.ok) {
                            const errorData = await response.json();
                            throw new Error(errorData.error || 'Failed to create lesson element');
                        }
                        alert('Lesson element created!');
                        if (currentCourseData) loadCourse(selectedCourseId, currentCourseData.name);
                        if (closeModalCallback) closeModalCallback();
                    } catch (error) {
                        console.error("Failed to create lesson element:", error);
                        alert(\`Error: \${error.message}\`);
                    }
                };
                openModal(\`Add New \${elementType.charAt(0).toUpperCase() + elementType.slice(1)} Element\`, formHTML, submitNewLessonElement);

                const moduleDropdownInModal = document.getElementById('modal-lesson-module');
                const orderInputInModal = document.getElementById('modal-lesson-order');
                if (moduleDropdownInModal && orderInputInModal && currentCourseData && currentCourseData.lessons) {
                    moduleDropdownInModal.addEventListener('change', function() {
                        const selectedModId = parseInt(this.value);
                        const lessonsInSelectedModule = currentCourseData.lessons.filter(l => l.module_id === selectedModId);
                        orderInputInModal.value = lessonsInSelectedModule.length + 1;
                    });
                }
            }

            function handleEditModuleClick(moduleId, name, description, orderIndex) {
                const formHTML = \`<form id="edit-module-modal-form" style="display:flex;flex-direction:column;gap:10px;"><input type="hidden" name="module_id" value="\${moduleId}"><div class="form-group"><label for="modal-edit-module-name">Name:</label><input type="text" id="modal-edit-module-name" name="name" value="\${name}" r style="width:98%;"></div><div class="form-group"><label for="modal-edit-module-description">Description:</label><textarea id="modal-edit-module-description" name="description" rows="3" style="width:98%;">\${description}</textarea></div><div class="form-group"><label for="modal-edit-module-order">Order:</label><input type="number" id="modal-edit-module-order" name="order_index" value="\${orderIndex}" min="1" r style="width:98%;"></div><button type="submit" class="btn-primary" style="width:100%;">Update Module</button></form>\`;
                const submitEditModule = async (formData, closeModalCallback) => {
                    const mId=formData.get('module_id'), uName=formData.get('name'), uDesc=formData.get('description'), uOrder=parseInt(formData.get('order_index'));
                    try {
                        const response=await fetch(`/api/admin/modules/${mId}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:uName,description:uDesc,order_index:uOrder})});
                        if(!response.ok)throw new Error((await response.json()).error||'Failed to update');
                        alert('Module updated!'); if(currentCourseData){const cName=currentCourseData.id===selectedCourseId?currentCourseData.name:document.querySelector(`#course-list li[data-course-id='${selectedCourseId}']`).textContent;loadCourse(selectedCourseId,cName);}
                        if(closeModalCallback)closeModalCallback();
                    } catch(error){console.error("Failed to update module:",error);alert(`Error: ${error.message}`);}
                };
                openModal(`Edit Module: ${name}`, formHTML, submitEditModule);
            }
        </script>
    </body>
    </html>
    """)

if __name__ == '__main__':
    # Initialize database
    init_db()
    
    # Run the application
    app.run(host='0.0.0.0', port=5000, debug=True)
