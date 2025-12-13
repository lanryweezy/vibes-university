from flask import Blueprint, render_template_string, redirect, url_for, session, request, jsonify
import json
import os
from datetime import datetime

# Import database utilities
from utils.db_utils import get_db_connection
# Import security utilities
from utils.security_utils import require_admin_auth, sanitize_input
# Import CSRF protection
from utils.security_middleware import generate_csrf_token, csrf_protect

# Placeholder for db access and other helpers
# from app import get_db_connection, ADMIN_PASSWORD, get_file_icon

admin_page_bp = Blueprint('admin_page_bp', __name__, url_prefix='/admin')  # Optional: common prefix

# Database connection function placeholder
def get_db_connection():
    DATABASE = 'vibes_university.db'
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# Admin password placeholder - should come from environment variables
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'vibesadmin123')

# File icon function
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

def render_markdown_content(md_text):
    try:
        import markdown
        return markdown.markdown(md_text)
    except ImportError:
        return f"<pre>{md_text}</pre>"

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
    finally:
        if conn:
            conn.close()
    
    return render_template_string('''
    <html><head><title>Admin Dashboard - Vibes University</title>
    <style>body{font-family:Arial,sans-serif;background:#111;color:#fff;margin:0;padding:20px;}.header{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;display:flex;justify-content:space-between;align-items:center;}.header h1{color:#ff6b35;margin:0;}.logout-btn{background:#ff6b35;color:#fff;padding:10px 20px;border:none;border-radius:8px;text-decoration:none;font-weight:bold;}.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:20px;margin-bottom:30px;}.stat-card{background:#222;padding:20px;border-radius:10px;text-align:center;border-left:4px solid #ff6b35;}.stat-number{font-size:2rem;font-weight:bold;color:#ff6b35;}.stat-label{color:#ccc;margin-top:5px;}.section{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;}.section h3{color:#ff6b35;margin-top:0;}.table{width:100%;border-collapse:collapse;margin-top:15px;}.table th,.table td{padding:12px;text-align:left;border-bottom:1px solid #444;}.table th{background:#333;color:#ff6b35;}.table tr:hover{background:#333;}.success-msg{background:#4CAF50;color:#fff;padding:15px;border-radius:8px;margin-bottom:20px;}.course-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:15px;}.course-stat{background:#333;padding:15px;border-radius:8px;text-align:center;}</style></head>
    <body><div class="header"><h1>🎓 Vibes University Admin Dashboard</h1>
    <div style="display:flex;gap:10px;"><a href="{{url_for('admin_page_bp.admin_users')}}" style="background:#333;color:#fff;padding:8px 15px;border-radius:5px;text-decoration:none;font-size:14px;">👥 Users</a><a href="{{url_for('admin_page_bp.admin_analytics')}}" style="background:#333;color:#fff;padding:8px 15px;border-radius:5px;text-decoration:none;font-size:14px;">📊 Analytics</a><a href="{{url_for('admin_page_bp.admin_settings')}}" style="background:#333;color:#fff;padding:8px 15px;border-radius:5px;text-decoration:none;font-size:14px;">⚙️ Settings</a><a href="{{url_for('admin_page_bp.admin_announcements')}}" style="background:#ff6b35;color:#fff;padding:8px 15px;border-radius:5px;text-decoration:none;font-size:14px;">📢 Announcements</a><a href="{{url_for('admin_page_bp.admin_course_studio_page')}}" style="background:#4CAF50;color:#fff;padding:8px 15px;border-radius:5px;text-decoration:none;font-size:14px;">🚀 Course Studio</a><a href="/demo-payment" style="background:#4CAF50;color:#fff;padding:8px 15px;border-radius:5px;text-decoration:none;font-size:14px;">🎯 Test Dashboard</a><a href="{{url_for('admin_page_bp.admin_logout')}}" class="logout-btn">Logout</a></div></div>
    {% if message %}<div class="success-msg">{{message}}</div>{% endif %}
    <div class="stats-grid"><div class="stat-card"><div class="stat-number">{{total_users}}</div><div class="stat-label">Total Users</div></div><div class="stat-card"><div class="stat-number">{{total_enrollments}}</div><div class="stat-label">Total Enrollments</div></div><div class="stat-card"><div class="stat-number">{{completed_payments}}</div><div class="stat-label">Completed Payments</div></div><div class="stat-card"><div class="stat-number">₦{{total_revenue}}</div><div class="stat-label">Total Revenue</div></div><div class="stat-card"><div class="stat-number">{{total_lessons_stat}}</div><div class="stat-label">Total Lessons</div></div></div>
    <div class="section"><h3>📊 Course Statistics</h3><div class="course-stats">
    {% for stat in course_stats %}<div class="course-stat"><div style="font-weight:bold;color:#ff6b35;">{{stat['course_type']|title}}</div><div>{{stat['count']}} students</div><div>₦{{stat['revenue']}}</div></div>{% endfor %}
    </div></div><div class="section"><h3>📋 Recent Enrollments</h3><table class="table"><tr><th>Student</th><th>Email</th><th>Course</th><th>Amount</th><th>Status</th><th>Date</th></tr>
    {% for enrollment in recent_enrollments %}<tr><td>{{enrollment['full_name']}}</td><td>{{enrollment['email']}}</td><td>{{enrollment['course_type']|title}}</td><td>₦{{enrollment['price']}}</td><td><span style="color:{{'#4CAF50' if enrollment['payment_status']=='completed' else '#ff9800'}};">{{enrollment['payment_status']|title}}</span></td><td>{{enrollment['enrolled_at']}}</td></tr>{% endfor %}
    </table></div></body></html>
    ''', message=message, total_users=total_users, total_enrollments=total_enrollments, completed_payments=completed_payments, total_revenue=total_revenue, total_lessons_stat=total_lessons_stat, recent_enrollments=recent_enrollments, course_stats=course_stats)

@admin_page_bp.route('/login', methods=['GET', 'POST'])
@csrf_protect
def admin_login():
    csrf_token = generate_csrf_token()
    message = ''
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_page_bp.admin_dashboard'))
        else:
            message = 'Invalid password.'
    return render_template_string('''
    <html><head><title>Admin Login</title></head><body style="background:#111;color:#fff;font-family:Arial,sans-serif;text-align:center;padding:60px;"><h2>Admin Login</h2><form method="post"><input type="hidden" name="csrf_token" value="{{csrf_token}}"><input type="password" name="password" placeholder="Admin Password" required style="padding:10px;border-radius:8px;"><button type="submit" style="padding:10px 20px;border-radius:8px;background:#ff6b35;color:#fff;font-weight:bold;">Login</button></form>{% if message %}<div style="color:#f00;margin-top:20px;">{{message}}</div>{% endif %}</body></html>
    ''', message=message, csrf_token=csrf_token)

@admin_page_bp.route('/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_page_bp.admin_login'))

@admin_page_bp.route('/users')
def admin_users():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_page_bp.admin_login'))
    
    conn = None
    try:
        conn = get_db_connection()
        users = conn.execute("SELECT u.*, COUNT(e.id) as enrollment_count, SUM(CASE WHEN e.payment_status = 'completed' THEN 1 ELSE 0 END) as completed_enrollments, SUM(CASE WHEN e.payment_status = 'completed' THEN e.price ELSE 0 END) as total_spent FROM users u LEFT JOIN enrollments e ON u.id = e.user_id GROUP BY u.id ORDER BY u.created_at DESC").fetchall()
    finally:
        if conn:
            conn.close()
    
    return render_template_string('''
    <html><head><title>User Management</title><style>body{font-family:Arial,sans-serif;background:#111;color:#fff;margin:0;padding:20px;}.header{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;display:flex;justify-content:space-between;align-items:center;}h1{color:#ff6b35;margin:0;}.back-btn{background:#ff6b35;color:#fff;padding:10px 20px;border:none;border-radius:8px;text-decoration:none;font-weight:bold;}.table{width:100%;border-collapse:collapse;background:#222;border-radius:10px;overflow:hidden;}.table th,.table td{padding:15px;text-align:left;border-bottom:1px solid #444;}.table th{background:#333;color:#ff6b35;font-weight:bold;}.table tr:hover{background:#333;}.status-active{color:#4CAF50;}.status-inactive{color:#f44336;}.user-email{color:#ff6b35;}</style></head>
    <body><div class="header"><h1>👥 User Management</h1><a href="{{url_for('admin_page_bp.admin_dashboard')}}" class="back-btn">← Dashboard</a></div>
    <table class="table"><tr><th>Name</th><th>Email</th><th>Phone</th><th>Enrollments</th><th>Completed</th><th>Total Spent</th><th>Joined</th><th>Status</th></tr>
    {% for user in users %}<tr><td>{{user['full_name']}}</td><td class="user-email">{{user['email']}}</td><td>{{user['phone']}}</td><td>{{user['enrollment_count']}}</td><td>{{user['completed_enrollments']}}</td><td>₦{{user['total_spent'] or 0}}</td><td>{{user['created_at']}}</td><td class="{{'status-active' if user['is_active'] else 'status-inactive'}}">{{'Active' if user['is_active'] else 'Inactive'}}</td></tr>{% endfor %}
    </table></body></html>
    ''', users=users)

@admin_page_bp.route('/analytics')
def admin_analytics():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_page_bp.admin_login'))
    
    conn = None
    try:
        conn = get_db_connection()
        monthly_revenue = conn.execute("SELECT strftime('%Y-%m',enrolled_at) as month, SUM(price) as revenue, COUNT(*) as enrollments FROM enrollments WHERE payment_status='completed' GROUP BY 1 ORDER BY 1 DESC LIMIT 12").fetchall()
        course_performance = conn.execute("SELECT course_type, COUNT(*) as total_enrollments, SUM(CASE WHEN payment_status='completed' THEN 1 ELSE 0 END) as completed_enrollments, SUM(CASE WHEN payment_status='completed' THEN price ELSE 0 END) as revenue, AVG(CASE WHEN payment_status='completed' THEN price ELSE NULL END) as avg_revenue FROM enrollments GROUP BY 1").fetchall()
        lesson_stats = conn.execute("SELECT c.name as course_name, m.name as module_name, l.lesson, COUNT(cp.id) as completions FROM lessons l JOIN modules m ON l.module_id=m.id JOIN courses c ON l.course_id=c.id LEFT JOIN course_progress cp ON l.id=cp.lesson_id AND cp.completed=1 GROUP BY l.id,c.name,m.name,l.lesson ORDER BY completions DESC LIMIT 10").fetchall()
    finally:
        if conn:
            conn.close()
    
    return render_template_string('''
    <html><head><title>Analytics</title><style>body{font-family:Arial,sans-serif;background:#111;color:#fff;margin:0;padding:20px;}.header{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;display:flex;justify-content:space-between;align-items:center;}h1{color:#ff6b35;margin:0;}.back-btn{background:#ff6b35;color:#fff;padding:10px 20px;border:none;border-radius:8px;text-decoration:none;font-weight:bold;}.section{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;}h3{color:#ff6b35;margin-top:0;}.table{width:100%;border-collapse:collapse;margin-top:15px;}.table th,.table td{padding:12px;text-align:left;border-bottom:1px solid #444;}.table th{background:#333;color:#ff6b35;}.table tr:hover{background:#333;}</style></head>
    <body><div class="header"><h1>📊 Analytics Dashboard</h1><a href="{{url_for('admin_page_bp.admin_dashboard')}}" class="back-btn">← Dashboard</a></div>
    <div class="section"><h3>💰 Monthly Revenue</h3><table class="table"><tr><th>Month</th><th>Revenue</th><th>Enrollments</th></tr>{% for r in monthly_revenue %}<tr><td>{{r.month}}</td><td>₦{{r.revenue}}</td><td>{{r.enrollments}}</td></tr>{% endfor %}</table></div>
    <div class="section"><h3>🎯 Course Performance</h3><table class="table"><tr><th>Course</th><th>Total</th><th>Completed</th><th>Revenue</th><th>Avg Rev.</th></tr>{% for c_perf in course_performance %}<tr><td>{{c_perf.course_type|title}}</td><td>{{c_perf.total_enrollments}}</td><td>{{c_perf.completed_enrollments}}</td><td>₦{{c_perf.revenue}}</td><td>₦{{c_perf.avg_revenue or 0}}</td></tr>{% endfor %}</table></div>
    <div class="section"><h3>📚 Top Lessons</h3><table class="table"><tr><th>Course</th><th>Module</th><th>Lesson</th><th>Completions</th></tr>{% for l_stat in lesson_stats %}<tr><td>{{l_stat.course_name|title}}</td><td>{{l_stat.module_name}}</td><td>{{l_stat.lesson}}</td><td>{{l_stat.completions}}</td></tr>{% endfor %}</table></div>
    </body></html>
    ''', monthly_revenue=monthly_revenue, course_performance=course_performance, lesson_stats=lesson_stats)

@admin_page_bp.route('/settings', methods=['GET', 'POST'])
@csrf_protect
def admin_settings():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_page_bp.admin_login'))
    
    message = ''
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        if new_password:
            message = 'Admin password update simulated (not persistent for this demo environment).'
        else:
            message = 'No new password provided.'

    return render_template_string('''
    <html><head><title>Settings</title><style>body{font-family:Arial,sans-serif;background:#111;color:#fff;margin:0;padding:20px;}.header{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;display:flex;justify-content:space-between;align-items:center;}h1{color:#ff6b35;margin:0;}.back-btn{background:#ff6b35;color:#fff;padding:10px 20px;border:none;border-radius:8px;text-decoration:none;font-weight:bold;}.section{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;}h3{color:#ff6b35;margin-top:0;}.form-group{margin-bottom:15px;}.form-group label{display:block;margin-bottom:5px;color:#ccc;}.form-group input{width:100%;padding:10px;border-radius:8px;border:none;background:#444;color:#fff;}.save-btn{background:#4CAF50;color:#fff;padding:12px 30px;border:none;border-radius:8px;font-weight:bold;cursor:pointer;}.success-msg{padding:15px;border-radius:8px;margin-bottom:20px; background-color: #333; color: #4CAF50; border: 1px solid #4CAF50;}</style></head>
    <body><div class="header"><h1>⚙️ System Settings</h1><a href="{{url_for('admin_page_bp.admin_dashboard')}}" class="back-btn">← Dashboard</a></div>
    {% if message %}<div class="success-msg">{{message}}</div>{% endif %}
    <div class="section"><h3>🔐 Security Settings</h3><form method="post">
    <div class="form-group"><label>New Admin Password:</label><input type="password" name="new_password" placeholder="Enter new admin password"></div>
    <button type="submit" class="save-btn">💾 Save Changes</button></form></div>
    <div class="section"><h3>🔗 Quick Links</h3><p><a href="{{url_for('admin_page_bp.admin_users')}}" style="color:#ff6b35;">👥 Manage Users</a></p><p><a href="{{url_for('admin_page_bp.admin_analytics')}}" style="color:#ff6b35;">📊 View Analytics</a></p><p><a href="{{url_for('main_bp.demo_payment')}}" style="color:#ff6b35;">🎯 Test Student Dashboard</a></p></div>
    </body></html>
    ''', message=message)

@admin_page_bp.route('/announcements', methods=['GET', 'POST'])
@csrf_protect
def admin_announcements():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_page_bp.admin_login'))
    
    message = ''
    conn = None
    try:
        conn = get_db_connection()  # Open connection early

        if request.method == 'POST':
            title = request.form.get('title')
            msg_content = request.form.get('message_content')
            priority = request.form.get('priority', 'normal')
            target_audience = request.form.get('target_audience', 'all')
            expires_at_str = request.form.get('expires_at')
            is_active = request.form.get('is_active', '1')  # Assuming '1' for active

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
    finally:
        if conn:
            conn.close()  # Close connection after all DB operations for this request

    return render_template_string('''
    <html><head><title>Admin - Announcements</title>
    <style>body{font-family:Arial,sans-serif;background:#111;color:#fff;margin:0;padding:20px;}.header{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;display:flex;justify-content:space-between;align-items:center;}h1{color:#ff6b35;margin:0;}.back-btn{background:#ff6b35;color:#fff;padding:10px 20px;border:none;border-radius:8px;text-decoration:none;font-weight:bold;}.section{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;}h3{color:#ff6b35;margin-top:0;}.form-group{margin-bottom:15px;}.form-group label{display:block;margin-bottom:5px;color:#ccc;}.form-group input, .form-group textarea, .form-group select{width:100%;padding:10px;border-radius:8px;border:none;background:#444;color:#fff;box-sizing: border-box;}.save-btn{background:#4CAF50;color:#fff;padding:12px 30px;border:none;border-radius:8px;font-weight:bold;cursor:pointer;}.success-msg{padding:15px;border-radius:8px;margin-bottom:20px; background-color: #333; color: #4CAF50; border: 1px solid #4CAF50;}.error-msg{padding:15px;border-radius:8px;margin-bottom:20px; background-color: #333; color: #f44336; border: 1px solid #f44336;}.table{width:100%;border-collapse:collapse;margin-top:15px;}.table th,.table td{padding:12px;text-align:left;border-bottom:1px solid #444;}.table th{background:#333;color:#ff6b35;}</style></head>
    <body><div class="header"><h1>📢 Manage Announcements</h1><a href="{{url_for('admin_page_bp.admin_dashboard')}}" class="back-btn">← Dashboard</a></div>
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

@admin_page_bp.route('/preview/<course_type>')
def admin_preview_course(course_type):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_page_bp.admin_login'))
    
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
    finally:
        if conn:
            conn.close()
    
    return render_template_string('''
    <html><head><title>Course Preview - {{course_name|title}}</title>
    <style>body{font-family:Arial,sans-serif;background:#111;color:#fff;margin:0;padding:20px;}.header{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;}.preview-title{color:#ff6b35;font-size:24px;margin-bottom:10px;}.course-info{color:#ccc;margin-bottom:20px;}.modules{display:grid;gap:20px;}.module-card{background:#222;border-radius:10px;padding:20px;border-left:4px solid #ff6b35;}.module-title{color:#ff6b35;font-size:20px;margin-bottom:15px;}.lessons{display:grid;gap:10px;}.lesson-item{background:#333;padding:15px;border-radius:8px;display:flex;justify-content:space-between;align-items:center;}.lesson-info{flex:1;}.lesson-title{color:#fff;font-weight:bold;margin-bottom:5px;}.lesson-desc{color:#ccc;font-size:14px;}.lesson-status a{color:inherit;text-decoration:none;background:#666;color:#ccc;padding:5px 10px;border-radius:15px;font-size:12px;font-weight:bold;margin-left:15px;}.nav-bar{background:#222;padding:15px;border-radius:8px;margin-bottom:20px;}.nav-bar a{color:#ff6b35;text-decoration:none;margin-right:20px;}.preview-notice{background:#333;color:#ff6b35;padding:15px;border-radius:8px;margin-bottom:20px;border:1px solid #ff6b35;}.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:15px;margin-bottom:20px;}.stat-card{background:#333;padding:15px;border-radius:8px;text-align:center;}.stat-number{font-size:1.5rem;font-weight:bold;color:#ff6b35;}</style></head>
    <body><div class="nav-bar"><a href="{{url_for('admin_page_bp.admin_dashboard')}}">← Admin Dashboard</a>
    <a href="{{url_for('admin_page_bp.admin_preview_course',course_type='AI Marketing Mastery')}}">AI Marketing Mastery</a> <a href="{{url_for('admin_page_bp.admin_preview_course',course_type='AI Coding & Development')}}">AI Coding</a></div>
    <div class="preview-notice"><strong>👁️ Admin Preview:</strong> {{course_name|title}}</div>
    <div class="header"><div class="preview-title">{{course_name|title}} Course Preview</div><div class="stats"><div class="stat-card"><div class="stat-number">{{modules_list|length}}</div><div>Modules</div></div><div class="stat-card"><div class="stat-number">{{lessons_list|length}}</div><div>Total Lessons</div></div></div></div>
    <div class="modules">{% for module_item in modules_list %}<div class="module-card"><div class="module-title">{{module_item.name}}</div><div class="lessons">
    {% for lesson_item in lessons_list %}{% if lesson_item.module_id == module_item.id %}<div class="lesson-item"><div class="lesson-info">
    <div class="lesson-title">{{get_file_icon((lesson_item.file_path or '').split('/')[-1])}} {{lesson_item.lesson}}</div>
    {% if lesson_item.description %}<div class="lesson-desc">{{lesson_item.description}}</div>{% endif %}</div>
    <div class="lesson-status"><a href="{{url_for('admin_page_bp.admin_preview_lesson',lesson_id=lesson_item.id)}}">👁️ Preview</a></div></div>{% endif %}{% endfor %}</div></div>{% endfor %}</div>
    {% if not modules_list %}<div style="text-align:center;padding:60px;color:#ccc;"><h3>No modules/lessons for {{course_name|title}} course.</h3><a href="{{url_for('admin_page_bp.admin_dashboard')}}" style="color:#ff6b35;">Go to Admin Dashboard</a></div>{% endif %}</body></html>
    ''', course_name=course_name_for_template, modules_list=modules_list, lessons_list=lessons_list, get_file_icon=get_file_icon)

@admin_page_bp.route('/preview/lesson/<int:lesson_id>')
def admin_preview_lesson(lesson_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_page_bp.admin_login'))
    
    conn = None
    try:
        conn = get_db_connection()
        lesson_data = conn.execute("SELECT l.*, m.name as module_name, c.name as course_name FROM lessons l JOIN modules m ON l.module_id = m.id JOIN courses c ON l.course_id = c.id WHERE l.id = ?", (lesson_id,)).fetchone()
        if not lesson_data:
            return "Lesson not found", 404

        lesson = dict(lesson_data)
        try:
            lesson['element_properties'] = json.loads(lesson_data['element_properties']) if lesson_data['element_properties'] else {}
        except:
            lesson['element_properties'] = {}

        all_lessons_raw = conn.execute("SELECT id,lesson,module_id FROM lessons WHERE course_id=? ORDER BY module_id,order_index,lesson", (lesson['course_id'],)).fetchall()
        all_lessons = [dict(l) for l in all_lessons_raw]
        current_index = next((i for i, l_item in enumerate(all_lessons) if l_item['id'] == lesson_id), None)
        next_l = all_lessons[current_index + 1] if current_index is not None and current_index + 1 < len(all_lessons) else None
        prev_l = all_lessons[current_index - 1] if current_index is not None and current_index > 0 else None
    finally:
        if conn:
            conn.close()

    content_type, props = lesson.get('content_type', 'file'), lesson.get('element_properties', {})
    lesson_render_content = "<p>No content.</p>"
    if content_type in ['text', 'markdown']:
        lesson_render_content = render_markdown_content(props.get('markdown_content', lesson.get('description', '')))
    elif content_type == 'video':
        url, fp = props.get('url'), lesson.get('file_path')
        if url:
            html_content = f"<iframe src='{url.replace('watch?v=', 'embed/')}' width='100%' height='450' frameborder='0' allowfullscreen></iframe>" if 'youtube.com' in url or 'youtu.be' in url else f"<video controls width='100%' src='{url}'></video>"
        elif fp:
            # Construct URL for static file
            static_path = fp.split('static/')[-1] if 'static/' in fp else fp
            html_content = f"<video controls width='100%' src='/static/{static_path}'></video>"
        lesson_render_content = html_content if 'html_content' in locals() else "<p>Video content not available.</p>"
    elif content_type == 'quiz':
        lesson_render_content = f"<h4>{props.get('question', 'N/A')}</h4><ul>{''.join(f'<li>{o}</li>' for o in props.get('options', []))}</ul>"
    elif content_type == 'download' and lesson.get('file_path'):
        # Construct URL for static file
        static_path = lesson['file_path'].split('static/')[-1] if 'static/' in lesson['file_path'] else lesson['file_path']
        lesson_render_content = f"<a href='/static/{static_path}' download class='download-btn'>Download {lesson['file_path'].split('/')[-1]}</a>"
    elif lesson.get('file_path'):
        # Construct URL for static file
        static_path = lesson['file_path'].split('static/')[-1] if 'static/' in lesson['file_path'] else lesson['file_path']
        filename = lesson['file_path'].split('/')[-1]
        if filename.split('.')[-1].lower() in ['jpg', 'png', 'gif', 'svg']:
            html_content = f"<img src='/static/{static_path}' style='max-width:100%;'>"
        else:
            html_content = f"<a href='/static/{static_path}' download class='download-btn'>Download {filename}</a>"
        lesson_render_content = html_content

    return render_template_string('''
    <html><head><title>{{lesson.lesson}} - Preview</title>
    <style>body{font-family:Arial,sans-serif;background:#111;color:#fff;margin:0;padding:20px;}.header{background:#222;padding:20px;border-radius:10px;margin-bottom:20px;}.lesson-title{color:#ff6b35;font-size:22px;}.lesson-meta{color:#ccc;font-size:0.9em;}.content{background:#222;padding:20px;border-radius:10px;}.navigation{display:flex;justify-content:space-between;margin-top:20px;}.nav-btn{background:#333;color:#fff;padding:10px 15px;border-radius:5px;text-decoration:none;}.nav-btn:disabled{background:#555;color:#888;}.back-link{color:#ff6b35;}</style></head>
    <body><a href="{{url_for('admin_page_bp.admin_preview_course', course_type=lesson.course_name)}}" class="back-link">← {{lesson.course_name}}</a>
    <div class="header"><h1 class="lesson-title">{{lesson.lesson}}</h1><p class="lesson-meta">Module: {{lesson.module_name}}</p></div>
    <div class="content">{{lesson_render_content|safe}}</div>
    <div class="navigation">
    {% if prev_l %}<a href="{{url_for('admin_page_bp.admin_preview_lesson',lesson_id=prev_l.id)}}" class="nav-btn">← Prev: {{prev_l.lesson}}</a>{% else %}<button class="nav-btn" disabled>← Prev</button>{% endif %}
    <a href="{{url_for('admin_page_bp.admin_preview_course', course_type=lesson.course_name)}}" class="nav-btn">Back to Course</a>
    {% if next_l %}<a href="{{url_for('admin_page_bp.admin_preview_lesson',lesson_id=next_l.id)}}" class="nav-btn">Next: {{next_l.lesson}} →</a>{% else %}<button class="nav-btn" disabled>Next →</button>{% endif %}
    </div></body></html>
    ''', lesson=lesson, prev_l=prev_l, next_l=next_l, lesson_render_content=lesson_render_content)

@admin_page_bp.route('/course-studio')
def admin_course_studio_page():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_page_bp.admin_login'))

    # Return a simple page for now - we'll implement the full studio later
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
                                            const staticPath = lesson.file_path.split('static/')[1] || lesson.file_path;
                                            previewHTML += `<div class="video-container-preview"><p style="color:#aaa;"><i>Video File: ${lesson.file_path.split('/').pop()}</i></p><video controls width="100%"><source src="/static/${staticPath}" type="video/${lesson.file_path.split('.').pop()}">Not supported.</video></div>`;
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
                                            const staticPath = lesson.file_path.split('static/')[1] || lesson.file_path;
                                            previewHTML += `<p><a href="/static/${staticPath}" download class="download-btn" style="opacity:1; cursor:pointer; background-color:#ff6b35;">Download: ${lesson.file_path.split('/').pop()}</a></p>`;
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

    """)
