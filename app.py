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

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'vibes-university-secret-key')
DATABASE = 'vibes_university.db'

# Payment Gateway Configuration
PAYSTACK_SECRET_KEY = os.environ.get('PAYSTACK_SECRET_KEY', 'sk_test_your_paystack_secret_key')
FLUTTERWAVE_SECRET_KEY = os.environ.get('FLUTTERWAVE_SECRET_KEY', 'FLWSECK_TEST-your_flutterwave_secret_key')

app.secret_key = app.config['SECRET_KEY']

# Admin config (for demo, use env var or DB in production)
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'vibesadmin123')
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
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Courses table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    # Enrollments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            course_type TEXT NOT NULL,
            price INTEGER NOT NULL,
            payment_method TEXT NOT NULL,
            payment_status TEXT DEFAULT 'pending',
            payment_reference TEXT,
            enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Course progress table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS course_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            course_id TEXT NOT NULL,
            lesson_id TEXT NOT NULL,
            completed BOOLEAN DEFAULT 0,
            completed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Payment logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            payment_method TEXT NOT NULL,
            gateway_response TEXT,
            status TEXT NOT NULL,
            reference TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Lessons table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course TEXT,
            module TEXT,
            lesson TEXT,
            description TEXT,
            file_path TEXT,
            content_type TEXT DEFAULT 'file',
            order_index INTEGER DEFAULT 1,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Announcements table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            priority TEXT DEFAULT 'normal',
            target_audience TEXT DEFAULT 'all',
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP
        )
    ''')
    
    # Add missing columns to existing lessons table if they don't exist
    try:
        cursor.execute('ALTER TABLE lessons ADD COLUMN content_type TEXT DEFAULT "file"')
    except sqlite3.OperationalError:
        # Column already exists
        pass
    
    try:
        cursor.execute('ALTER TABLE lessons ADD COLUMN order_index INTEGER DEFAULT 1')
    except sqlite3.OperationalError:
        # Column already exists
        pass
    
    conn.commit()
    conn.close()

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def home():
    """Serve the main course platform page"""
    try:
        # Use current directory instead of hardcoded Linux path
        index_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')
        with open(index_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return jsonify({'error': 'Platform not found'}), 404
    except Exception as e:
        return jsonify({'error': f'Error loading platform: {str(e)}'}), 500

@app.route('/api/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['email', 'password', 'full_name', 'phone']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Check if user already exists
        conn = get_db_connection()
        existing_user = conn.execute(
            'SELECT id FROM users WHERE email = ?', (data['email'],)
        ).fetchone()
        
        if existing_user:
            conn.close()
            return jsonify({'error': 'User already exists'}), 400
        
        # Create new user
        password_hash = generate_password_hash(data['password'])
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (email, password_hash, full_name, phone)
            VALUES (?, ?, ?, ?)
        ''', (data['email'], password_hash, data['full_name'], data['phone']))
        
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'User registered successfully',
            'user_id': user_id
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    """Login user"""
    try:
        data = request.get_json()
        
        if not data.get('email') or not data.get('password'):
            return jsonify({'error': 'Email and password are required'}), 400
        
        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE email = ?', (data['email'],)
        ).fetchone()
        conn.close()
        
        if not user or not check_password_hash(user['password_hash'], data['password']):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        return jsonify({
            'success': True,
            'user': {
                'id': user['id'],
                'email': user['email'],
                'full_name': user['full_name'],
                'phone': user['phone']
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/initiate-payment', methods=['POST'])
def initiate_payment():
    """Initiate payment process"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['user_id', 'course_type', 'price', 'payment_method']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Generate payment reference
        payment_reference = f"VU_{data['user_id']}_{int(datetime.now().timestamp())}"
        
        # Store enrollment record
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO enrollments (user_id, course_type, price, payment_method, payment_reference)
            VALUES (?, ?, ?, ?, ?)
        ''', (data['user_id'], data['course_type'], data['price'], data['payment_method'], payment_reference))
        
        enrollment_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Process payment based on method
        if data['payment_method'] == 'card':
            payment_url = initiate_paystack_payment(data, payment_reference)
        elif data['payment_method'] == 'bank':
            payment_url = initiate_flutterwave_payment(data, payment_reference)
        elif data['payment_method'] == 'crypto':
            payment_url = initiate_crypto_payment(data, payment_reference)
        else:
            return jsonify({'error': 'Invalid payment method'}), 400
        
        return jsonify({
            'success': True,
            'payment_reference': payment_reference,
            'payment_url': payment_url,
            'enrollment_id': enrollment_id
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def initiate_paystack_payment(data, reference):
    """Initiate Paystack payment"""
    try:
        url = "https://api.paystack.co/transaction/initialize"
        headers = {
            "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "email": data.get('email', 'student@vibesuniversity.com'),
            "amount": data['price'] * 100,  # Paystack expects amount in kobo
            "reference": reference,
            "callback_url": "https://vibesuniversity.com/payment/callback",
            "metadata": {
                "course_type": data['course_type'],
                "user_id": data['user_id']
            }
        }
        
        # For demo purposes, return a mock payment URL
        return f"https://checkout.paystack.com/demo?reference={reference}"
        
    except Exception as e:
        print(f"Paystack error: {e}")
        return f"https://checkout.paystack.com/demo?reference={reference}"

def initiate_flutterwave_payment(data, reference):
    """Initiate Flutterwave payment"""
    try:
        # For demo purposes, return a mock payment URL
        return f"https://checkout.flutterwave.com/demo?reference={reference}"
        
    except Exception as e:
        print(f"Flutterwave error: {e}")
        return f"https://checkout.flutterwave.com/demo?reference={reference}"

def initiate_crypto_payment(data, reference):
    """Initiate cryptocurrency payment"""
    try:
        # For demo purposes, return crypto payment instructions
        return f"https://vibesuniversity.com/crypto-payment?reference={reference}"
        
    except Exception as e:
        print(f"Crypto payment error: {e}")
        return f"https://vibesuniversity.com/crypto-payment?reference={reference}"

@app.route('/api/verify-payment', methods=['POST'])
def verify_payment():
    """Verify payment status"""
    try:
        data = request.get_json()
        reference = data.get('reference')
        
        if not reference:
            return jsonify({'error': 'Payment reference is required'}), 400
        
        # For demo purposes, simulate successful payment verification
        # In production, this would verify with the actual payment gateway
        
        # Update enrollment status
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE enrollments 
            SET payment_status = 'completed'
            WHERE payment_reference = ?
        ''', (reference,))
        
        # Get enrollment details
        enrollment = conn.execute('''
            SELECT e.*, u.email, u.full_name 
            FROM enrollments e
            JOIN users u ON e.user_id = u.id
            WHERE e.payment_reference = ?
        ''', (reference,)).fetchone()
        
        conn.commit()
        conn.close()
        
        if enrollment:
            # Send welcome email and course access (would be implemented)
            send_course_access(enrollment)
            
            return jsonify({
                'success': True,
                'message': 'Payment verified successfully',
                'enrollment': dict(enrollment)
            })
        else:
            return jsonify({'error': 'Enrollment not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def send_course_access(enrollment):
    """Send course access to student"""
    # This would integrate with email service and WhatsApp API
    print(f"Sending course access to {enrollment['email']} for {enrollment['course_type']}")
    
    # Course access URLs based on type
    course_urls = {
        'course': 'https://vibesuniversity.com/courses/basic',
        'online': 'https://vibesuniversity.com/courses/mentorship',
        'vip': 'https://vibesuniversity.com/courses/vip'
    }
    
    # In production, this would send actual emails and WhatsApp messages
    return True

@app.route('/api/courses', methods=['GET'])
def get_courses():
    """Get available courses"""
    courses = {
        'course1': {
            'id': 'ai_marketing_mastery',
            'title': 'AI Marketing Mastery',
            'description': 'Master AI-powered marketing automation and generate ₦500K-₦2M monthly',
            'modules': 4,
            'lessons': 12,
            'duration': '6 weeks'
        },
        'course2': {
            'id': 'ai_coding_development',
            'title': 'AI Coding & Development',
            'description': 'Build AI-powered applications and earn ₦800K-₦3M monthly as a developer',
            'modules': 4,
            'lessons': 15,
            'duration': '8 weeks'
        },
        'course3': {
            'id': 'ai_content_creation',
            'title': 'AI Content Creation & Monetization',
            'description': 'Create viral content with AI and monetize across multiple platforms',
            'modules': 3,
            'lessons': 10,
            'duration': '5 weeks'
        },
        'course4': {
            'id': 'ai_ecommerce_automation',
            'title': 'AI E-commerce & Sales Automation',
            'description': 'Build automated e-commerce systems generating ₦1M-₦5M monthly',
            'modules': 4,
            'lessons': 14,
            'duration': '7 weeks'
        },
        'course5': {
            'id': 'ai_business_automation',
            'title': 'AI Business Process Automation',
            'description': 'Automate entire business processes and scale without hiring',
            'modules': 4,
            'lessons': 13,
            'duration': '6 weeks'
        },
        'course6': {
            'id': 'ai_tools_mastery',
            'title': 'AI Tools Mastery for Income Generation',
            'description': 'Master 50+ AI tools and create multiple income streams',
            'modules': 4,
            'lessons': 16,
            'duration': '8 weeks'
        }
    }
    
    return jsonify({'courses': courses})

@app.route('/api/user-progress/<int:user_id>', methods=['GET'])
def get_user_progress(user_id):
    """Get user's course progress"""
    try:
        conn = get_db_connection()
        
        # Get user's enrollments
        enrollments = conn.execute('''
            SELECT * FROM enrollments 
            WHERE user_id = ? AND payment_status = 'completed'
        ''', (user_id,)).fetchall()
        
        # Get course progress
        progress = conn.execute('''
            SELECT * FROM course_progress 
            WHERE user_id = ?
        ''', (user_id,)).fetchall()
        
        conn.close()
        
        return jsonify({
            'enrollments': [dict(row) for row in enrollments],
            'progress': [dict(row) for row in progress]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/update-progress', methods=['POST'])
def update_progress():
    """Update user's lesson progress"""
    try:
        data = request.get_json()
        
        required_fields = ['user_id', 'course_id', 'lesson_id']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if progress record exists
        existing = conn.execute('''
            SELECT id FROM course_progress 
            WHERE user_id = ? AND course_id = ? AND lesson_id = ?
        ''', (data['user_id'], data['course_id'], data['lesson_id'])).fetchone()
        
        if existing:
            # Update existing record
            cursor.execute('''
                UPDATE course_progress 
                SET completed = 1, completed_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND course_id = ? AND lesson_id = ?
            ''', (data['user_id'], data['course_id'], data['lesson_id']))
        else:
            # Insert new record
            cursor.execute('''
                INSERT INTO course_progress (user_id, course_id, lesson_id, completed, completed_at)
                VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
            ''', (data['user_id'], data['course_id'], data['lesson_id']))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Progress updated'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get platform statistics"""
    try:
        conn = get_db_connection()
        
        # Get user count
        user_count = conn.execute('SELECT COUNT(*) as count FROM users').fetchone()['count']
        
        # Get enrollment count
        enrollment_count = conn.execute('''
            SELECT COUNT(*) as count FROM enrollments 
            WHERE payment_status = 'completed'
        ''').fetchone()['count']
        
        # Get total revenue
        total_revenue = conn.execute('''
            SELECT SUM(price) as total FROM enrollments 
            WHERE payment_status = 'completed'
        ''').fetchone()['total'] or 0
        
        conn.close()
        
        return jsonify({
            'users': user_count,
            'enrollments': enrollment_count,
            'revenue': total_revenue,
            'success_rate': '97%',
            'average_income': '₦1,200,000'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/testimonials', methods=['GET'])
def get_testimonials():
    """Get student testimonials"""
    testimonials = [
        {
            'name': 'Chioma Okafor',
            'age': 24,
            'location': 'Lagos',
            'income': '₦800,000/month',
            'story': 'I was broke 3 months ago. Now I make more than my parents combined. AI automation changed my life!',
            'course': 'AI Marketing Mastery',
            'timeframe': '3 months'
        },
        {
            'name': 'Emeka Nwankwo',
            'age': 22,
            'location': 'Abuja',
            'income': '₦2,500,000/month',
            'story': 'Quit university to focus on my AI business. Best decision ever. I work 1 hour per day.',
            'course': 'AI Coding & Development',
            'timeframe': '4 months'
        },
        {
            'name': 'Fatima Abdullahi',
            'age': 26,
            'location': 'Kano',
            'income': '₦1,200,000/month',
            'story': 'Financial freedom at 26. Bought my parents a house. Thank you Vibes University!',
            'course': 'AI Content Creation',
            'timeframe': '5 months'
        },
        {
            'name': 'David Ogundimu',
            'age': 23,
            'location': 'Port Harcourt',
            'income': '₦3,000,000/month',
            'story': 'From ₦0 to ₦3M monthly in 4 months. The system works if you follow it exactly.',
            'course': 'AI E-commerce Automation',
            'timeframe': '4 months'
        }
    ]
    
    return jsonify({'testimonials': testimonials})

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

@app.route('/pay', methods=['GET', 'POST'])
def pay():
    plans = {
        'course': {'name': 'Course Access', 'price': 100000},
        'online': {'name': 'Online Mentorship', 'price': 400000},
        'vip': {'name': 'VIP Physical Class', 'price': 2000000}
    }
    selected_plan = request.args.get('plan', 'course')
    plan = plans.get(selected_plan, plans['course'])
    message = ''
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        plan_key = request.form.get('plan')
        plan = plans.get(plan_key, plans['course'])
        price = plan['price']
        
        # 1. Create user if not exists
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if not user:
            password_hash = generate_password_hash(secrets.token_hex(8))
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (email, password_hash, full_name, phone)
                VALUES (?, ?, ?, ?)
            ''', (email, password_hash, name, phone))
            user_id = cursor.lastrowid
            conn.commit()
        else:
            user_id = user['id']
        conn.close()
        
        # 2. Initiate payment
        payment_data = {
            'user_id': user_id,
            'course_type': plan_key,
            'price': price,
            'payment_method': 'card',
            'email': email
        }
        
        # Call the internal API endpoint
        with app.test_request_context():
            with app.test_client() as client:
                resp = client.post('/api/initiate-payment', json=payment_data)
                resp_json = resp.get_json()
        
        if resp_json and resp_json.get('success'):
            payment_url = resp_json['payment_url']
            # Store reference in session for callback
            session['pending_reference'] = resp_json['payment_reference']
            session['user_id'] = user_id
            return redirect(payment_url)
        else:
            message = resp_json.get('error', 'Payment initiation failed. Please try again.')
    
    return render_template_string('''
    <html>
    <head>
        <title>Vibes University - Payment</title>
        <style>
            body { font-family: Arial, sans-serif; background: #111; color: #fff; }
            .container { max-width: 500px; margin: 60px auto; background: #222; padding: 40px; border-radius: 15px; box-shadow: 0 8px 32px #0008; }
            h2 { color: #ff6b35; }
            label { display: block; margin-top: 20px; }
            input, select { width: 100%; padding: 10px; margin-top: 5px; border-radius: 8px; border: none; background: #333; color: #fff; }
            .btn { background: linear-gradient(45deg, #ff6b35, #ff8c42); color: #fff; border: none; padding: 15px 0; width: 100%; border-radius: 8px; font-size: 1.1rem; margin-top: 30px; cursor: pointer; font-weight: bold; }
            .msg { background: #222; color: #0f0; padding: 15px; border-radius: 8px; margin-top: 20px; text-align: center; }
            .demo-notice { background: #333; color: #ff6b35; padding: 15px; border-radius: 8px; margin-top: 20px; text-align: center; border: 1px solid #ff6b35; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Secure Your Spot</h2>
            <form method="post">
                <label for="plan">Select Plan</label>
                <select name="plan" id="plan">
                    {% for key, p in plans.items() %}
                        <option value="{{key}}" {% if key == selected_plan %}selected{% endif %}>{{p.name}} (₦{{p.price}})</option>
                    {% endfor %}
                </select>
                <label for="name">Full Name</label>
                <input type="text" name="name" id="name" required>
                <label for="email">Email</label>
                <input type="email" name="email" id="email" required>
                <label for="phone">Phone</label>
                <input type="text" name="phone" id="phone" required>
                <button class="btn" type="submit">Proceed to Payment</button>
            </form>
            {% if message %}<div class="msg">{{message}}</div>{% endif %}
            <div class="demo-notice">
                <strong>Demo Mode:</strong> This is a demo payment system. Click "Proceed to Payment" to simulate payment and access the student dashboard.
            </div>
        </div>
    </body>
    </html>
    ''', plans=plans, selected_plan=selected_plan, plan=plan, message=message)

@app.route('/payment/callback')
def payment_callback():
    # Paystack/Flutterwave will redirect here with ?reference=...
    reference = request.args.get('reference') or session.get('pending_reference')
    if not reference:
        return "Missing payment reference.", 400
    # Verify payment
    with app.test_request_context():
        with app.test_client() as client:
            resp = client.post('/api/verify-payment', json={'reference': reference})
            resp_json = resp.get_json()
    if resp_json and resp_json.get('success'):
        # Mark user as logged in (for demo)
        session['enrollment'] = resp_json['enrollment']
        return redirect(url_for('dashboard'))
    else:
        return f"Payment verification failed: {resp_json.get('error', 'Unknown error')}", 400

@app.route('/dashboard')
def dashboard():
    if not session.get('enrollment'):
        return redirect(url_for('student_login'))
    enrollment = session['enrollment']
    user_id = enrollment['user_id']
    conn = get_db_connection()

    # Fetch active announcements
    announcements = conn.execute('''
        SELECT * FROM announcements 
        WHERE is_active = 1 
        AND (expires_at IS NULL OR expires_at > datetime('now'))
        AND (target_audience = 'all' OR target_audience = ?)
        ORDER BY priority DESC, created_at DESC
    ''', (enrollment['course_type'],)).fetchall()

    # Fetch all lessons for the student's course
    lessons = conn.execute('''
        SELECT * FROM lessons WHERE course = ? ORDER BY module, order_index, uploaded_at''', (enrollment['course_type'],)).fetchall()
    total_lessons = len(lessons)

    # Fetch completed lessons for this user
    completed = conn.execute('''
        SELECT lesson_id FROM course_progress WHERE user_id = ? AND course_id = ? AND completed = 1''', (user_id, enrollment['course_type'])).fetchall()
    completed_ids = set([row['lesson_id'] for row in completed])
    completed_count = len(completed_ids)
    progress_percent = int((completed_count / total_lessons) * 100) if total_lessons else 0

    conn.close()

    return render_template_string('''
    <html>
    <head>
        <title>Student Dashboard - Vibes University</title>
        <style>
            body { font-family: Arial, sans-serif; background: #111; color: #fff; margin: 0; padding: 20px; }
            .header { background: #222; padding: 20px; border-radius: 10px; margin-bottom: 30px; }
            .header h1 { color: #ff6b35; margin: 0; }
            .announcements { background: #222; border-left: 5px solid #ff6b35; padding: 20px; border-radius: 10px; margin-bottom: 30px; }
            .announcement-title { color: #ff6b35; font-weight: bold; font-size: 18px; }
            .announcement-meta { color: #ccc; font-size: 12px; margin-bottom: 8px; }
            .announcement-message { background: #333; padding: 12px; border-radius: 6px; margin-bottom: 10px; }
            .progress-section { background: #222; padding: 20px; border-radius: 10px; margin-bottom: 30px; }
            .progress-bar-bg { background: #333; border-radius: 8px; height: 30px; width: 100%; margin-bottom: 10px; }
            .progress-bar { background: #4CAF50; height: 30px; border-radius: 8px; text-align: center; color: #fff; font-weight: bold; line-height: 30px; }
            .lesson-list { margin-top: 20px; }
            .lesson-item { padding: 10px; border-bottom: 1px solid #444; display: flex; align-items: center; }
            .lesson-completed { color: #4CAF50; margin-right: 10px; }
            .lesson-pending { color: #ff9800; margin-right: 10px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🎓 Welcome, {{enrollment['full_name']}}</h1>
            <p>Course: <b>{{enrollment['course_type']|title}}</b></p>
        </div>

        {% if announcements %}
        <div class="announcements">
            <h2>📢 Announcements</h2>
            {% for a in announcements %}
                <div class="announcement-title">{{a['title']}}</div>
                <div class="announcement-meta">{{a['created_at']}} | {{a['priority']|title}}</div>
                <div class="announcement-message">{{a['message']}}</div>
            {% endfor %}
        </div>
        {% endif %}

        <div class="progress-section">
            <h2>📈 Course Progress</h2>
            <div class="progress-bar-bg">
                <div class="progress-bar" style="width: {{progress_percent}}%;">{{progress_percent}}%</div>
            </div>
            <div class="lesson-list">
                {% for lesson in lessons %}
                    <div class="lesson-item">
                        {% if lesson['id'] in completed_ids %}
                            <span class="lesson-completed">✔️</span>
                        {% else %}
                            <span class="lesson-pending">⏳</span>
                        {% endif %}
                        {{lesson['module']}} - {{lesson['lesson']}}
                    </div>
                {% endfor %}
            </div>
        </div>
    </body>
    </html>
    ''', enrollment=enrollment, announcements=announcements, lessons=lessons, completed_ids=completed_ids, progress_percent=progress_percent)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    message = ''
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            message = 'Invalid password.'
    return render_template_string('''
    <html><head><title>Admin Login</title></head><body style="background:#111;color:#fff;font-family:Arial,sans-serif;text-align:center;padding:60px;">
    <h2>Admin Login</h2>
    <form method="post">
        <input type="password" name="password" placeholder="Admin Password" required style="padding:10px;border-radius:8px;">
        <button type="submit" style="padding:10px 20px;border-radius:8px;background:#ff6b35;color:#fff;font-weight:bold;">Login</button>
    </form>
    {% if message %}<div style="color:#f00;margin-top:20px;">{{message}}</div>{% endif %}
    </body></html>
    ''', message=message)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    message = ''
    conn = get_db_connection()
    
    # Get comprehensive statistics
    total_users = conn.execute('SELECT COUNT(*) as count FROM users').fetchone()['count']
    total_enrollments = conn.execute('SELECT COUNT(*) as count FROM enrollments').fetchone()['count']
    completed_payments = conn.execute('SELECT COUNT(*) as count FROM enrollments WHERE payment_status = "completed"').fetchone()['count']
    total_revenue = conn.execute('SELECT SUM(price) as total FROM enrollments WHERE payment_status = "completed"').fetchone()['total'] or 0
    total_lessons = conn.execute('SELECT COUNT(*) as count FROM lessons').fetchone()['count']
    
    # Get recent enrollments
    recent_enrollments = conn.execute('''
        SELECT e.*, u.full_name, u.email 
        FROM enrollments e 
        JOIN users u ON e.user_id = u.id 
        ORDER BY e.enrolled_at DESC 
        LIMIT 10
    ''').fetchall()
    
    # Get course statistics
    course_stats = conn.execute('''
        SELECT course_type, COUNT(*) as count, SUM(price) as revenue
        FROM enrollments 
        WHERE payment_status = 'completed'
        GROUP BY course_type
    ''').fetchall()
    
    # Get available courses for upload
    courses = conn.execute('SELECT DISTINCT course_type FROM enrollments').fetchall()
    
    if request.method == 'POST':
        # Handle file upload and metadata
        course = request.form.get('course')
        module = request.form.get('module')
        lesson = request.form.get('lesson')
        description = request.form.get('description')
        file = request.files.get('file')
        
        if not (course and module and lesson and file and allowed_file(file.filename)):
            message = 'All fields and a valid file are required.'
        else:
            filename = secure_filename(file.filename)
            course_dir = os.path.join(app.config['UPLOAD_FOLDER'], course, module)
            os.makedirs(course_dir, exist_ok=True)
            filepath = os.path.join(course_dir, filename)
            file.save(filepath)
            
            # Store metadata in DB
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO lessons (course, module, lesson, description, file_path)
                VALUES (?, ?, ?, ?, ?)
            ''', (course, module, lesson, description, filepath))
            conn.commit()
            message = 'Upload successful!'
    
    # List existing lessons with pagination
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page
    
    lessons = conn.execute('''
        SELECT *, COALESCE(order_index, 1) as order_index 
        FROM lessons 
        ORDER BY uploaded_at DESC 
        LIMIT ? OFFSET ?
    ''', (per_page, offset)).fetchall()
    
    total_lessons_count = conn.execute('SELECT COUNT(*) as count FROM lessons').fetchone()['count']
    total_pages = (total_lessons_count + per_page - 1) // per_page
    
    conn.close()
    
    return render_template_string('''
    <html>
    <head>
        <title>Admin Dashboard - Vibes University</title>
        <style>
            body { font-family: Arial, sans-serif; background: #111; color: #fff; margin: 0; padding: 20px; }
            .header { background: #222; padding: 20px; border-radius: 10px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: center; }
            .header h1 { color: #ff6b35; margin: 0; }
            .logout-btn { background: #ff6b35; color: #fff; padding: 10px 20px; border: none; border-radius: 8px; text-decoration: none; font-weight: bold; }
            .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
            .stat-card { background: #222; padding: 20px; border-radius: 10px; text-align: center; border-left: 4px solid #ff6b35; }
            .stat-number { font-size: 2rem; font-weight: bold; color: #ff6b35; }
            .stat-label { color: #ccc; margin-top: 5px; }
            .section { background: #222; padding: 20px; border-radius: 10px; margin-bottom: 30px; }
            .section h3 { color: #ff6b35; margin-top: 0; }
            .upload-form { background: #333; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
            .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
            .form-group { margin-bottom: 15px; }
            .form-group label { display: block; margin-bottom: 5px; color: #ccc; }
            .form-group input, .form-group select, .form-group textarea { 
                width: 100%; padding: 10px; border-radius: 8px; border: none; background: #444; color: #fff; 
            }
            .upload-btn { background: #4CAF50; color: #fff; padding: 12px 30px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; }
            .table { width: 100%; border-collapse: collapse; margin-top: 15px; }
            .table th, .table td { padding: 12px; text-align: left; border-bottom: 1px solid #444; }
            .table th { background: #333; color: #ff6b35; }
            .table tr:hover { background: #333; }
            .action-btn { 
                padding: 5px 10px; border: none; border-radius: 4px; text-decoration: none; font-size: 12px; margin-right: 5px;
            }
            .edit-btn { background: #4CAF50; color: #fff; }
            .delete-btn { background: #f44336; color: #fff; }
            .view-btn { background: #2196F3; color: #fff; }
            .pagination { display: flex; justify-content: center; gap: 10px; margin-top: 20px; }
            .pagination a { 
                background: #333; color: #fff; padding: 10px 15px; text-decoration: none; border-radius: 5px;
            }
            .pagination a:hover { background: #ff6b35; }
            .pagination .current { background: #ff6b35; }
            .success-msg { background: #4CAF50; color: #fff; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
            .course-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; }
            .course-stat { background: #333; padding: 15px; border-radius: 8px; text-align: center; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🎓 Vibes University Admin Dashboard</h1>
            <div style="display: flex; gap: 10px;">
                <a href="{{url_for('admin_users')}}" style="background: #333; color: #fff; padding: 8px 15px; border-radius: 5px; text-decoration: none; font-size: 14px;">👥 Users</a>
                <a href="{{url_for('admin_analytics')}}" style="background: #333; color: #fff; padding: 8px 15px; border-radius: 5px; text-decoration: none; font-size: 14px;">📊 Analytics</a>
                <a href="{{url_for('admin_settings')}}" style="background: #333; color: #fff; padding: 8px 15px; border-radius: 5px; text-decoration: none; font-size: 14px;">⚙️ Settings</a>
                <a href="{{url_for('admin_announcements')}}" style="background: #ff6b35; color: #fff; padding: 8px 15px; border-radius: 5px; text-decoration: none; font-size: 14px;">📢 Announcements</a>
                <a href="{{url_for('admin_course_builder')}}" style="background: #4CAF50; color: #fff; padding: 8px 15px; border-radius: 5px; text-decoration: none; font-size: 14px;">📝 Course Builder</a>
                <a href="{{url_for('admin_preview_course', course_type='course')}}" style="background: #2196F3; color: #fff; padding: 8px 15px; border-radius: 5px; text-decoration: none; font-size: 14px;">👁️ Preview Course</a>
                <a href="/demo-payment" style="background: #4CAF50; color: #fff; padding: 8px 15px; border-radius: 5px; text-decoration: none; font-size: 14px;">🎯 Test Dashboard</a>
                <a href="{{url_for('admin_logout')}}" class="logout-btn">Logout</a>
                <a href="{{url_for('admin_courses')}}" style="background: #333; color: #fff; padding: 8px 15px; border-radius: 5px; text-decoration: none; font-size: 14px;">📚 Manage Courses</a>
            </div>
        </div>
        
        {% if message %}<div class="success-msg">{{message}}</div>{% endif %}
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">{{total_users}}</div>
                <div class="stat-label">Total Users</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{total_enrollments}}</div>
                <div class="stat-label">Total Enrollments</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{completed_payments}}</div>
                <div class="stat-label">Completed Payments</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">₦{{total_revenue}}</div>
                <div class="stat-label">Total Revenue</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{total_lessons}}</div>
                <div class="stat-label">Total Lessons</div>
            </div>
        </div>
        
        <div class="section">
            <h3>📊 Course Statistics</h3>
            <div class="course-stats">
                {% for stat in course_stats %}
                <div class="course-stat">
                    <div style="font-weight: bold; color: #ff6b35;">{{stat['course_type']|title}}</div>
                    <div>{{stat['count']}} students</div>
                    <div>₦{{stat['revenue']}}</div>
                </div>
                {% endfor %}
            </div>
        </div>
        
        <div class="section">
            <h3>📤 Upload Course Content</h3>
            <form method="post" enctype="multipart/form-data" class="upload-form">
                <div class="form-grid">
                    <div class="form-group">
                        <label>Course Name:</label>
                        <select name="course" required>
                            <option value="">Select Course</option>
                            {% for c in courses %}
                                <option value="{{c['name']}}">{{c['name']}}</option>
                            {% endfor %}
                        </select>
                        <a href="{{url_for('admin_courses')}}" style="color:#4CAF50; margin-left:10px; font-size:14px; text-decoration:none;">➕ Add New Course</a>
                    </div>
                    <div class="form-group">
                        <label>Module Name:</label>
                        <select name="module" required>
                            {% for i in range(1, 16) %}
                                <option value="Module {{i}}">Module {{i}}</option>
                            {% endfor %}
                        </select>
                    </div>
                </div>
                <div class="form-group">
                    <label>Lesson Title:</label>
                    <input type="text" name="lesson" placeholder="e.g., Getting Started with AI" required>
                </div>
                <div class="form-group">
                    <label>Description:</label>
                    <textarea name="description" placeholder="Brief description of the lesson content" rows="3"></textarea>
                </div>
                <div class="form-group">
                    <label>Upload File (videos, docs, images, audio, archives):</label>
                    <input type="file" name="file" required>
                </div>
                <button type="submit" class="upload-btn">📁 Upload Lesson</button>
            </form>
        </div>
        
        <div class="section">
            <h3>📋 Recent Enrollments</h3>
            <table class="table">
                <tr>
                    <th>Student</th>
                    <th>Email</th>
                    <th>Course</th>
                    <th>Amount</th>
                    <th>Status</th>
                    <th>Date</th>
                </tr>
                {% for enrollment in recent_enrollments %}
                <tr>
                    <td>{{enrollment['full_name']}}</td>
                    <td>{{enrollment['email']}}</td>
                    <td>{{enrollment['course_type']|title}}</td>
                    <td>₦{{enrollment['price']}}</td>
                    <td>
                        <span style="color: {{'#4CAF50' if enrollment['payment_status'] == 'completed' else '#ff9800'}};">
                            {{enrollment['payment_status']|title}}
                        </span>
                    </td>
                    <td>{{enrollment['enrolled_at']}}</td>
                </tr>
                {% endfor %}
            </table>
        </div>
        
        <div class="section">
            <h3>📚 Course Content Management</h3>
            <table class="table">
                <tr>
                    <th>Course</th>
                    <th>Module</th>
                    <th>Lesson</th>
                    <th>File</th>
                    <th>Uploaded</th>
                    <th>Actions</th>
                </tr>
                {% for lesson in lessons %}
                <tr>
                    <td>{{lesson['course']|title}}</td>
                    <td>{{lesson['module']}}</td>
                    <td>{{lesson['lesson']}}</td>
                    <td>
                        <a href="{{(lesson['file_path'] or '').replace('static','/static')}}" style="color: #ff6b35; text-decoration: none;">
                            {{get_file_icon((lesson['file_path'] or '').split('/')[-1])}} {{(lesson['file_path'] or '').split('/')[-1]}}
                        </a>
                    </td>
                    <td>{{lesson['uploaded_at']}}</td>
                    <td>
                        <a href="{{url_for('admin_edit_lesson', lesson_id=lesson['id'])}}" class="action-btn edit-btn">✏️ Edit</a>
                        <a href="{{url_for('admin_preview_lesson', lesson_id=lesson['id'])}}" class="action-btn view-btn">👁️ Preview</a>
                        <a href="{{url_for('admin_delete_lesson', lesson_id=lesson['id'])}}" 
                           onclick="return confirm('Are you sure you want to delete this lesson?')" 
                           class="action-btn delete-btn">🗑️ Delete</a>
                    </td>
                </tr>
                {% endfor %}
            </table>
            
            {% if total_pages > 1 %}
            <div class="pagination">
                {% for p in range(1, total_pages + 1) %}
                    <a href="?page={{p}}" class="{{'current' if p == page else ''}}">{{p}}</a>
                {% endfor %}
            </div>
            {% endif %}
        </div>
    </body>
    </html>
    ''', message=message, lessons=lessons, get_file_icon=get_file_icon, 
         total_users=total_users, total_enrollments=total_enrollments, 
         completed_payments=completed_payments, total_revenue=total_revenue,
         total_lessons=total_lessons, recent_enrollments=recent_enrollments,
         course_stats=course_stats, page=page, total_pages=total_pages)

@app.route('/admin/edit/<int:lesson_id>', methods=['GET', 'POST'])
def admin_edit_lesson(lesson_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    lesson = conn.execute('SELECT * FROM lessons WHERE id = ?', (lesson_id,)).fetchone()
    
    if not lesson:
        conn.close()
        return "Lesson not found", 404
    
    message = ''
    if request.method == 'POST':
        course = request.form.get('course')
        module = request.form.get('module')
        lesson_title = request.form.get('lesson')
        description = request.form.get('description')
        file = request.files.get('file')
        
        if not (course and module and lesson_title):
            message = 'Course, module, and lesson title are required.'
        else:
            # Update metadata
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE lessons 
                SET course = ?, module = ?, lesson = ?, description = ?
                WHERE id = ?
            ''', (course, module, lesson_title, description, lesson_id))
            
            # Handle file upload if new file is provided
            if file and file.filename and allowed_file(file.filename):
                # Delete old file
                if os.path.exists(lesson['file_path']):
                    os.remove(lesson['file_path'])
                
                # Save new file
                filename = secure_filename(file.filename)
                course_dir = os.path.join(app.config['UPLOAD_FOLDER'], course, module)
                os.makedirs(course_dir, exist_ok=True)
                filepath = os.path.join(course_dir, filename)
                file.save(filepath)
                
                # Update file path in database
                cursor.execute('UPDATE lessons SET file_path = ? WHERE id = ?', (filepath, lesson_id))
            
            conn.commit()
            message = 'Lesson updated successfully!'
            lesson = conn.execute('SELECT * FROM lessons WHERE id = ?', (lesson_id,)).fetchone()
    
    conn.close()
    
    return render_template_string('''
    <html><head><title>Edit Lesson</title></head><body style="background:#111;color:#fff;font-family:Arial,sans-serif;padding:40px;">
    <h2>Edit Lesson</h2>
    <a href="{{url_for('admin_dashboard')}}" style="color:#ff6b35;">← Back to Dashboard</a>
    <form method="post" enctype="multipart/form-data" style="background:#222;padding:30px;border-radius:12px;max-width:500px;margin:30px auto;">
        <label>Course Name: <input type="text" name="course" value="{{lesson['course']}}" required style="width:100%;padding:8px;"></label><br><br>
        <label>Module Name: <input type="text" name="module" value="{{lesson['module']}}" required style="width:100%;padding:8px;"></label><br><br>
        <label>Lesson Title: <input type="text" name="lesson" value="{{lesson['lesson']}}" required style="width:100%;padding:8px;"></label><br><br>
        <label>Description:<br><textarea name="description" style="width:100%;height:60px;padding:8px;">{{lesson['description'] or ''}}</textarea></label><br><br>
        <label>Current File: <span style="color:#ff6b35;">{{(lesson['file_path'] or '').split('/')[-1]}}</span></label><br><br>
        <label>Upload New File (optional): <input type="file" name="file"></label><br><br>
        <button type="submit" style="background:#4CAF50;color:#fff;padding:12px 30px;border:none;border-radius:8px;font-weight:bold;">Update Lesson</button>
    </form>
    {% if message %}<div style="color:#0f0;margin:20px 0;">{{message}}</div>{% endif %}
    </body></html>
    ''', lesson=lesson, message=message)

@app.route('/admin/delete/<int:lesson_id>')
def admin_delete_lesson(lesson_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    lesson = conn.execute('SELECT * FROM lessons WHERE id = ?', (lesson_id,)).fetchone()
    
    if lesson:
        # Delete file from filesystem
        if os.path.exists(lesson['file_path']):
            os.remove(lesson['file_path'])
        
        # Delete from database
        conn.execute('DELETE FROM lessons WHERE id = ?', (lesson_id,))
        conn.commit()
    
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/courses')
def student_courses():
    """Student dashboard showing enrolled courses"""
    enrollment = session.get('enrollment')
    if not enrollment:
        return redirect(url_for('pay'))
    
    conn = get_db_connection()
    
    # Get all lessons for the student's course type
    lessons = conn.execute('''
        SELECT *, COALESCE(order_index, 1) as order_index 
        FROM lessons 
        WHERE course = ? 
        ORDER BY module, order_index, lesson
    ''', (enrollment['course_type'],)).fetchall()
    
    # Get student's progress
    progress = conn.execute('''
        SELECT * FROM course_progress 
        WHERE user_id = ?
    ''', (enrollment['user_id'],)).fetchall()
    
    # Organize lessons by module
    modules = {}
    for lesson in lessons:
        module_name = lesson['module']
        if module_name not in modules:
            modules[module_name] = []
        modules[module_name].append(lesson)
    
    # Create progress lookup - handle case where progress data might be empty
    progress_lookup = {}
    for p in progress:
        try:
            key = f"{p['course_id']}_{p['lesson_id']}"
            progress_lookup[key] = p['completed']
        except (KeyError, TypeError):
            # Skip invalid progress records
            continue
    
    conn.close()
    
    return render_template_string('''
    <html>
    <head>
        <title>My Courses - Vibes University</title>
        <style>
            body { font-family: Arial, sans-serif; background: #111; color: #fff; margin: 0; padding: 20px; }
            .header { background: #222; padding: 20px; border-radius: 10px; margin-bottom: 30px; }
            .welcome { color: #ff6b35; font-size: 24px; margin-bottom: 10px; }
            .course-info { color: #ccc; }
            .modules { display: grid; gap: 20px; }
            .module-card { background: #222; border-radius: 10px; padding: 20px; border-left: 4px solid #ff6b35; }
            .module-title { color: #ff6b35; font-size: 20px; margin-bottom: 15px; }
            .lessons { display: grid; gap: 10px; }
            .lesson-item { 
                background: #333; padding: 15px; border-radius: 8px; 
                display: flex; justify-content: space-between; align-items: center;
                transition: all 0.3s;
            }
            .lesson-item:hover { background: #444; transform: translateX(5px); }
            .lesson-info { flex: 1; }
            .lesson-title { color: #fff; font-weight: bold; margin-bottom: 5px; }
            .lesson-desc { color: #ccc; font-size: 14px; }
            .lesson-status { 
                padding: 5px 10px; border-radius: 15px; font-size: 12px; font-weight: bold;
                margin-left: 15px;
            }
            .completed { background: #4CAF50; color: #fff; }
            .pending { background: #ff9800; color: #fff; }
            .locked { background: #666; color: #ccc; }
            .file-icon { margin-right: 8px; }
            .nav-bar { background: #222; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
            .nav-bar a { color: #ff6b35; text-decoration: none; margin-right: 20px; }
            .progress-bar { 
                background: #333; height: 8px; border-radius: 4px; margin: 10px 0;
                overflow: hidden;
            }
            .progress-fill { 
                background: linear-gradient(90deg, #ff6b35, #ff8c42); 
                height: 100%; transition: width 0.3s;
            }
        </style>
    </head>
    <body>
        <div class="nav-bar">
            <a href="/dashboard">← Dashboard</a>
            <a href="/courses">My Courses</a>
            <a href="/logout">Logout</a>
        </div>
        
        <div class="header">
            <div class="welcome">Welcome back, {{enrollment['full_name']}}!</div>
            <div class="course-info">You're enrolled in: <strong>{{enrollment['course_type']|title}} Course</strong></div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {{(progress|length / lessons|length * 100) if lessons else 0}}%"></div>
            </div>
            <div style="color: #ccc; font-size: 14px;">
                {{progress|length}} of {{lessons|length}} lessons completed
            </div>
        </div>
        
        <div class="modules">
            {% for module_name, module_lessons in modules.items() %}
            <div class="module-card">
                <div class="module-title">{{module_name}}</div>
                <div class="lessons">
                    {% for lesson in module_lessons %}
                    {% set lesson_key = enrollment['course_type'] + '_' + lesson['id']|string %}
                    {% set is_completed = progress_lookup.get(lesson_key, False) %}
                    <div class="lesson-item">
                        <div class="lesson-info">
                            <div class="lesson-title">
                                {{get_file_icon((lesson['file_path'] or '').split('/')[-1])}} {{lesson['lesson']}}
                            </div>
                            {% if lesson['description'] %}
                            <div class="lesson-desc">{{lesson['description']}}</div>
                            {% endif %}
                        </div>
                        <div class="lesson-status {{'completed' if is_completed else 'pending'}}">
                            {% if is_completed %}
                                ✅ Completed
                            {% else %}
                                <a href="{{url_for('view_lesson', lesson_id=lesson['id'])}}" style="color: inherit; text-decoration: none;">
                                    ▶️ Start Lesson
                                </a>
                            {% endif %}
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endfor %}
        </div>
        
        {% if not modules %}
        <div style="text-align: center; padding: 60px; color: #ccc;">
            <h3>No lessons available yet</h3>
            <p>Your course content is being prepared. Check back soon!</p>
        </div>
        {% endif %}
    </body>
    </html>
    ''', enrollment=enrollment, modules=modules, progress=progress, lessons=lessons, 
         progress_lookup=progress_lookup, get_file_icon=get_file_icon)

@app.route('/lesson/<int:lesson_id>')
def view_lesson(lesson_id):
    """View individual lesson"""
    enrollment = session.get('enrollment')
    if not enrollment:
        return redirect(url_for('pay'))
    
    conn = get_db_connection()
    lesson = conn.execute('SELECT * FROM lessons WHERE id = ?', (lesson_id,)).fetchone()
    
    if not lesson:
        conn.close()
        return "Lesson not found", 404
    
    # Check if lesson belongs to student's course
    if lesson['course'] != enrollment['course_type']:
        conn.close()
        return "Access denied", 403
    
    # Get next and previous lessons
    all_lessons = conn.execute('''
        SELECT *, COALESCE(order_index, 1) as order_index 
        FROM lessons 
        WHERE course = ? 
        ORDER BY module, order_index, lesson
    ''', (enrollment['course_type'],)).fetchall()
    
    current_index = None
    for i, l in enumerate(all_lessons):
        if l['id'] == lesson_id:
            current_index = i
            break
    
    next_lesson = all_lessons[current_index + 1] if current_index is not None and current_index + 1 < len(all_lessons) else None
    prev_lesson = all_lessons[current_index - 1] if current_index is not None and current_index > 0 else None
    
    conn.close()
    
    # Determine content type and render appropriately
    content_type = lesson['content_type'] if lesson['content_type'] else 'file'
    
    if content_type == 'markdown':
        # Render markdown content
        lesson_content = render_markdown_content(lesson['description'] if lesson['description'] else '')
    else:
        # Handle file-based content
        if lesson['file_path']:
            file_ext = (lesson['file_path'] or '').split('.')[-1].lower()
            file_url = (lesson['file_path'] or '').replace('static', '/static')
            
            if file_ext in ['mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv']:
                lesson_content = f'''
                <div class="video-container">
                    <video controls>
                        <source src="{file_url}" type="video/{file_ext}">
                        Your browser does not support the video tag.
                    </video>
                </div>
                '''
            elif file_ext in ['jpg', 'jpeg', 'png', 'gif', 'svg']:
                lesson_content = f'''
                <div style="text-align: center;">
                    <img src="{file_url}" style="max-width: 100%; border-radius: 8px;" alt="{lesson['lesson']}">
                </div>
                '''
            else:
                lesson_content = f'''
                <div class="file-download">
                    <h3>{get_file_icon(lesson['file_path'].split('/')[-1])} {lesson['file_path'].split('/')[-1]}</h3>
                    <p>This file cannot be displayed directly. Please download it to view.</p>
                    <a href="{file_url}" class="download-btn" download>Download File</a>
                </div>
                '''
        else:
            lesson_content = '<p>No content available for this lesson.</p>'
    
    return render_template_string('''
    <html>
    <head>
        <title>{{lesson['lesson']}} - Vibes University</title>
        <style>
            body { font-family: Arial, sans-serif; background: #111; color: #fff; margin: 0; padding: 20px; }
            .header { background: #222; padding: 20px; border-radius: 10px; margin-bottom: 30px; }
            .lesson-title { color: #ff6b35; font-size: 24px; margin-bottom: 10px; }
            .lesson-meta { color: #ccc; margin-bottom: 20px; }
            .content { background: #222; border-radius: 10px; padding: 30px; margin-bottom: 30px; }
            .video-container { position: relative; width: 100%; max-width: 800px; margin: 0 auto; }
            .video-container video { width: 100%; border-radius: 8px; }
            .file-download { 
                background: #333; padding: 20px; border-radius: 8px; text-align: center;
                border: 2px dashed #ff6b35;
            }
            .download-btn { 
                background: #ff6b35; color: #fff; padding: 15px 30px; 
                border: none; border-radius: 8px; font-size: 16px; font-weight: bold;
                text-decoration: none; display: inline-block; margin: 10px;
            }
            .download-btn:hover { background: #ff8c42; }
            .navigation { display: flex; justify-content: space-between; margin-top: 30px; }
            .nav-btn { 
                background: #333; color: #fff; padding: 12px 20px; 
                border: none; border-radius: 8px; text-decoration: none;
            }
            .nav-btn:hover { background: #444; }
            .nav-btn:disabled { background: #666; color: #999; cursor: not-allowed; }
            .back-link { color: #ff6b35; text-decoration: none; margin-bottom: 20px; display: inline-block; }
        </style>
    </head>
    <body>
        <a href="{{url_for('student_courses')}}" class="back-link">← Back to Courses</a>
        
        <div class="header">
            <div class="lesson-title">{{lesson['lesson']}}</div>
            <div class="lesson-meta">
                Course: {{lesson['course']|title}} | Module: {{lesson['module']}}
                {% if lesson['order_index'] %}<span style="margin-left: 15px;">Order: {{lesson['order_index']}}</span>{% endif %}
            </div>
        </div>
        
        <div class="content">
            {{lesson_content|safe}}
        </div>
        
        <div class="navigation">
            {% if prev_lesson %}
            <a href="{{url_for('view_lesson', lesson_id=prev_lesson['id'])}}" class="nav-btn">← Previous: {{prev_lesson['lesson']}}</a>
            {% else %}
            <button class="nav-btn" disabled>← Previous</button>
            {% endif %}
            
            <a href="{{url_for('student_courses')}}" class="nav-btn">Back to Courses</a>
            
            {% if next_lesson %}
            <a href="{{url_for('view_lesson', lesson_id=next_lesson['id'])}}" class="nav-btn">Next: {{next_lesson['lesson']}} →</a>
            {% else %}
            <button class="nav-btn" disabled>Next →</button>
            {% endif %}
        </div>
        
        <script>
            // Mark lesson as completed when video ends or content is viewed
            function markCompleted() {
                fetch('/api/mark-completed', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        user_id: {{enrollment['user_id']}},
                        course_id: '{{lesson['course']}}',
                        lesson_id: '{{lesson['id']}}'
                    })
                }).then(response => response.json())
                  .then(data => {
                      if (data.success) {
                          console.log('Lesson marked as completed');
                      }
                  });
            }
            
            // Mark as completed when video ends
            const video = document.querySelector('video');
            if (video) {
                video.addEventListener('ended', markCompleted);
            }
            
            // Mark as completed when download link is clicked
            const downloadBtn = document.querySelector('.download-btn');
            if (downloadBtn) {
                downloadBtn.addEventListener('click', markCompleted);
            }
            
            // Mark as completed when markdown content is viewed (after 30 seconds)
            {% if lesson['content_type'] == 'markdown' %}
            setTimeout(markCompleted, 30000);
            {% endif %}
        </script>
    </body>
    </html>
    ''', lesson=lesson, enrollment=enrollment, next_lesson=next_lesson, prev_lesson=prev_lesson, lesson_content=lesson_content)

@app.route('/api/mark-completed', methods=['POST'])
def mark_lesson_completed():
    """Mark a lesson as completed"""
    enrollment = session.get('enrollment')
    if not enrollment:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    user_id = data.get('user_id')
    course_id = data.get('course_id')
    lesson_id = data.get('lesson_id')
    
    if not all([user_id, course_id, lesson_id]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Verify user owns this enrollment
    if user_id != enrollment['user_id']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if already completed
    existing = conn.execute('''
        SELECT id FROM course_progress 
        WHERE user_id = ? AND course_id = ? AND lesson_id = ?
    ''', (user_id, course_id, lesson_id)).fetchone()
    
    if existing:
        # Update existing record
        cursor.execute('''
            UPDATE course_progress 
            SET completed = 1, completed_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND course_id = ? AND lesson_id = ?
        ''', (user_id, course_id, lesson_id))
    else:
        # Insert new record
        cursor.execute('''
            INSERT INTO course_progress (user_id, course_id, lesson_id, completed, completed_at)
            VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
        ''', (user_id, course_id, lesson_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Lesson marked as completed'})

@app.route('/logout')
def logout():
    """Logout user"""
    session.clear()
    return redirect(url_for('home'))

@app.route('/demo-payment', methods=['GET', 'POST'])
def demo_payment():
    """Demo payment route for testing student dashboard"""
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        plan_key = request.form.get('plan', 'course')
        
        # Create user if not exists
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if not user:
            password_hash = generate_password_hash(secrets.token_hex(8))
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (email, password_hash, full_name, phone)
                VALUES (?, ?, ?, ?)
            ''', (email, password_hash, name, phone))
            user_id = cursor.lastrowid
            conn.commit()
        else:
            user_id = user['id']
        
        # Create demo enrollment
        plans = {
            'course': {'name': 'Course Access', 'price': 100000},
            'online': {'name': 'Online Mentorship', 'price': 400000},
            'vip': {'name': 'VIP Physical Class', 'price': 2000000}
        }
        plan = plans.get(plan_key, plans['course'])
        
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO enrollments (user_id, course_type, price, payment_method, payment_status, payment_reference)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, plan_key, plan['price'], 'demo', 'completed', f'DEMO_{user_id}_{int(datetime.now().timestamp())}'))
        
        enrollment_id = cursor.lastrowid
        conn.commit()
        
        # Get enrollment details
        enrollment = conn.execute('''
            SELECT e.*, u.email, u.full_name 
            FROM enrollments e
            JOIN users u ON e.user_id = u.id
            WHERE e.id = ?
        ''', (enrollment_id,)).fetchone()
        
        conn.close()
        
        # Set session and redirect to dashboard
        session['enrollment'] = dict(enrollment)
        return redirect(url_for('dashboard'))
    
    return render_template_string('''
    <html>
    <head>
        <title>Demo Payment - Vibes University</title>
        <style>
            body { font-family: Arial, sans-serif; background: #111; color: #fff; }
            .container { max-width: 500px; margin: 60px auto; background: #222; padding: 40px; border-radius: 15px; box-shadow: 0 8px 32px #0008; }
            h2 { color: #ff6b35; }
            label { display: block; margin-top: 20px; }
            input, select { width: 100%; padding: 10px; margin-top: 5px; border-radius: 8px; border: none; background: #333; color: #fff; }
            .btn { background: linear-gradient(45deg, #ff6b35, #ff8c42); color: #fff; border: none; padding: 15px 0; width: 100%; border-radius: 8px; font-size: 1.1rem; margin-top: 30px; cursor: pointer; font-weight: bold; }
            .demo-notice { background: #333; color: #ff6b35; padding: 15px; border-radius: 8px; margin-top: 20px; text-align: center; border: 1px solid #ff6b35; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>🎯 Demo Payment - Test Student Dashboard</h2>
            <div class="demo-notice">
                <strong>Testing Mode:</strong> This will create a demo enrollment and take you directly to the student dashboard for testing purposes.
            </div>
            <form method="post">
                <label for="plan">Select Plan</label>
                <select name="plan" id="plan">
                    <option value="course">Course Access (₦100,000)</option>
                    <option value="online">Online Mentorship (₦400,000)</option>
                    <option value="vip">VIP Physical Class (₦2,000,000)</option>
                </select>
                <label for="name">Full Name</label>
                <input type="text" name="name" id="name" required>
                <label for="email">Email</label>
                <input type="email" name="email" id="email" required>
                <label for="phone">Phone</label>
                <input type="text" name="phone" id="phone" required>
                <button class="btn" type="submit">🚀 Access Student Dashboard</button>
            </form>
        </div>
    </body>
    </html>
    ''')

@app.route('/admin/users')
def admin_users():
    """Admin user management page"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    
    # Get all users with their enrollment info
    users = conn.execute('''
        SELECT u.*, 
               COUNT(e.id) as enrollment_count,
               SUM(CASE WHEN e.payment_status = 'completed' THEN 1 ELSE 0 END) as completed_enrollments,
               SUM(CASE WHEN e.payment_status = 'completed' THEN e.price ELSE 0 END) as total_spent
        FROM users u
        LEFT JOIN enrollments e ON u.id = e.user_id
        GROUP BY u.id
        ORDER BY u.created_at DESC
    ''').fetchall()
    
    conn.close()
    
    return render_template_string('''
    <html>
    <head>
        <title>User Management - Vibes University</title>
        <style>
            body { font-family: Arial, sans-serif; background: #111; color: #fff; margin: 0; padding: 20px; }
            .header { background: #222; padding: 20px; border-radius: 10px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: center; }
            .header h1 { color: #ff6b35; margin: 0; }
            .back-btn { background: #ff6b35; color: #fff; padding: 10px 20px; border: none; border-radius: 8px; text-decoration: none; font-weight: bold; }
            .table { width: 100%; border-collapse: collapse; background: #222; border-radius: 10px; overflow: hidden; }
            .table th, .table td { padding: 15px; text-align: left; border-bottom: 1px solid #444; }
            .table th { background: #333; color: #ff6b35; font-weight: bold; }
            .table tr:hover { background: #333; }
            .status-active { color: #4CAF50; }
            .status-inactive { color: #f44336; }
            .user-email { color: #ff6b35; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>👥 User Management</h1>
            <a href="{{url_for('admin_dashboard')}}" class="back-btn">← Back to Dashboard</a>
        </div>
        
        <table class="table">
            <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Phone</th>
                <th>Enrollments</th>
                <th>Completed</th>
                <th>Total Spent</th>
                <th>Joined</th>
                <th>Status</th>
            </tr>
            {% for user in users %}
            <tr>
                <td>{{user['full_name']}}</td>
                <td class="user-email">{{user['email']}}</td>
                <td>{{user['phone']}}</td>
                <td>{{user['enrollment_count']}}</td>
                <td>{{user['completed_enrollments']}}</td>
                <td>₦{{user['total_spent'] or 0}}</td>
                <td>{{user['created_at']}}</td>
                <td class="{{'status-active' if user['is_active'] else 'status-inactive'}}">
                    {{'Active' if user['is_active'] else 'Inactive'}}
                </td>
            </tr>
            {% endfor %}
        </table>
    </body>
    </html>
    ''', users=users)

@app.route('/admin/analytics')
def admin_analytics():
    """Admin analytics page"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    
    # Get monthly revenue data
    monthly_revenue = conn.execute('''
        SELECT strftime('%Y-%m', enrolled_at) as month,
               SUM(price) as revenue,
               COUNT(*) as enrollments
        FROM enrollments 
        WHERE payment_status = 'completed'
        GROUP BY strftime('%Y-%m', enrolled_at)
        ORDER BY month DESC
        LIMIT 12
    ''').fetchall()
    
    # Get course performance
    course_performance = conn.execute('''
        SELECT course_type,
               COUNT(*) as total_enrollments,
               SUM(CASE WHEN payment_status = 'completed' THEN 1 ELSE 0 END) as completed_enrollments,
               SUM(CASE WHEN payment_status = 'completed' THEN price ELSE 0 END) as revenue,
               AVG(CASE WHEN payment_status = 'completed' THEN price ELSE NULL END) as avg_revenue
        FROM enrollments
        GROUP BY course_type
    ''').fetchall()
    
    # Get lesson completion stats
    lesson_stats = conn.execute('''
        SELECT l.course, l.module, l.lesson,
               COUNT(cp.id) as completions
        FROM lessons l
        LEFT JOIN course_progress cp ON l.id = cp.lesson_id
        GROUP BY l.id
        ORDER BY completions DESC
        LIMIT 10
    ''').fetchall()
    
    conn.close()
    
    return render_template_string('''
    <html>
    <head>
        <title>Analytics - Vibes University</title>
        <style>
            body { font-family: Arial, sans-serif; background: #111; color: #fff; margin: 0; padding: 20px; }
            .header { background: #222; padding: 20px; border-radius: 10px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: center; }
            .header h1 { color: #ff6b35; margin: 0; }
            .back-btn { background: #ff6b35; color: #fff; padding: 10px 20px; border: none; border-radius: 8px; text-decoration: none; font-weight: bold; }
            .section { background: #222; padding: 20px; border-radius: 10px; margin-bottom: 30px; }
            .section h3 { color: #ff6b35; margin-top: 0; }
            .table { width: 100%; border-collapse: collapse; margin-top: 15px; }
            .table th, .table td { padding: 12px; text-align: left; border-bottom: 1px solid #444; }
            .table th { background: #333; color: #ff6b35; }
            .table tr:hover { background: #333; }
            .metric { background: #333; padding: 15px; border-radius: 8px; text-align: center; margin: 10px 0; }
            .metric-value { font-size: 1.5rem; font-weight: bold; color: #ff6b35; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📊 Analytics Dashboard</h1>
            <a href="{{url_for('admin_dashboard')}}" class="back-btn">← Back to Dashboard</a>
        </div>
        
        <div class="section">
            <h3>💰 Monthly Revenue</h3>
            <table class="table">
                <tr>
                    <th>Month</th>
                    <th>Revenue</th>
                    <th>Enrollments</th>
                </tr>
                {% for month in monthly_revenue %}
                <tr>
                    <td>{{month['month']}}</td>
                    <td>₦{{month['revenue']}}</td>
                    <td>{{month['enrollments']}}</td>
                </tr>
                {% endfor %}
            </table>
        </div>
        
        <div class="section">
            <h3>🎯 Course Performance</h3>
            <table class="table">
                <tr>
                    <th>Course</th>
                    <th>Total Enrollments</th>
                    <th>Completed</th>
                    <th>Revenue</th>
                    <th>Avg Revenue</th>
                </tr>
                {% for course in course_performance %}
                <tr>
                    <td>{{course['course_type']|title}}</td>
                    <td>{{course['total_enrollments']}}</td>
                    <td>{{course['completed_enrollments']}}</td>
                    <td>₦{{course['revenue']}}</td>
                    <td>₦{{course['avg_revenue'] or 0}}</td>
                </tr>
                {% endfor %}
            </table>
        </div>
        
        <div class="section">
            <h3>📚 Top Performing Lessons</h3>
            <table class="table">
                <tr>
                    <th>Course</th>
                    <th>Module</th>
                    <th>Lesson</th>
                    <th>Completions</th>
                </tr>
                {% for lesson in lesson_stats %}
                <tr>
                    <td>{{lesson['course']|title}}</td>
                    <td>{{lesson['module']}}</td>
                    <td>{{lesson['lesson']}}</td>
                    <td>{{lesson['completions']}}</td>
                </tr>
                {% endfor %}
            </table>
        </div>
    </body>
    </html>
    ''', monthly_revenue=monthly_revenue, course_performance=course_performance, lesson_stats=lesson_stats)

@app.route('/admin/settings')
def admin_settings():
    """Admin settings page"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    message = ''
    if request.method == 'POST':
        # Handle settings updates
        new_password = request.form.get('new_password')
        if new_password:
            # Update admin password (in production, use environment variables)
            global ADMIN_PASSWORD
            ADMIN_PASSWORD = new_password
            message = 'Admin password updated successfully!'
    
    return render_template_string('''
    <html>
    <head>
        <title>Settings - Vibes University</title>
        <style>
            body { font-family: Arial, sans-serif; background: #111; color: #fff; margin: 0; padding: 20px; }
            .header { background: #222; padding: 20px; border-radius: 10px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: center; }
            .header h1 { color: #ff6b35; margin: 0; }
            .back-btn { background: #ff6b35; color: #fff; padding: 10px 20px; border: none; border-radius: 8px; text-decoration: none; font-weight: bold; }
            .section { background: #222; padding: 20px; border-radius: 10px; margin-bottom: 30px; }
            .section h3 { color: #ff6b35; margin-top: 0; }
            .form-group { margin-bottom: 15px; }
            .form-group label { display: block; margin-bottom: 5px; color: #ccc; }
            .form-group input { width: 100%; padding: 10px; border-radius: 8px; border: none; background: #444; color: #fff; }
            .save-btn { background: #4CAF50; color: #fff; padding: 12px 30px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; }
            .success-msg { background: #4CAF50; color: #fff; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>⚙️ System Settings</h1>
            <a href="{{url_for('admin_dashboard')}}" class="back-btn">← Back to Dashboard</a>
        </div>
        
        {% if message %}<div class="success-msg">{{message}}</div>{% endif %}
        
        <div class="section">
            <h3>🔐 Security Settings</h3>
            <form method="post">
                <div class="form-group">
                    <label>New Admin Password:</label>
                    <input type="password" name="new_password" placeholder="Enter new admin password">
                </div>
                <button type="submit" class="save-btn">💾 Save Changes</button>
            </form>
        </div>
        
        <div class="section">
            <h3>🔗 Quick Links</h3>
            <p><a href="{{url_for('admin_users')}}" style="color: #ff6b35;">👥 Manage Users</a></p>
            <p><a href="{{url_for('admin_analytics')}}" style="color: #ff6b35;">📊 View Analytics</a></p>
            <p><a href="/demo-payment" style="color: #ff6b35;">🎯 Test Student Dashboard</a></p>
        </div>
    </body>
    </html>
    ''', message=message)

@app.route('/admin/preview/<course_type>')
def admin_preview_course(course_type):
    """Admin course preview - view course as a student would see it"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    
    # Get all lessons for the specified course type
    lessons = conn.execute('''
        SELECT * FROM lessons 
        WHERE course = ? 
        ORDER BY module, lesson
    ''', (course_type,)).fetchall()
    
    # Organize lessons by module
    modules = {}
    for lesson in lessons:
        module_name = lesson['module']
        if module_name not in modules:
            modules[module_name] = []
        modules[module_name].append(lesson)
    
    conn.close()
    
    return render_template_string('''
    <html>
    <head>
        <title>Course Preview - {{course_type|title}} - Vibes University</title>
        <style>
            body { font-family: Arial, sans-serif; background: #111; color: #fff; margin: 0; padding: 20px; }
            .header { background: #222; padding: 20px; border-radius: 10px; margin-bottom: 30px; }
            .preview-title { color: #ff6b35; font-size: 24px; margin-bottom: 10px; }
            .course-info { color: #ccc; margin-bottom: 20px; }
            .modules { display: grid; gap: 20px; }
            .module-card { background: #222; border-radius: 10px; padding: 20px; border-left: 4px solid #ff6b35; }
            .module-title { color: #ff6b35; font-size: 20px; margin-bottom: 15px; }
            .lessons { display: grid; gap: 10px; }
            .lesson-item { 
                background: #333; padding: 15px; border-radius: 8px; 
                display: flex; justify-content: space-between; align-items: center;
                transition: all 0.3s;
            }
            .lesson-item:hover { background: #444; transform: translateX(5px); }
            .lesson-info { flex: 1; }
            .lesson-title { color: #fff; font-weight: bold; margin-bottom: 5px; }
            .lesson-desc { color: #ccc; font-size: 14px; }
            .lesson-status { 
                padding: 5px 10px; border-radius: 15px; font-size: 12px; font-weight: bold;
                margin-left: 15px;
                background: #666; color: #ccc;
            }
            .file-icon { margin-right: 8px; }
            .nav-bar { background: #222; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
            .nav-bar a { color: #ff6b35; text-decoration: none; margin-right: 20px; }
            .preview-notice { 
                background: #333; color: #ff6b35; padding: 15px; border-radius: 8px; 
                margin-bottom: 20px; border: 1px solid #ff6b35;
            }
            .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 20px; }
            .stat-card { background: #333; padding: 15px; border-radius: 8px; text-align: center; }
            .stat-number { font-size: 1.5rem; font-weight: bold; color: #ff6b35; }
        </style>
    </head>
    <body>
        <div class="nav-bar">
            <a href="{{url_for('admin_dashboard')}}">← Back to Admin Dashboard</a>
            <a href="{{url_for('admin_preview_course', course_type='course')}}">Course Access</a>
            <a href="{{url_for('admin_preview_course', course_type='online')}}">Online Mentorship</a>
            <a href="{{url_for('admin_preview_course', course_type='vip')}}">VIP Physical Class</a>
        </div>
        
        <div class="preview-notice">
            <strong>👁️ Admin Preview Mode:</strong> This is how students will see the {{course_type|title}} course content.
        </div>
        
        <div class="header">
            <div class="preview-title">{{course_type|title}} Course Preview</div>
            <div class="course-info">Course Type: <strong>{{course_type|title}}</strong></div>
            
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number">{{modules|length}}</div>
                    <div>Modules</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{{lessons|length}}</div>
                    <div>Total Lessons</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{{course_type|title}}</div>
                    <div>Course Type</div>
                </div>
            </div>
        </div>
        
        <div class="modules">
            {% for module_name, module_lessons in modules.items() %}
            <div class="module-card">
                <div class="module-title">{{module_name}}</div>
                <div class="lessons">
                    {% for lesson in module_lessons %}
                    <div class="lesson-item">
                        <div class="lesson-info">
                            <div class="lesson-title">
                                {{get_file_icon((lesson['file_path'] or '').split('/')[-1])}} {{lesson['lesson']}}
                            </div>
                            {% if lesson['description'] %}
                            <div class="lesson-desc">{{lesson['description']}}</div>
                            {% endif %}
                        </div>
                        <div class="lesson-status">
                            <a href="{{url_for('admin_preview_lesson', lesson_id=lesson['id'])}}" style="color: inherit; text-decoration: none;">
                                👁️ Preview
                            </a>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endfor %}
        </div>
        
        {% if not modules %}
        <div style="text-align: center; padding: 60px; color: #ccc;">
            <h3>No lessons available for {{course_type|title}} course</h3>
            <p>Upload some lessons to see the preview.</p>
            <a href="{{url_for('admin_dashboard')}}" style="color: #ff6b35;">Go to Admin Dashboard</a>
        </div>
        {% endif %}
    </body>
    </html>
    ''', course_type=course_type, modules=modules, lessons=lessons, get_file_icon=get_file_icon)

@app.route('/admin/preview/lesson/<int:lesson_id>')
def admin_preview_lesson(lesson_id):
    """Admin lesson preview - view individual lesson as a student would see it"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    lesson = conn.execute('SELECT * FROM lessons WHERE id = ?', (lesson_id,)).fetchone()
    
    if not lesson:
        conn.close()
        return "Lesson not found", 404
    
    # Get next and previous lessons
    all_lessons = conn.execute('''
        SELECT *, COALESCE(order_index, 1) as order_index 
        FROM lessons 
        WHERE course = ? 
        ORDER BY module, order_index, lesson
    ''', (lesson['course'],)).fetchall()
    
    current_index = None
    for i, l in enumerate(all_lessons):
        if l['id'] == lesson_id:
            current_index = i
            break
    
    next_lesson = all_lessons[current_index + 1] if current_index is not None and current_index + 1 < len(all_lessons) else None
    prev_lesson = all_lessons[current_index - 1] if current_index is not None and current_index > 0 else None
    
    conn.close()
    
    # Determine file type and render appropriately
    file_ext = (lesson['file_path'] or '').split('.')[-1].lower()
    file_url = (lesson['file_path'] or '').replace('static', '/static')
    
    return render_template_string('''
    <html>
    <head>
        <title>{{lesson['lesson']}} - Admin Preview - Vibes University</title>
        <style>
            body { font-family: Arial, sans-serif; background: #111; color: #fff; margin: 0; padding: 20px; }
            .header { background: #222; padding: 20px; border-radius: 10px; margin-bottom: 30px; }
            .lesson-title { color: #ff6b35; font-size: 24px; margin-bottom: 10px; }
            .lesson-meta { color: #ccc; margin-bottom: 20px; }
            .content { background: #222; border-radius: 10px; padding: 30px; margin-bottom: 30px; }
            .video-container { position: relative; width: 100%; max-width: 800px; margin: 0 auto; }
            .video-container video { width: 100%; border-radius: 8px; }
            .file-download { 
                background: #333; padding: 20px; border-radius: 8px; text-align: center;
                border: 2px dashed #ff6b35;
            }
            .download-btn { 
                background: #ff6b35; color: #fff; padding: 15px 30px; 
                border: none; border-radius: 8px; font-size: 16px; font-weight: bold;
                text-decoration: none; display: inline-block; margin: 10px;
            }
            .download-btn:hover { background: #ff8c42; }
            .navigation { display: flex; justify-content: space-between; margin-top: 30px; }
            .nav-btn { 
                background: #333; color: #fff; padding: 12px 20px; 
                border: none; border-radius: 8px; text-decoration: none;
            }
            .nav-btn:hover { background: #444; }
            .nav-btn:disabled { background: #666; color: #999; cursor: not-allowed; }
            .description { color: #ccc; line-height: 1.6; margin: 20px 0; }
            .back-link { color: #ff6b35; text-decoration: none; margin-bottom: 20px; display: inline-block; }
            .preview-notice { 
                background: #333; color: #ff6b35; padding: 15px; border-radius: 8px; 
                margin-bottom: 20px; border: 1px solid #ff6b35;
            }
        </style>
    </head>
    <body>
        <div class="preview-notice">
            <strong>👁️ Admin Preview Mode:</strong> This is how students will see this lesson.
        </div>
        
        <a href="{{url_for('admin_preview_course', course_type=lesson['course'])}}" class="back-link">← Back to Course Preview</a>
        
        <div class="header">
            <div class="lesson-title">{{lesson['lesson']}}</div>
            <div class="lesson-meta">
                Course: {{lesson['course']|title}} | Module: {{lesson['module']}}
            </div>
        </div>
        
        <div class="content">
            {% if lesson['description'] %}
            <div class="description">{{lesson['description']}}</div>
            {% endif %}
            
            {% if file_ext in ['mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv'] %}
            <div class="video-container">
                <video controls>
                    <source src="{{file_url}}" type="video/{{file_ext}}">
                    Your browser does not support the video tag.
                </video>
            </div>
            {% elif file_ext in ['jpg', 'jpeg', 'png', 'gif', 'svg'] %}
            <div style="text-align: center;">
                <img src="{{file_url}}" style="max-width: 100%; border-radius: 8px;" alt="{{lesson['lesson']}}">
            </div>
            {% else %}
            <div class="file-download">
                <h3>{{get_file_icon(lesson['file_path'].split('/')[-1])}} {{(lesson['file_path'] or '').split('/')[-1]}}</h3>
                <p>This file cannot be displayed directly. Students will download it to view.</p>
                <a href="{{file_url}}" class="download-btn" download>Download File</a>
            </div>
            {% endif %}
        </div>
        
        <div class="navigation">
            {% if prev_lesson %}
            <a href="{{url_for('admin_preview_lesson', lesson_id=prev_lesson['id'])}}" class="nav-btn">← Previous: {{prev_lesson['lesson']}}</a>
            {% else %}
            <button class="nav-btn" disabled>← Previous</button>
            {% endif %}
            
            <a href="{{url_for('admin_preview_course', course_type=lesson['course'])}}" class="nav-btn">Back to Course</a>
            
            {% if next_lesson %}
            <a href="{{url_for('admin_preview_lesson', lesson_id=next_lesson['id'])}}" class="nav-btn">Next: {{next_lesson['lesson']}} →</a>
            {% else %}
            <button class="nav-btn" disabled>Next →</button>
            {% endif %}
        </div>
    </body>
    </html>
    ''', lesson=lesson, next_lesson=next_lesson, prev_lesson=prev_lesson, get_file_icon=get_file_icon)

@app.route('/admin/course-builder', methods=['GET', 'POST'])
def admin_course_builder():
    """Admin course builder - create lessons with markdown content"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    message = ''
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create_lesson':
            course = request.form.get('course')
            module = request.form.get('module')
            lesson_title = request.form.get('lesson_title')
            content = request.form.get('content')
            order_index = request.form.get('order_index', 1)
            
            if not all([course, module, lesson_title, content]):
                message = 'All fields are required.'
            else:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO lessons (course, module, lesson, description, content_type, order_index)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (course, module, lesson_title, content, 'markdown', order_index))
                conn.commit()
                message = 'Lesson created successfully!'
        
        elif action == 'update_lesson':
            lesson_id = request.form.get('lesson_id')
            course = request.form.get('course')
            module = request.form.get('module')
            lesson_title = request.form.get('lesson_title')
            content = request.form.get('content')
            order_index = request.form.get('order_index', 1)
            
            if not all([lesson_id, course, module, lesson_title, content]):
                message = 'All fields are required.'
            else:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE lessons 
                    SET course = ?, module = ?, lesson = ?, description = ?, order_index = ?
                    WHERE id = ?
                ''', (course, module, lesson_title, content, order_index, lesson_id))
                conn.commit()
                message = 'Lesson updated successfully!'
    
    # Get all lessons organized by course and module
    lessons = conn.execute('''
        SELECT *, COALESCE(order_index, 1) as order_index 
        FROM lessons 
        ORDER BY course, module, order_index, lesson
    ''').fetchall()
    
    # Organize lessons by course and module
    courses = {}
    for lesson in lessons:
        course_name = lesson['course']
        if course_name not in courses:
            courses[course_name] = {}
        
        module_name = lesson['module']
        if module_name not in courses[course_name]:
            courses[course_name][module_name] = []
        
        courses[course_name][module_name].append(lesson)
    
    conn.close()
    
    return render_template_string('''
    <html>
    <head>
        <title>Course Builder - Vibes University</title>
        <style>
            body { font-family: Arial, sans-serif; background: #111; color: #fff; margin: 0; padding: 20px; }
            .header { background: #222; padding: 20px; border-radius: 10px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: center; }
            .header h1 { color: #ff6b35; margin: 0; }
            .back-btn { background: #ff6b35; color: #fff; padding: 10px 20px; border: none; border-radius: 8px; text-decoration: none; font-weight: bold; }
            .section { background: #222; padding: 20px; border-radius: 10px; margin-bottom: 30px; }
            .section h3 { color: #ff6b35; margin-top: 0; }
            .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
            .form-group { margin-bottom: 15px; }
            .form-group label { display: block; margin-bottom: 5px; color: #ccc; }
            .form-group input, .form-group select, .form-group textarea { 
                width: 100%; padding: 10px; border-radius: 8px; border: none; background: #444; color: #fff; 
            }
            .form-group textarea { min-height: 300px; font-family: 'Courier New', monospace; }
            .btn { background: #4CAF50; color: #fff; padding: 12px 30px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; }
            .btn-secondary { background: #666; }
            .success-msg { background: #4CAF50; color: #fff; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
            .course-tabs { display: flex; gap: 10px; margin-bottom: 20px; }
            .course-tab { 
                background: #333; color: #fff; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer;
            }
            .course-tab.active { background: #ff6b35; }
            .lesson-list { background: #333; padding: 15px; border-radius: 8px; margin: 10px 0; }
            .lesson-item { 
                background: #444; padding: 10px; border-radius: 5px; margin: 5px 0; 
                display: flex; justify-content: space-between; align-items: center;
            }
            .lesson-actions { display: flex; gap: 5px; }
            .action-btn { 
                padding: 5px 10px; border: none; border-radius: 3px; text-decoration: none; font-size: 12px;
            }
            .edit-btn { background: #4CAF50; color: #fff; }
            .delete-btn { background: #f44336; color: #fff; }
            .preview-btn { background: #2196F3; color: #fff; }
            .markdown-help { 
                background: #333; padding: 15px; border-radius: 8px; margin-top: 10px; 
                border-left: 4px solid #ff6b35;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📝 Course Builder</h1>
            <a href="{{url_for('admin_dashboard')}}" class="back-btn">← Back to Dashboard</a>
        </div>
        
        {% if message %}<div class="success-msg">{{message}}</div>{% endif %}
        
        <div class="section">
            <h3>➕ Create New Lesson</h3>
            <form method="post">
                <input type="hidden" name="action" value="create_lesson">
                <div class="form-grid">
                    <div class="form-group">
                        <label>Course:</label>
                        <select name="course" required>
                            <option value="">Select Course</option>
                            {% for c in courses %}
                                <option value="{{c['name']}}">{{c['name']}}</option>
                            {% endfor %}
                        </select>
                        <a href="{{url_for('admin_courses')}}" style="color:#4CAF50; margin-left:10px; font-size:14px; text-decoration:none;">➕ Add New Course</a>
                    </div>
                    <div class="form-group">
                        <label>Module:</label>
                        <select name="module" required>
                            {% for i in range(1, 16) %}
                                <option value="Module {{i}}">Module {{i}}</option>
                            {% endfor %}
                        </select>
                    </div>
                </div>
                <div class="form-group">
                    <label>Lesson Title:</label>
                    <input type="text" name="lesson_title" placeholder="e.g., Getting Started with AI" required>
                </div>
                <div class="form-group">
                    <label>Order Index:</label>
                    <input type="number" name="order_index" value="1" min="1" required>
                </div>
                <div class="form-group">
                    <label>Lesson Content (Markdown):</label>
                    <textarea name="content" placeholder="Write your lesson content in markdown format..." required></textarea>
                </div>
                <button type="submit" class="btn">📝 Create Lesson</button>
            </form>
            
            <div class="markdown-help">
                <h4>📖 Markdown Guide:</h4>
                <p><strong>Headers:</strong> # H1, ## H2, ### H3</p>
                <p><strong>Bold:</strong> **text** or __text__</p>
                <p><strong>Italic:</strong> *text* or _text_</p>
                <p><strong>Lists:</strong> - item or 1. item</p>
                <p><strong>Links:</strong> [text](url)</p>
                <p><strong>Images:</strong> ![alt](image_url)</p>
                <p><strong>Videos:</strong> Use YouTube embed: &lt;iframe src="youtube_url"&gt;&lt;/iframe&gt;</p>
                <p><strong>Code:</strong> `code` or ```code block```</p>
            </div>
        </div>
        
        <div class="section">
            <h3>📚 Course Content</h3>
            {% for course_name, modules in courses.items() %}
            <div class="course-section">
                <h4 style="color: #ff6b35; margin-bottom: 15px;">{{course_name|title}} Course</h4>
                {% for module_name, module_lessons in modules.items() %}
                <div class="lesson-list">
                    <h5 style="color: #ccc; margin-bottom: 10px;">{{module_name}}</h5>
                    {% for lesson in module_lessons %}
                    <div class="lesson-item">
                        <div>
                            <strong>{{lesson['lesson']}}</strong>
                            <span style="color: #666; font-size: 12px;">(Order: {{lesson['order_index']}})</span>
                        </div>
                        <div class="lesson-actions">
                            <a href="{{url_for('admin_edit_lesson_content', lesson_id=lesson['id'])}}" class="action-btn edit-btn">✏️ Edit</a>
                            <a href="{{url_for('admin_preview_lesson', lesson_id=lesson['id'])}}" class="action-btn preview-btn">👁️ Preview</a>
                            <a href="{{url_for('admin_delete_lesson', lesson_id=lesson['id'])}}" 
                               onclick="return confirm('Are you sure you want to delete this lesson?')" 
                               class="action-btn delete-btn">🗑️ Delete</a>
                        </div>
                    </div>
                    {% endfor %}
                </div>
                {% endfor %}
            </div>
            {% endfor %}
        </div>
    </body>
    </html>
    ''', message=message, courses=courses)

@app.route('/admin/edit-lesson-content/<int:lesson_id>', methods=['GET', 'POST'])
def admin_edit_lesson_content(lesson_id):
    """Edit lesson content with markdown"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    lesson = conn.execute('SELECT * FROM lessons WHERE id = ?', (lesson_id,)).fetchone()
    
    if not lesson:
        conn.close()
        return "Lesson not found", 404
    
    message = ''
    if request.method == 'POST':
        course = request.form.get('course')
        module = request.form.get('module')
        lesson_title = request.form.get('lesson_title')
        content = request.form.get('content')
        order_index = request.form.get('order_index', 1)
        
        if not all([course, module, lesson_title, content]):
            message = 'All fields are required.'
        else:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE lessons 
                SET course = ?, module = ?, lesson = ?, description = ?, order_index = ?
                WHERE id = ?
            ''', (course, module, lesson_title, content, order_index, lesson_id))
            conn.commit()
            message = 'Lesson updated successfully!'
            lesson = conn.execute('SELECT * FROM lessons WHERE id = ?', (lesson_id,)).fetchone()
    
    conn.close()
    
    return render_template_string('''
    <html>
    <head>
        <title>Edit Lesson - Vibes University</title>
        <style>
            body { font-family: Arial, sans-serif; background: #111; color: #fff; margin: 0; padding: 20px; }
            .header { background: #222; padding: 20px; border-radius: 10px; margin-bottom: 30px; }
            .header h1 { color: #ff6b35; margin: 0; }
            .back-btn { background: #ff6b35; color: #fff; padding: 10px 20px; border: none; border-radius: 8px; text-decoration: none; font-weight: bold; }
            .form-container { background: #222; padding: 30px; border-radius: 12px; max-width: 800px; margin: 0 auto; }
            .form-group { margin-bottom: 15px; }
            .form-group label { display: block; margin-bottom: 5px; color: #ccc; }
            .form-group input, .form-group select, .form-group textarea { 
                width: 100%; padding: 10px; border-radius: 8px; border: none; background: #444; color: #fff; 
            }
            .form-group textarea { min-height: 400px; font-family: 'Courier New', monospace; }
            .btn { background: #4CAF50; color: #fff; padding: 12px 30px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; }
            .success-msg { background: #4CAF50; color: #fff; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>✏️ Edit Lesson: {{lesson['lesson']}}</h1>
            <a href="{{url_for('admin_course_builder')}}" class="back-btn">← Back to Course Builder</a>
        </div>
        
        {% if message %}<div class="success-msg">{{message}}</div>{% endif %}
        
        <div class="form-container">
            <form method="post">
                <input type="hidden" name="action" value="update_lesson">
                <input type="hidden" name="lesson_id" value="{{lesson['id']}}">
                
                <div class="form-group">
                    <label>Course:</label>
                    <select name="course" required>
                        <option value="course" {{'selected' if lesson['course'] == 'course' else ''}}>Course Access</option>
                        <option value="online" {{'selected' if lesson['course'] == 'online' else ''}}>Online Mentorship</option>
                        <option value="vip" {{'selected' if lesson['course'] == 'vip' else ''}}>VIP Physical Class</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label>Module:</label>
                    <input type="text" name="module" value="{{lesson['module']}}" required>
                </div>
                
                <div class="form-group">
                    <label>Lesson Title:</label>
                    <input type="text" name="lesson_title" value="{{lesson['lesson']}}" required>
                </div>
                
                <div class="form-group">
                    <label>Order Index:</label>
                    <input type="number" name="order_index" value="{{lesson['order_index'] or 1}}" min="1" required>
                </div>
                
                <div class="form-group">
                    <label>Lesson Content (Markdown):</label>
                    <textarea name="content" required>{{lesson['description'] or ''}}</textarea>
                </div>
                
                <button type="submit" class="btn">💾 Update Lesson</button>
            </form>
        </div>
    </body>
    </html>
    ''', lesson=lesson, message=message)

def render_markdown_content(content):
    """Render markdown content with embedded videos and images"""
    if not content:
        return ""
    
    # Convert markdown to HTML
    md = markdown.Markdown(extensions=['fenced_code', 'tables', 'codehilite'])
    html_content = md.convert(content)
    
    # Process embedded videos (YouTube, Vimeo, etc.)
    # Look for iframe patterns and make them responsive
    iframe_pattern = r'<iframe[^>]*src="([^"]*)"[^>]*></iframe>'
    def make_iframe_responsive(match):
        src = match.group(1)
        return f'''
        <div style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%; margin: 20px 0;">
            <iframe src="{src}" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: 0;" allowfullscreen></iframe>
        </div>
        '''
    
    html_content = re.sub(iframe_pattern, make_iframe_responsive, html_content)
    
    # Add custom styling for markdown content
    styled_content = f'''
    <style>
        .markdown-content {{
            line-height: 1.6;
            color: #fff;
        }}
        .markdown-content h1, .markdown-content h2, .markdown-content h3, 
        .markdown-content h4, .markdown-content h5, .markdown-content h6 {{
            color: #ff6b35;
            margin-top: 30px;
            margin-bottom: 15px;
        }}
        .markdown-content h1 {{ font-size: 2em; }}
        .markdown-content h2 {{ font-size: 1.5em; }}
        .markdown-content h3 {{ font-size: 1.3em; }}
        .markdown-content p {{ margin-bottom: 15px; }}
        .markdown-content ul, .markdown-content ol {{ margin-bottom: 15px; padding-left: 20px; }}
        .markdown-content li {{ margin-bottom: 5px; }}
        .markdown-content code {{
            background: #333;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
        }}
        .markdown-content pre {{
            background: #333;
            padding: 15px;
            border-radius: 8px;
            overflow-x: auto;
            margin: 20px 0;
        }}
        .markdown-content pre code {{
            background: none;
            padding: 0;
        }}
        .markdown-content blockquote {{
            border-left: 4px solid #ff6b35;
            padding-left: 15px;
            margin: 20px 0;
            color: #ccc;
        }}
        .markdown-content img {{
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            margin: 15px 0;
        }}
        .markdown-content table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        .markdown-content th, .markdown-content td {{
            border: 1px solid #444;
            padding: 10px;
            text-align: left;
        }}
        .markdown-content th {{
            background: #333;
            color: #ff6b35;
        }}
    </style>
    <div class="markdown-content">
        {html_content}
    </div>
    '''
    
    return styled_content

@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
    """Student login page"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            return render_template_string('''
            <html>
            <head>
                <title>Student Login - Vibes University</title>
                <style>
                    body { font-family: Arial, sans-serif; background: #111; color: #fff; margin: 0; padding: 20px; }
                    .login-container { max-width: 400px; margin: 100px auto; background: #222; padding: 40px; border-radius: 15px; }
                    .header { text-align: center; margin-bottom: 30px; }
                    .header h1 { color: #ff6b35; margin: 0; }
                    .form-group { margin-bottom: 20px; }
                    .form-group label { display: block; margin-bottom: 8px; color: #ccc; }
                    .form-group input { width: 100%; padding: 12px; border-radius: 8px; border: none; background: #333; color: #fff; box-sizing: border-box; }
                    .login-btn { width: 100%; background: #ff6b35; color: #fff; padding: 15px; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; }
                    .login-btn:hover { background: #ff8c42; }
                    .error { background: #f44336; color: #fff; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
                    .links { text-align: center; margin-top: 20px; }
                    .links a { color: #ff6b35; text-decoration: none; margin: 0 10px; }
                </style>
            </head>
            <body>
                <div class="login-container">
                    <div class="header">
                        <h1>🎓 Student Login</h1>
                        <p>Welcome back to Vibes University</p>
                    </div>
                    
                    <div class="error">Email and password are required</div>
                    
                    <form method="post">
                        <div class="form-group">
                            <label>Email Address:</label>
                            <input type="email" name="email" value="{{email}}" required>
                        </div>
                        <div class="form-group">
                            <label>Password:</label>
                            <input type="password" name="password" required>
                        </div>
                        <button type="submit" class="login-btn">Login to My Courses</button>
                    </form>
                    
                    <div class="links">
                        <a href="/pay">New Student? Enroll Here</a>
                        <a href="/">Back to Home</a>
                    </div>
                </div>
            </body>
            </html>
            ''', email=email)
        
        # Verify user credentials
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        
        if not user or not check_password_hash(user['password_hash'], password):
            conn.close()
            return render_template_string('''
            <html>
            <head>
                <title>Student Login - Vibes University</title>
                <style>
                    body { font-family: Arial, sans-serif; background: #111; color: #fff; margin: 0; padding: 20px; }
                    .login-container { max-width: 400px; margin: 100px auto; background: #222; padding: 40px; border-radius: 15px; }
                    .header { text-align: center; margin-bottom: 30px; }
                    .header h1 { color: #ff6b35; margin: 0; }
                    .form-group { margin-bottom: 20px; }
                    .form-group label { display: block; margin-bottom: 8px; color: #ccc; }
                    .form-group input { width: 100%; padding: 12px; border-radius: 8px; border: none; background: #333; color: #fff; box-sizing: border-box; }
                    .login-btn { width: 100%; background: #ff6b35; color: #fff; padding: 15px; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; }
                    .login-btn:hover { background: #ff8c42; }
                    .error { background: #f44336; color: #fff; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
                    .links { text-align: center; margin-top: 20px; }
                    .links a { color: #ff6b35; text-decoration: none; margin: 0 10px; }
                </style>
            </head>
            <body>
                <div class="login-container">
                    <div class="header">
                        <h1>🎓 Student Login</h1>
                        <p>Welcome back to Vibes University</p>
                    </div>
                    
                    <div class="error">Invalid email or password. Please try again.</div>
                    
                    <form method="post">
                        <div class="form-group">
                            <label>Email Address:</label>
                            <input type="email" name="email" value="{{email}}" required>
                        </div>
                        <div class="form-group">
                            <label>Password:</label>
                            <input type="password" name="password" required>
                        </div>
                        <button type="submit" class="login-btn">Login to My Courses</button>
                    </form>
                    
                    <div class="links">
                        <a href="/pay">New Student? Enroll Here</a>
                        <a href="/">Back to Home</a>
                    </div>
                </div>
            </body>
            </html>
            ''', email=email)
        
        # Check if user has any completed enrollments
        enrollment = conn.execute('''
            SELECT e.*, u.full_name, u.email 
            FROM enrollments e 
            JOIN users u ON e.user_id = u.id 
            WHERE e.user_id = ? AND e.payment_status = 'completed'
            ORDER BY e.enrolled_at DESC 
            LIMIT 1
        ''', (user['id'],)).fetchone()
        
        conn.close()
        
        if not enrollment:
            return render_template_string('''
            <html>
            <head>
                <title>Student Login - Vibes University</title>
                <style>
                    body { font-family: Arial, sans-serif; background: #111; color: #fff; margin: 0; padding: 20px; }
                    .login-container { max-width: 400px; margin: 100px auto; background: #222; padding: 40px; border-radius: 15px; }
                    .header { text-align: center; margin-bottom: 30px; }
                    .header h1 { color: #ff6b35; margin: 0; }
                    .form-group { margin-bottom: 20px; }
                    .form-group label { display: block; margin-bottom: 8px; color: #ccc; }
                    .form-group input { width: 100%; padding: 12px; border-radius: 8px; border: none; background: #333; color: #fff; box-sizing: border-box; }
                    .login-btn { width: 100%; background: #ff6b35; color: #fff; padding: 15px; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; }
                    .login-btn:hover { background: #ff8c42; }
                    .error { background: #f44336; color: #fff; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
                    .links { text-align: center; margin-top: 20px; }
                    .links a { color: #ff6b35; text-decoration: none; margin: 0 10px; }
                </style>
            </head>
            <body>
                <div class="login-container">
                    <div class="header">
                        <h1>🎓 Student Login</h1>
                        <p>Welcome back to Vibes University</p>
                    </div>
                    
                    <div class="error">No active course enrollment found. Please enroll in a course first.</div>
                    
                    <form method="post">
                        <div class="form-group">
                            <label>Email Address:</label>
                            <input type="email" name="email" value="{{email}}" required>
                        </div>
                        <div class="form-group">
                            <label>Password:</label>
                            <input type="password" name="password" required>
                        </div>
                        <button type="submit" class="login-btn">Login to My Courses</button>
                    </form>
                    
                    <div class="links">
                        <a href="/pay">New Student? Enroll Here</a>
                        <a href="/">Back to Home</a>
                    </div>
                </div>
            </body>
            </html>
            ''', email=email)
        
        # Store enrollment in session
        session['enrollment'] = dict(enrollment)
        session['enrollment']['user_id'] = user['id']
        
        return redirect(url_for('dashboard'))
    
    # GET request - show login form
    return render_template_string('''
    <html>
    <head>
        <title>Student Login - Vibes University</title>
        <style>
            body { font-family: Arial, sans-serif; background: #111; color: #fff; margin: 0; padding: 20px; }
            .login-container { max-width: 400px; margin: 100px auto; background: #222; padding: 40px; border-radius: 15px; }
            .header { text-align: center; margin-bottom: 30px; }
            .header h1 { color: #ff6b35; margin: 0; }
            .form-group { margin-bottom: 20px; }
            .form-group label { display: block; margin-bottom: 8px; color: #ccc; }
            .form-group input { width: 100%; padding: 12px; border-radius: 8px; border: none; background: #333; color: #fff; box-sizing: border-box; }
            .login-btn { width: 100%; background: #ff6b35; color: #fff; padding: 15px; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; }
            .login-btn:hover { background: #ff8c42; }
            .links { text-align: center; margin-top: 20px; }
            .links a { color: #ff6b35; text-decoration: none; margin: 0 10px; }
        </style>
    </head>
    <body>
        <div class="login-container">
            <div class="header">
                <h1>🎓 Student Login</h1>
                <p>Welcome back to Vibes University</p>
            </div>
            
            <form method="post">
                <div class="form-group">
                    <label>Email Address:</label>
                    <input type="email" name="email" required>
                </div>
                <div class="form-group">
                    <label>Password:</label>
                    <input type="password" name="password" required>
                </div>
                <button type="submit" class="login-btn">Login to My Courses</button>
            </form>
            
            <div class="links">
                <a href="/pay">New Student? Enroll Here</a>
                <a href="/">Back to Home</a>
            </div>
        </div>
    </body>
    </html>
    ''')

@app.route('/admin/announcements', methods=['GET', 'POST'])
def admin_announcements():
    """Admin announcements page for broadcasting messages to students"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    message = ''
    conn = get_db_connection()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create':
            title = request.form.get('title')
            message_text = request.form.get('message')
            priority = request.form.get('priority', 'normal')
            target_audience = request.form.get('target_audience', 'all')
            expires_at = request.form.get('expires_at')
            
            if not title or not message_text:
                message = 'Title and message are required.'
            else:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO announcements (title, message, priority, target_audience, expires_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (title, message_text, priority, target_audience, expires_at))
                conn.commit()
                message = 'Announcement created successfully!'
        
        elif action == 'delete':
            announcement_id = request.form.get('announcement_id')
            if announcement_id:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM announcements WHERE id = ?', (announcement_id,))
                conn.commit()
                message = 'Announcement deleted successfully!'
        
        elif action == 'toggle':
            announcement_id = request.form.get('announcement_id')
            if announcement_id:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE announcements 
                    SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END 
                    WHERE id = ?
                ''', (announcement_id,))
                conn.commit()
                message = 'Announcement status updated!'
    
    # Get all announcements
    announcements = conn.execute('''
        SELECT * FROM announcements 
        ORDER BY created_at DESC
    ''').fetchall()
    
    # Get student count for audience targeting
    total_students = conn.execute('''
        SELECT COUNT(DISTINCT user_id) as count 
        FROM enrollments 
        WHERE payment_status = 'completed'
    ''').fetchone()['count']
    
    conn.close()
    
    return render_template_string('''
    <html>
    <head>
        <title>Admin Announcements - Vibes University</title>
        <style>
            body { font-family: Arial, sans-serif; background: #111; color: #fff; margin: 0; padding: 20px; }
            .header { background: #222; padding: 20px; border-radius: 10px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: center; }
            .header h1 { color: #ff6b35; margin: 0; }
            .back-btn { background: #333; color: #fff; padding: 10px 20px; border: none; border-radius: 8px; text-decoration: none; font-weight: bold; }
            .section { background: #222; padding: 20px; border-radius: 10px; margin-bottom: 30px; }
            .section h3 { color: #ff6b35; margin-top: 0; }
            .create-form { background: #333; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
            .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
            .form-group { margin-bottom: 15px; }
            .form-group label { display: block; margin-bottom: 5px; color: #ccc; }
            .form-group input, .form-group select, .form-group textarea { 
                width: 100%; padding: 10px; border-radius: 8px; border: none; background: #444; color: #fff; 
            }
            .form-group textarea { height: 120px; resize: vertical; }
            .create-btn { background: #4CAF50; color: #fff; padding: 12px 30px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; }
            .announcements-list { margin-top: 20px; }
            .announcement-card { 
                background: #333; padding: 20px; border-radius: 8px; margin-bottom: 15px; 
                border-left: 4px solid #ff6b35;
            }
            .announcement-header { 
                display: flex; justify-content: space-between; align-items: center; 
                margin-bottom: 10px;
            }
            .announcement-title { font-size: 18px; font-weight: bold; color: #ff6b35; }
            .announcement-meta { 
                display: flex; gap: 15px; font-size: 12px; color: #ccc; 
                margin-bottom: 10px;
            }
            .announcement-message { 
                background: #444; padding: 15px; border-radius: 5px; 
                margin-bottom: 15px; line-height: 1.5;
            }
            .announcement-actions { 
                display: flex; gap: 10px; 
            }
            .action-btn { 
                padding: 5px 10px; border: none; border-radius: 4px; text-decoration: none; 
                font-size: 12px; cursor: pointer;
            }
            .toggle-btn { background: #2196F3; color: #fff; }
            .delete-btn { background: #f44336; color: #fff; }
            .priority-high { border-left-color: #f44336; }
            .priority-normal { border-left-color: #ff6b35; }
            .priority-low { border-left-color: #4CAF50; }
            .status-active { color: #4CAF50; }
            .status-inactive { color: #f44336; }
            .success-msg { background: #4CAF50; color: #fff; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
            .stats-card { 
                background: #333; padding: 15px; border-radius: 8px; text-align: center; 
                margin-bottom: 20px;
            }
            .stats-number { font-size: 2rem; font-weight: bold; color: #ff6b35; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📢 Admin Announcements</h1>
            <a href="{{url_for('admin_dashboard')}}" class="back-btn">← Back to Dashboard</a>
        </div>
        
        {% if message %}<div class="success-msg">{{message}}</div>{% endif %}
        
        <div class="stats-card">
            <div class="stats-number">{{total_students}}</div>
            <div>Total Active Students</div>
        </div>
        
        <div class="section">
            <h3>📝 Create New Announcement</h3>
            <form method="post" class="create-form">
                <input type="hidden" name="action" value="create">
                <div class="form-grid">
                    <div class="form-group">
                        <label>Title:</label>
                        <input type="text" name="title" placeholder="Enter announcement title" required>
                    </div>
                    <div class="form-group">
                        <label>Priority:</label>
                        <select name="priority">
                            <option value="low">Low</option>
                            <option value="normal" selected>Normal</option>
                            <option value="high">High</option>
                        </select>
                    </div>
                </div>
                <div class="form-group">
                    <label>Message:</label>
                    <textarea name="message" placeholder="Enter your announcement message here..." required></textarea>
                </div>
                <div class="form-grid">
                    <div class="form-group">
                        <label>Target Audience:</label>
                        <select name="target_audience">
                            <option value="all">All Students</option>
                            <option value="course">Course Access Students</option>
                            <option value="online">Online Mentorship Students</option>
                            <option value="vip">VIP Physical Class Students</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Expires At (Optional):</label>
                        <input type="datetime-local" name="expires_at">
                    </div>
                </div>
                <button type="submit" class="create-btn">📢 Broadcast Announcement</button>
            </form>
        </div>
        
        <div class="section">
            <h3>📋 All Announcements</h3>
            <div class="announcements-list">
                {% for announcement in announcements %}
                <div class="announcement-card priority-{{announcement['priority']}}">
                    <div class="announcement-header">
                        <div class="announcement-title">{{announcement['title']}}</div>
                        <div class="announcement-actions">
                            <form method="post" style="display: inline;">
                                <input type="hidden" name="action" value="toggle">
                                <input type="hidden" name="announcement_id" value="{{announcement['id']}}">
                                <button type="submit" class="action-btn toggle-btn">
                                    {% if announcement['is_active'] %}🟢 Active{% else %}🔴 Inactive{% endif %}
                                </button>
                            </form>
                            <form method="post" style="display: inline;" onsubmit="return confirm('Are you sure you want to delete this announcement?')">
                                <input type="hidden" name="action" value="delete">
                                <input type="hidden" name="announcement_id" value="{{announcement['id']}}">
                                <button type="submit" class="action-btn delete-btn">🗑️ Delete</button>
                            </form>
                        </div>
                    </div>
                    <div class="announcement-meta">
                        <span>📅 {{announcement['created_at']}}</span>
                        <span>🎯 {{announcement['target_audience']|title}}</span>
                        <span>⚡ {{announcement['priority']|title}}</span>
                        {% if announcement['expires_at'] %}
                        <span>⏰ Expires: {{announcement['expires_at']}}</span>
                        {% endif %}
                    </div>
                    <div class="announcement-message">{{announcement['message']}}</div>
                </div>
                {% else %}
                <div style="text-align: center; color: #ccc; padding: 40px;">
                    <h3>No announcements yet</h3>
                    <p>Create your first announcement to broadcast to students!</p>
                </div>
                {% endfor %}
            </div>
        </div>
    </body>
    </html>
    ''')

@app.route('/api/announcements', methods=['GET'])
def get_announcements():
    """Get active announcements for students"""
    try:
        conn = get_db_connection()
        
        # Get active announcements that haven't expired
        announcements = conn.execute('''
            SELECT * FROM announcements 
            WHERE is_active = 1 
            AND (expires_at IS NULL OR expires_at > datetime('now'))
            ORDER BY priority DESC, created_at DESC
        ''').fetchall()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'announcements': [dict(announcement) for announcement in announcements]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/courses', methods=['GET', 'POST'])
def admin_courses():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    conn = get_db_connection()
    message = ''
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        if name:
            try:
                conn.execute('INSERT INTO courses (name, description) VALUES (?, ?)', (name, description))
                conn.commit()
                message = 'Course added!'
            except sqlite3.IntegrityError:
                message = 'Course already exists!'
        elif request.form.get('delete_id'):
            delete_id = request.form.get('delete_id')
            conn.execute('DELETE FROM courses WHERE id = ?', (delete_id,))
            conn.commit()
            message = 'Course deleted.'
    courses = conn.execute('SELECT * FROM courses ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template_string("""
    <html><head><title>Manage Courses</title></head><body style='background:#111;color:#fff;font-family:Arial,sans-serif;padding:40px;'>
    <h2>Manage Courses</h2>
    <a href='{{url_for("admin_dashboard")}}' style='color:#ff6b35;'>← Back to Dashboard</a>
    <form method='post' style='margin-top:20px;'>
        <input name='name' placeholder='Course Name' required>
        <input name='description' placeholder='Description'>
        <button type='submit'>Add Course</button>
    </form>
    {% if message %}<div style='color:#4CAF50;'>{{message}}</div>{% endif %}
    <ul>
    {% for c in courses %}
        <li><b>{{c['name']}}</b> - {{c['description']}}
            <form method='post' style='display:inline;'>
                <input type='hidden' name='delete_id' value='{{c['id']}}'>
                <button type='submit' style='color:#fff;background:#f44336;border:none;padding:2px 8px;border-radius:4px;cursor:pointer;'>Delete</button>
            </form>
        </li>
    {% endfor %}
    </ul>
    </body></html>
    """, courses=courses, message=message)

# 1. Add a new route for /admin/courses/<int:course_id> to manage modules and lessons for a course
@app.route('/admin/courses/<int:course_id>', methods=['GET', 'POST'])
def admin_course_detail(course_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    conn = get_db_connection()
    course = conn.execute('SELECT * FROM courses WHERE id = ?', (course_id,)).fetchone()
    if not course:
        conn.close()
        return 'Course not found', 404
    message = ''
    # Add module or lesson
    if request.method == 'POST':
        if request.form.get('action') == 'add_lesson':
            module = request.form.get('module')
            lesson = request.form.get('lesson')
            description = request.form.get('description')
            file = request.files.get('file')
            if not (module and lesson and file and allowed_file(file.filename)):
                message = 'All fields and a valid file are required.'
            else:
                filename = secure_filename(file.filename)
                course_dir = os.path.join(app.config['UPLOAD_FOLDER'], course['name'], module)
                os.makedirs(course_dir, exist_ok=True)
                filepath = os.path.join(course_dir, filename)
                file.save(filepath)
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO lessons (course, module, lesson, description, file_path)
                    VALUES (?, ?, ?, ?, ?)
                ''', (course['name'], module, lesson, description, filepath))
                conn.commit()
                message = 'Lesson added!'
    # Get all modules and lessons for this course
    lessons = conn.execute('SELECT * FROM lessons WHERE course = ? ORDER BY module, order_index, uploaded_at', (course['name'],)).fetchall()
    modules = {}
    for lesson in lessons:
        module_name = lesson['module']
        if module_name not in modules:
            modules[module_name] = []
        modules[module_name].append(lesson)
    conn.close()
    return render_template_string("""
    <html><head><title>Manage {{course['name']}}</title></head><body style='background:#111;color:#fff;font-family:Arial,sans-serif;padding:40px;'>
    <h2>Manage Course: {{course['name']}}</h2>
    <a href='{{url_for("admin_courses")}}' style='color:#ff6b35;'>← Back to Courses</a>
    <form method='post' enctype='multipart/form-data' style='margin-top:20px;'>
        <input type='hidden' name='action' value='add_lesson'>
        <select name='module' required>
            <option value=''>Select Module</option>
            {% for i in range(1, 16) %}
                <option value='Module {{i}}'>Module {{i}}</option>
            {% endfor %}
        </select>
        <input name='lesson' placeholder='Lesson Title' required>
        <input name='description' placeholder='Description'>
        <input type='file' name='file' required>
        <button type='submit'>Add Lesson</button>
    </form>
    {% if message %}<div style='color:#4CAF50;'>{{message}}</div>{% endif %}
    <h3>Modules & Lessons</h3>
    {% for module, lessons in modules.items() %}
        <h4 style='color:#ff6b35;'>{{module}}</h4>
        <ul>
        {% for lesson in lessons %}
            <li><b>{{lesson['lesson']}}</b> - {{lesson['description']}} <span style='color:#888;'>({{(lesson['file_path'] or '').split('/')[-1]}})</span></li>
        {% endfor %}
        </ul>
    {% endfor %}
    </body></html>
    """, course=course, modules=modules, message=message)

# 2. In /admin/courses, add a link to each course's detail page:
# <a href='{{url_for("admin_course_detail", course_id=c["id"])}}'>Manage</a>

# 3. Remove all course dropdowns from other admin forms. All lesson/module management is now done from the course's management page.

if __name__ == '__main__':
    # Initialize database
    init_db()
    
    # Run the application
    app.run(host='0.0.0.0', port=5000, debug=True)

