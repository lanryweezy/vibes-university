from flask import Blueprint, render_template, render_template_string, redirect, url_for, session, request, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import secrets

# Import utilities
from utils.db_utils import get_db_connection, return_db_connection
from utils.logging_utils import app_logger, security_logger, log_info, log_error, log_warning
from utils.security_utils import validate_email, validate_phone, sanitize_input, get_env_variable
from utils.security_middleware import generate_csrf_token, validate_csrf_token, csrf_protect
from utils.auth_utils import require_teacher_auth

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
    <label for="email">Email</label><input type="email" name="email" id="email" required autocomplete="email">
    <label for="password">Password</label><input type="password" name="password" id="password" required autocomplete="current-password">
    <button class="btn" type="submit">Login as Teacher</button></form>
    {% if message %}<div class="msg {% if 'successful' in message %}success{% else %}error{% endif %}">{{message}}</div>{% endif %}
    <div style="margin-top:20px;text-align:center;">
    <p>Teacher registration is managed by administrators.<br>Contact admin team to become a teacher.</p>
    <p><a href="/" style="color:#ff6b35;">← Back to Home</a></p>
    </div></div></body></html>
    ''', message=message, csrf_token=csrf_token)

@teacher_auth_bp.route('/dashboard')
@require_teacher_auth
def teacher_dashboard():
    """Teacher dashboard."""
    teacher_name = session.get('teacher_name', 'Teacher')
    teacher_id = session.get('teacher_id')
    
    conn = None
    try:
        conn = get_db_connection()
        # Get courses for this teacher
        courses = conn.execute("SELECT id, name FROM courses WHERE teacher_id = ?", (teacher_id,)).fetchall()
        course_ids = [c['id'] for c in courses]

        # Stats
        course_count = len(courses)
        student_count = 0
        total_earnings = 0

        if course_ids:
            # Simple simulation of student count and earnings based on enrollments
            # In a real app, you'd match course names to course_type or use a mapping table
            placeholders = ','.join(['?'] * len(courses))
            course_names = [c['name'] for c in courses]

            # ⚡ Bolt Optimization: Use DB aggregation instead of fetching all rows into memory
            stats = conn.execute(f"SELECT COUNT(*) as count, SUM(price) as total_earnings FROM enrollments WHERE course_type IN ({placeholders}) AND payment_status = 'completed'", course_names).fetchone()
            student_count = stats['count'] if stats and stats['count'] else 0
            total_earnings = stats['total_earnings'] if stats and stats['total_earnings'] else 0

        return render_template('teacher_dashboard.html',
                               teacher_name=teacher_name,
                               active_courses=course_count,
                               total_students=student_count,
                               total_earnings=total_earnings)
    except Exception as e:
        log_error(app_logger, "Dashboard loading error", error=str(e))
        return render_template('teacher_dashboard.html', teacher_name=teacher_name, active_courses=0, total_students=0, total_earnings=0)
    finally:
        if conn:
            return_db_connection(conn)

@teacher_auth_bp.route('/earnings')
@require_teacher_auth
def view_earnings():
    """Teacher earnings page."""
    teacher_id = session.get('teacher_id')
    conn = None
    try:
        conn = get_db_connection()
        courses = conn.execute("SELECT name FROM courses WHERE teacher_id = ?", (teacher_id,)).fetchall()
        course_names = [c['name'] for c in courses]

        earnings_data = []
        total_earnings = 0
        if course_names:
            placeholders = ','.join(['?'] * len(course_names))
            earnings_data = conn.execute(f"""
                SELECT course_type, COUNT(*) as enrollment_count, SUM(price) as revenue
                FROM enrollments
                WHERE course_type IN ({placeholders}) AND payment_status = 'completed'
                GROUP BY course_type
            """, course_names).fetchall()
            total_earnings = sum([row['revenue'] for row in earnings_data])

        return render_template_string('''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>My Earnings | Vibes U</title>
            <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
            <style>
                :root { --primary: #4CAF50; --bg-dark: #0f172a; --card-bg: #1e293b; --text-main: #f1f5f9; --text-muted: #94a3b8; }
                body { font-family: 'Inter', sans-serif; background: var(--bg-dark); color: var(--text-main); margin: 0; display: flex; }
                .sidebar { width: 280px; background: #020617; border-right: 1px solid rgba(255,255,255,0.05); height: 100vh; position: fixed; padding: 32px; }
                .logo { font-size: 1.25rem; font-weight: 800; color: var(--primary); text-transform: uppercase; letter-spacing: 2px; margin-bottom: 48px; }
                .nav-link { display: flex; align-items: center; gap: 12px; padding: 12px 16px; color: var(--text-muted); text-decoration: none; border-radius: 12px; transition: 0.3s; margin-bottom: 8px; }
                .nav-link:hover, .nav-link.active { background: rgba(76, 175, 80, 0.1); color: var(--primary); }
                .main-content { margin-left: 280px; padding: 48px; flex-grow: 1; }
                h1 { font-size: 2.5rem; margin-bottom: 8px; }
                .earnings-card { background: linear-gradient(135deg, var(--primary) 0%, #2e7d32 100%); padding: 40px; border-radius: 24px; margin-bottom: 48px; }
                .total-label { text-transform: uppercase; font-size: 0.85rem; font-weight: 700; letter-spacing: 1px; opacity: 0.9; }
                .total-value { font-size: 3.5rem; font-weight: 800; margin-top: 8px; }
                .table-container { background: var(--card-bg); border-radius: 24px; overflow: hidden; border: 1px solid rgba(255,255,255,0.05); }
                table { width: 100%; border-collapse: collapse; }
                th { text-align: left; padding: 20px 32px; background: rgba(255,255,255,0.02); color: var(--text-muted); font-size: 0.85rem; text-transform: uppercase; }
                td { padding: 20px 32px; border-bottom: 1px solid rgba(255,255,255,0.05); }
            </style>
        </head>
        <body>
            <aside class="sidebar">
                <div class="logo">Vibes U</div>
                <a href="{{ url_for('teacher_auth_bp.teacher_dashboard') }}" class="nav-link"><i class="fas fa-chart-line"></i> Overview</a>
                <a href="{{ url_for('teacher_auth_bp.manage_students') }}" class="nav-link"><i class="fas fa-users"></i> Students</a>
                <a href="{{ url_for('teacher_auth_bp.view_earnings') }}" class="nav-link active"><i class="fas fa-wallet"></i> Earnings</a>
                <a href="{{ url_for('teacher_courses_bp.teacher_course_studio_page') }}" class="nav-link"><i class="fas fa-rocket"></i> Course Studio</a>
                <a href="{{ url_for('blog_bp.list_blogs') }}" class="nav-link"><i class="fas fa-rss"></i> AI Blog</a>
                <a href="{{ url_for('teacher_auth_bp.teacher_logout') }}" class="nav-link" style="margin-top:auto; color:#ef4444;"><i class="fas fa-sign-out-alt"></i> Logout</a>
            </aside>
            <main class="main-content">
                <h1>Financial Performance</h1>
                <div class="earnings-card">
                    <div class="total-label">Total Lifetime Earnings</div>
                    <div class="total-value">₦{{ "{:,}".format(total_earnings) }}</div>
                </div>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr><th>Course Name</th><th>Total Enrolled</th><th>Revenue Generated</th></tr>
                        </thead>
                        <tbody>
                            {% for item in earnings_data %}
                            <tr>
                                <td style="font-weight:600;">{{ item.course_type }}</td>
                                <td>{{ item.enrollment_count }}</td>
                                <td style="color:var(--primary); font-weight:700;">₦{{ "{:,}".format(item.revenue) }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </main>
        </body>
        </html>
        ''', earnings_data=earnings_data, total_earnings=total_earnings)
    except Exception as e:
        log_error(app_logger, "Earnings page error", error=str(e))
        return "Error loading earnings", 500
    finally:
        if conn:
            return_db_connection(conn)

@teacher_auth_bp.route('/students')
@require_teacher_auth
def manage_students():
    """Teacher student management page."""
    teacher_id = session.get('teacher_id')
    conn = None
    try:
        conn = get_db_connection()
        # Find courses taught by this teacher
        courses = conn.execute("SELECT name FROM courses WHERE teacher_id = ?", (teacher_id,)).fetchall()
        course_names = [c['name'] for c in courses]

        students = []
        if course_names:
            placeholders = ','.join(['?'] * len(course_names))
            students = conn.execute(f"""
                SELECT u.full_name, u.email, e.course_type, e.enrolled_at
                FROM users u
                JOIN enrollments e ON u.id = e.user_id
                WHERE e.course_type IN ({placeholders}) AND e.payment_status = 'completed'
                ORDER BY e.enrolled_at DESC
            """, course_names).fetchall()

        return render_template_string('''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Manage Students | Vibes U</title>
            <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
            <style>
                :root { --primary: #4CAF50; --bg-dark: #0f172a; --card-bg: #1e293b; --text-main: #f1f5f9; --text-muted: #94a3b8; }
                body { font-family: 'Inter', sans-serif; background: var(--bg-dark); color: var(--text-main); margin: 0; display: flex; }
                .sidebar { width: 280px; background: #020617; border-right: 1px solid rgba(255,255,255,0.05); height: 100vh; position: fixed; padding: 32px; }
                .logo { font-size: 1.25rem; font-weight: 800; color: var(--primary); text-transform: uppercase; letter-spacing: 2px; margin-bottom: 48px; }
                .nav-link { display: flex; align-items: center; gap: 12px; padding: 12px 16px; color: var(--text-muted); text-decoration: none; border-radius: 12px; transition: 0.3s; margin-bottom: 8px; }
                .nav-link:hover, .nav-link.active { background: rgba(76, 175, 80, 0.1); color: var(--primary); }
                .main-content { margin-left: 280px; padding: 48px; flex-grow: 1; }
                h1 { font-size: 2.5rem; margin-bottom: 32px; }
                .table-container { background: var(--card-bg); border-radius: 24px; overflow: hidden; border: 1px solid rgba(255,255,255,0.05); }
                table { width: 100%; border-collapse: collapse; }
                th { text-align: left; padding: 20px 32px; background: rgba(255,255,255,0.02); color: var(--text-muted); font-size: 0.85rem; text-transform: uppercase; letter-spacing: 1px; }
                td { padding: 20px 32px; border-bottom: 1px solid rgba(255,255,255,0.05); }
                tr:last-child td { border-bottom: none; }
                .badge { padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; font-weight: 700; background: rgba(76, 175, 80, 0.1); color: var(--primary); }
            </style>
        </head>
        <body>
            <aside class="sidebar">
                <div class="logo">Vibes U</div>
                <a href="{{ url_for('teacher_auth_bp.teacher_dashboard') }}" class="nav-link"><i class="fas fa-chart-line"></i> Overview</a>
                <a href="{{ url_for('teacher_auth_bp.manage_students') }}" class="nav-link active"><i class="fas fa-users"></i> Students</a>
                <a href="{{ url_for('teacher_auth_bp.view_earnings') }}" class="nav-link"><i class="fas fa-wallet"></i> Earnings</a>
                <a href="{{ url_for('teacher_courses_bp.teacher_course_studio_page') }}" class="nav-link"><i class="fas fa-rocket"></i> Course Studio</a>
                <a href="{{ url_for('blog_bp.list_blogs') }}" class="nav-link"><i class="fas fa-rss"></i> AI Blog</a>
                <a href="{{ url_for('teacher_auth_bp.teacher_logout') }}" class="nav-link" style="margin-top:auto; color:#ef4444;"><i class="fas fa-sign-out-alt"></i> Logout</a>
            </aside>
            <main class="main-content">
                <h1>Student Management</h1>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr><th>Student Name</th><th>Email</th><th>Course</th><th>Enrolled Date</th></tr>
                        </thead>
                        <tbody>
                            {% for student in students %}
                            <tr>
                                <td style="font-weight:600;">{{ student.full_name }}</td>
                                <td style="color:var(--text-muted);">{{ student.email }}</td>
                                <td><span class="badge">{{ student.course_type }}</span></td>
                                <td style="font-size:0.9rem;">{{ student.enrolled_at.split(' ')[0] }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </main>
        </body>
        </html>
        ''', students=students)
    except Exception as e:
        log_error(app_logger, "Student management error", error=str(e))
        return "Error loading students", 500
    finally:
        if conn:
            return_db_connection(conn)

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