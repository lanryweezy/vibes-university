from flask import Blueprint, render_template_string, redirect, url_for, session, request, jsonify
import json
import os
import secrets
from datetime import datetime

# Import utilities
from utils.db_utils import get_db_connection, return_db_connection
from utils.logging_utils import app_logger, db_logger, log_info, log_error, log_warning
from utils.security_utils import sanitize_input, require_admin_auth
from utils.security_middleware import generate_csrf_token, csrf_protect

admin_page_bp = Blueprint('admin_page_bp', __name__, url_prefix='/admin')

@admin_page_bp.route('/')
@require_admin_auth
def admin_dashboard():
    message = sanitize_input(request.args.get('message', ''))
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

        # Contact Messages
        unread_messages = conn.execute("SELECT * FROM contact_messages WHERE status = 'unread' ORDER BY created_at DESC LIMIT 10").fetchall()
        unread_count_row = conn.execute("SELECT COUNT(*) as count FROM contact_messages WHERE status = 'unread'").fetchone()
        unread_count = unread_count_row['count'] if unread_count_row else 0

        return render_template_string('''
        <html><head><title>Admin Dashboard - Vibes University</title>
        <style>
            body{font-family:'Inter', sans-serif;background:#0f172a;color:#f8fafc;margin:0;padding:20px;}
            .header{background:#1e293b;padding:20px;border-radius:15px;margin-bottom:30px;display:flex;justify-content:space-between;align-items:center;border:1px solid rgba(255,255,255,0.05);}
            .header h1{color:#ff6b35;margin:0;font-size:1.5rem;}
            .logout-btn{background:#ef4444;color:#fff;padding:10px 20px;border:none;border-radius:8px;text-decoration:none;font-weight:bold;font-size:0.9rem;}
            .stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:20px;margin-bottom:30px;}
            .stat-card{background:#1e293b;padding:20px;border-radius:15px;text-align:center;border-left:4px solid #ff6b35;border-top:1px solid rgba(255,255,255,0.05);}
            .stat-number{font-size:2rem;font-weight:bold;color:#ff6b35;}
            .stat-label{color:#94a3b8;margin-top:5px;text-transform:uppercase;font-size:0.75rem;letter-spacing:1px;font-weight:600;}
            .section{background:#1e293b;padding:24px;border-radius:15px;margin-bottom:30px;border:1px solid rgba(255,255,255,0.05);}
            .section h3{color:#ff6b35;margin-top:0;margin-bottom:20px;font-size:1.25rem;display:flex;align-items:center;gap:10px;}
            .table{width:100%;border-collapse:collapse;}
            .table th,.table td{padding:12px;text-align:left;border-bottom:1px solid rgba(255,255,255,0.05);}
            .table th{color:#94a3b8;font-size:0.85rem;text-transform:uppercase;letter-spacing:1px;}
            .table tr:hover{background:rgba(255,255,255,0.02);}
            .msg-badge{background:#ef4444;color:white;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:800;}
            .nav-tabs{display:flex;gap:10px;margin-bottom:20px;}
            .nav-tabs a{background:#334155;color:#fff;padding:8px 16px;border-radius:8px;text-decoration:none;font-size:0.85rem;transition:0.3s;}
            .nav-tabs a:hover{background:#ff6b35;}
        </style>
        </head>
        <body>
            <div class="header">
                <h1>🎓 Vibes University Admin</h1>
                <a href="{{url_for('admin_page_bp.admin_logout')}}" class="logout-btn">Logout</a>
            </div>

            <div class="nav-tabs">
                <a href="{{url_for('admin_page_bp.admin_users')}}">👥 Users</a>
                <a href="{{url_for('admin_page_bp.admin_analytics')}}">📊 Analytics</a>
                <a href="{{url_for('admin_page_bp.admin_settings')}}">⚙️ Settings</a>
                <a href="{{url_for('admin_page_bp.admin_announcements')}}">📢 Announcements</a>
                <a href="/teacher/course-studio">🚀 Course Studio</a>
            </div>

            <div class="stats-grid">
                <div class="stat-card"><div class="stat-number">{{total_users}}</div><div class="stat-label">Total Users</div></div>
                <div class="stat-card"><div class="stat-number">{{total_enrollments}}</div><div class="stat-label">Enrollments</div></div>
                <div class="stat-card"><div class="stat-number">{{unread_count}}</div><div class="stat-label">New Messages</div></div>
                <div class="stat-card"><div class="stat-number">₦{{ "{:,}".format(total_revenue) }}</div><div class="stat-label">Total Revenue</div></div>
                <div class="stat-card"><div class="stat-number">{{total_lessons_stat}}</div><div class="stat-label">Total Lessons</div></div>
            </div>

            <div class="section">
                <h3>📩 Unread Contact Messages {% if unread_count > 0 %}<span class="msg-badge">NEW</span>{% endif %}</h3>
                {% if unread_messages %}
                <table class="table">
                    <thead><tr><th>Name</th><th>Email</th><th>Message Snippet</th><th>Date</th></tr></thead>
                    <tbody>
                        {% for msg in unread_messages %}
                        <tr>
                            <td style="font-weight:600;">{{msg.name}}</td>
                            <td style="color:#ff6b35;">{{msg.email}}</td>
                            <td style="color:#94a3b8;">{{msg.message[:80]}}...</td>
                            <td style="font-size:0.85rem;">{{msg.created_at.split('.')[0]}}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                {% else %}
                <p style="color:#94a3b8;">No new messages.</p>
                {% endif %}
            </div>

            <div class="section">
                <h3>📋 Recent Enrollments</h3>
                <table class="table">
                    <thead><tr><th>Student</th><th>Course</th><th>Amount</th><th>Status</th><th>Date</th></tr></thead>
                    <tbody>
                        {% for enrollment in recent_enrollments %}
                        <tr>
                            <td>{{enrollment['full_name']}}<br><small style="color:#94a3b8;">{{enrollment['email']}}</small></td>
                            <td>{{enrollment['course_type']|title}}</td>
                            <td style="font-weight:600;">₦{{ "{:,}".format(enrollment['price']) }}</td>
                            <td><span style="color:{{'#10b981' if enrollment['payment_status']=='completed' else '#f59e0b'}};">{{enrollment['payment_status']|title}}</span></td>
                            <td style="font-size:0.85rem;">{{enrollment['enrolled_at'].split(' ')[0]}}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </body></html>
        ''', message=message, total_users=total_users, total_enrollments=total_enrollments, unread_count=unread_count, total_revenue=total_revenue, total_lessons_stat=total_lessons_stat, recent_enrollments=recent_enrollments, unread_messages=unread_messages)
    except Exception as e:
        log_error(app_logger, "Admin dashboard error", error=str(e))
        return "Error loading dashboard", 500
    finally:
        if conn:
            return_db_connection(conn)

@admin_page_bp.route('/login', methods=['GET', 'POST'])
@csrf_protect
def admin_login():
    csrf_token = generate_csrf_token()
    message = ''
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'vibesadmin123')
    if request.method == 'POST':
        password = request.form.get('password')
        if password and ADMIN_PASSWORD and secrets.compare_digest(password, ADMIN_PASSWORD):
            session['admin_logged_in'] = True
            log_info(app_logger, "Admin logged in successfully")
            return redirect(url_for('admin_page_bp.admin_dashboard'))
        else:
            message = 'Invalid password.'
            log_warning(app_logger, "Admin login failed")
    return render_template_string('''
    <html><head><title>Admin Login</title>
    <style>
        body{background:#0f172a;color:#fff;font-family:'Inter', sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;}
        .card{background:#1e293b;padding:40px;border-radius:24px;box-shadow:0 25px 50px -12px rgba(0,0,0,0.5);width:350px;border:1px solid rgba(255,255,255,0.05);}
        h2{color:#ff6b35;text-align:center;margin-bottom:30px;}
        input{width:100%;padding:14px;border-radius:12px;border:1px solid rgba(255,255,255,0.1);background:#0f172a;color:#fff;box-sizing:border-box;margin-bottom:20px;}
        button{width:100%;padding:14px;border-radius:12px;border:none;background:linear-gradient(45deg,#ff6b35,#ff8c42);color:#fff;font-weight:bold;cursor:pointer;}
    </style>
    </head>
    <body>
        <div class="card">
            <h2>Admin Secure Access</h2>
            <form method="post">
                <input type="hidden" name="csrf_token" value="{{csrf_token}}">
                <input type="password" name="password" placeholder="Admin Password" required>
                <button type="submit">Unlock Dashboard</button>
            </form>
            {% if message %}<div style="color:#ef4444;margin-top:20px;text-align:center;font-size:0.9rem;">{{message}}</div>{% endif %}
        </div>
    </body></html>
    ''', message=message, csrf_token=csrf_token)

@admin_page_bp.route('/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_page_bp.admin_login'))

@admin_page_bp.route('/users')
@require_admin_auth
def admin_users():
    conn = None
    try:
        conn = get_db_connection()
        users = conn.execute("SELECT u.*, COUNT(e.id) as enrollment_count, SUM(CASE WHEN e.payment_status = 'completed' THEN 1 ELSE 0 END) as completed_enrollments, SUM(CASE WHEN e.payment_status = 'completed' THEN e.price ELSE 0 END) as total_spent FROM users u LEFT JOIN enrollments e ON u.id = e.user_id GROUP BY u.id ORDER BY u.created_at DESC").fetchall()
        return render_template_string('''
        <html><head><title>User Management</title><style>body{font-family:Arial,sans-serif;background:#0f172a;color:#fff;margin:0;padding:20px;}.header{background:#1e293b;padding:20px;border-radius:10px;margin-bottom:30px;display:flex;justify-content:space-between;align-items:center;}h1{color:#ff6b35;margin:0;}.back-btn{background:#334155;color:#fff;padding:10px 20px;border:none;border-radius:8px;text-decoration:none;font-weight:bold;}.table{width:100%;border-collapse:collapse;background:#1e293b;border-radius:10px;overflow:hidden;}.table th,.table td{padding:15px;text-align:left;border-bottom:1px solid rgba(255,255,255,0.05);}.table th{background:#0f172a;color:#94a3b8;font-weight:bold;}.table tr:hover{background:rgba(255,255,255,0.02);}.status-active{color:#10b981;}.status-inactive{color:#ef4444;}.user-email{color:#ff6b35;}</style></head>
        <body><div class="header"><h1>👥 User Management</h1><a href="{{url_for('admin_page_bp.admin_dashboard')}}" class="back-btn">← Dashboard</a></div>
        <table class="table"><tr><th>Name</th><th>Email</th><th>Phone</th><th>Enrollments</th><th>Completed</th><th>Total Spent</th><th>Joined</th><th>Status</th></tr>
        {% for user in users %}<tr><td>{{user['full_name']}}</td><td class="user-email">{{user['email']}}</td><td>{{user['phone']}}</td><td>{{user['enrollment_count']}}</td><td>{{user['completed_enrollments']}}</td><td>₦{{ "{:,}".format(user['total_spent'] or 0) }}</td><td>{{user['created_at'].split(' ')[0]}}</td><td class="{{'status-active' if user['is_active'] else 'status-inactive'}}">{{'Active' if user['is_active'] else 'Inactive'}}</td></tr>{% endfor %}
        </table></body></html>
        ''', users=users)
    except Exception as e:
        log_error(app_logger, "Admin users error", error=str(e))
        return "Error", 500
    finally:
        if conn:
            return_db_connection(conn)

@admin_page_bp.route('/analytics')
@require_admin_auth
def admin_analytics():
    conn = None
    try:
        conn = get_db_connection()
        monthly_revenue = conn.execute("SELECT strftime('%Y-%m',enrolled_at) as month, SUM(price) as revenue, COUNT(*) as enrollments FROM enrollments WHERE payment_status='completed' GROUP BY 1 ORDER BY 1 DESC LIMIT 12").fetchall()
        course_performance = conn.execute("SELECT course_type, COUNT(*) as total_enrollments, SUM(CASE WHEN payment_status='completed' THEN 1 ELSE 0 END) as completed_enrollments, SUM(CASE WHEN payment_status='completed' THEN price ELSE 0 END) as revenue, AVG(CASE WHEN payment_status='completed' THEN price ELSE NULL END) as avg_revenue FROM enrollments GROUP BY 1").fetchall()
        lesson_stats = conn.execute("SELECT c.name as course_name, m.name as module_name, l.lesson, COUNT(cp.id) as completions FROM lessons l JOIN modules m ON l.module_id=m.id JOIN courses c ON l.course_id=c.id LEFT JOIN course_progress cp ON l.id=cp.lesson_id AND cp.completed=1 GROUP BY l.id,c.name,m.name,l.lesson ORDER BY completions DESC LIMIT 10").fetchall()

        return render_template_string('''
        <html><head><title>Analytics</title><style>body{font-family:Arial,sans-serif;background:#0f172a;color:#fff;margin:0;padding:20px;}.header{background:#1e293b;padding:20px;border-radius:10px;margin-bottom:30px;display:flex;justify-content:space-between;align-items:center;}h1{color:#ff6b35;margin:0;}.back-btn{background:#334155;color:#fff;padding:10px 20px;border:none;border-radius:8px;text-decoration:none;font-weight:bold;}.section{background:#1e293b;padding:20px;border-radius:10px;margin-bottom:30px;border:1px solid rgba(255,255,255,0.05);}h3{color:#ff6b35;margin-top:0;}.table{width:100%;border-collapse:collapse;margin-top:15px;}.table th,.table td{padding:12px;text-align:left;border-bottom:1px solid rgba(255,255,255,0.05);}.table th{background:#0f172a;color:#94a3b8;}.table tr:hover{background:rgba(255,255,255,0.02);}</style></head>
        <body><div class="header"><h1>📊 Analytics Dashboard</h1><a href="{{url_for('admin_page_bp.admin_dashboard')}}" class="back-btn">← Dashboard</a></div>
        <div class="section"><h3>💰 Monthly Revenue</h3><table class="table"><tr><th>Month</th><th>Revenue</th><th>Enrollments</th></tr>{% for r in monthly_revenue %}<tr><td>{{r.month}}</td><td>₦{{ "{:,}".format(r.revenue or 0) }}</td><td>{{r.enrollments}}</td></tr>{% endfor %}</table></div>
        <div class="section"><h3>🎯 Course Performance</h3><table class="table"><tr><th>Course</th><th>Total</th><th>Completed</th><th>Revenue</th></tr>{% for c_perf in course_performance %}<tr><td>{{c_perf.course_type|title}}</td><td>{{c_perf.total_enrollments}}</td><td>{{c_perf.completed_enrollments}}</td><td>₦{{ "{:,}".format(c_perf.revenue or 0) }}</td></tr>{% endfor %}</table></div>
        </body></html>
        ''', monthly_revenue=monthly_revenue, course_performance=course_performance, lesson_stats=lesson_stats)
    except Exception as e:
        log_error(app_logger, "Admin analytics error", error=str(e))
        return "Error", 500
    finally:
        if conn:
            return_db_connection(conn)

@admin_page_bp.route('/settings', methods=['GET', 'POST'])
@require_admin_auth
@csrf_protect
def admin_settings():
    message = ''
    if request.method == 'POST':
        message = 'Settings update simulated.'

    return render_template_string('''
    <html><head><title>Settings</title><style>body{font-family:Arial,sans-serif;background:#0f172a;color:#fff;margin:0;padding:20px;}.header{background:#1e293b;padding:20px;border-radius:10px;margin-bottom:30px;display:flex;justify-content:space-between;align-items:center;}h1{color:#ff6b35;margin:0;}.back-btn{background:#334155;color:#fff;padding:10px 20px;border:none;border-radius:8px;text-decoration:none;font-weight:bold;}.section{background:#1e293b;padding:20px;border-radius:10px;margin-bottom:30px;border:1px solid rgba(255,255,255,0.05);}h3{color:#ff6b35;margin-top:0;}.form-group{margin-bottom:15px;}.form-group label{display:block;margin-bottom:5px;color:#94a3b8;}.form-group input{width:100%;padding:10px;border-radius:8px;border:1px solid rgba(255,255,255,0.1);background:#0f172a;color:#fff;}.save-btn{background:#10b981;color:#fff;padding:12px 30px;border:none;border-radius:8px;font-weight:bold;cursor:pointer;}</style></head>
    <body><div class="header"><h1>⚙️ System Settings</h1><a href="{{url_for('admin_page_bp.admin_dashboard')}}" class="back-btn">← Dashboard</a></div>
    <div class="section"><h3>🔐 Security Settings</h3><form method="post">
    <input type="hidden" name="csrf_token" value="{{generate_csrf_token()}}">
    <div class="form-group"><label>New Admin Password:</label><input type="password" name="new_password" placeholder="Enter new admin password"></div>
    <button type="submit" class="save-btn">💾 Save Changes</button></form></div>
    </body></html>
    ''', message=message)

@admin_page_bp.route('/announcements', methods=['GET', 'POST'])
@require_admin_auth
@csrf_protect
def admin_announcements():
    message = ''
    conn = None
    try:
        conn = get_db_connection()
        if request.method == 'POST':
            title = sanitize_input(request.form.get('title'))
            msg = sanitize_input(request.form.get('message_content'))
            if title and msg:
                conn.execute("INSERT INTO announcements (title, message) VALUES (?, ?)", (title, msg))
                conn.commit()
                message = "Announcement created."
        
        anns = conn.execute("SELECT * FROM announcements ORDER BY created_at DESC").fetchall()
        return render_template_string('''
        <html><head><title>Announcements</title><style>body{font-family:Arial,sans-serif;background:#0f172a;color:#fff;margin:0;padding:20px;}.header{background:#1e293b;padding:20px;border-radius:10px;margin-bottom:30px;display:flex;justify-content:space-between;align-items:center;}h1{color:#ff6b35;margin:0;}.back-btn{background:#334155;color:#fff;padding:10px 20px;border:none;border-radius:8px;text-decoration:none;font-weight:bold;}.section{background:#1e293b;padding:20px;border-radius:10px;margin-bottom:30px;border:1px solid rgba(255,255,255,0.05);}.form-group{margin-bottom:15px;}.form-group label{display:block;margin-bottom:5px;}.form-group input, .form-group textarea{width:100%;padding:10px;border-radius:8px;border:1px solid rgba(255,255,255,0.1);background:#0f172a;color:#fff;box-sizing:border-box;}.btn{background:#ff6b35;color:#fff;padding:12px 30px;border:none;border-radius:8px;font-weight:bold;cursor:pointer;}</style></head>
        <body><div class="header"><h1>📢 Announcements</h1><a href="{{url_for('admin_page_bp.admin_dashboard')}}" class="back-btn">← Dashboard</a></div>
        <div class="section"><h3>New Announcement</h3><form method="post">
        <input type="hidden" name="csrf_token" value="{{generate_csrf_token()}}">
        <div class="form-group"><label>Title:</label><input type="text" name="title" required></div>
        <div class="form-group"><label>Message:</label><textarea name="message_content" rows="4" required></textarea></div>
        <button type="submit" class="btn">Post Announcement</button></form></div>
        </body></html>
        ''', anns=anns)
    except Exception as e:
        log_error(app_logger, "Admin announcements error", error=str(e))
        return "Error", 500
    finally:
        if conn:
            return_db_connection(conn)
