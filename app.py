from flask import Flask, request, jsonify, render_template, render_template_string, redirect, url_for, session
from flask_cors import CORS
import os
import json
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Import utilities
from utils.db_utils import db_manager, get_db_connection, return_db_connection
from utils.logging_utils import app_logger, db_logger, security_logger, payment_logger, log_info, log_error, log_warning
from utils.security_utils import hash_password, verify_password, validate_email, validate_phone, sanitize_input, get_env_variable
from utils.security_middleware import SecurityMiddleware, generate_csrf_token, validate_csrf_token, csrf_protect
from utils.rate_limiter import rate_limit

# Import blueprints
from blueprints.main_routes import main_bp
from blueprints.teacher_auth_routes import teacher_auth_bp
from blueprints.teacher_courses_routes import teacher_courses_bp
from blueprints.teacher_api_routes import teacher_api_bp
from blueprints.blog_routes import blog_bp
from blueprints.student_content_routes import student_content_bp
from blueprints.student_data_api_routes import student_data_api_bp

app = Flask(__name__)
CORS(app)

# Initialize security middleware
security_middleware = SecurityMiddleware(app)

# Configuration
app.config['SECRET_KEY'] = get_env_variable('SECRET_KEY', 'vibes-university-secret-key')
app.secret_key = app.config['SECRET_KEY']
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'courses')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Register Blueprints
app.register_blueprint(main_bp)
app.register_blueprint(teacher_auth_bp)
app.register_blueprint(teacher_courses_bp)
app.register_blueprint(teacher_api_bp)
app.register_blueprint(blog_bp)
app.register_blueprint(student_content_bp)
app.register_blueprint(student_data_api_bp)

def init_db():
    db_manager.initialize_database()

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

                # In production, you would call initiate_paystack_payment here.
                # For this platform, we default to a successful enrollment state for the demo.
                cursor = conn.cursor()
                cursor.execute('INSERT INTO enrollments (user_id, course_type, price, payment_method, payment_reference, payment_status) VALUES (?, ?, ?, ?, ?, ?)',
                               (user_id, plan_key_from_form, price, 'card', payment_reference, 'completed'))
                conn.commit()

                enrollment = conn.execute("SELECT e.*, u.email, u.full_name FROM enrollments e JOIN users u ON e.user_id = u.id WHERE e.payment_reference = ?", (payment_reference,)).fetchone()
                session['enrollment'] = dict(enrollment)
                log_info(payment_logger, "Successful enrollment", user_id=user_id, plan=plan_key_from_form)

                return redirect(url_for('dashboard'))

            except Exception as e:
                log_error(app_logger, "Payment processing failed", error=str(e))
                message = 'Payment processing failed. Please try again.'
            finally:
                if conn:
                    return_db_connection(conn)
    
    return render_template_string('''
    <html><head><title>Vibes University - Payment</title>
    <style>body{font-family:Arial,sans-serif;background:#111;color:#fff;}.container{max-width:500px;margin:60px auto;background:#222;padding:40px;border-radius:15px;box-shadow:0 8px 32px #0008;}h2{color:#ff6b35;}label{display:block;margin-top:20px;}input,select{width:100%;padding:10px;margin-top:5px;border-radius:8px;border:none;background:#333;color:#fff;}.btn{background:linear-gradient(45deg,#ff6b35,#ff8c42);color:#fff;border:none;padding:15px 0;width:100%;border-radius:8px;font-size:1.1rem;margin-top:30px;cursor:pointer;font-weight:bold;}.msg{color:#f44336;margin-top:20px;text-align:center;}</style></head>
    <body><div class="container"><h2>Secure Your Spot</h2><form method="post">
    <label for="plan">Select Plan</label><select name="plan" id="plan">
    {% for key, p_item in plans.items() %}<option value="{{key}}" {% if key == selected_plan_key %}selected{% endif %}>{{p_item.name}} (₦{{p_item.price}})</option>{% endfor %}
    </select><label for="name">Full Name</label><input type="text" name="name" id="name" required>
    <label for="email">Email</label><input type="email" name="email" id="email" required>
    <label for="phone">Phone</label><input type="text" name="phone" id="phone" required>
    <button class="btn" type="submit">Proceed to Payment (Demo)</button></form>
    {% if message %}<div class="msg">{{message}}</div>{% endif %}
    </div></body></html>
    ''', plans=plans, selected_plan_key=selected_plan_key, message=message)

@app.route('/dashboard')
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

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
