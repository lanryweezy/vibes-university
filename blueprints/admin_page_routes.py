from flask import Blueprint, render_template, redirect, url_for, session, request, jsonify
import json
import os
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

        # Contact Messages
        unread_messages = conn.execute("SELECT * FROM contact_messages WHERE status = 'unread' ORDER BY created_at DESC LIMIT 10").fetchall()
        unread_count_row = conn.execute("SELECT COUNT(*) as count FROM contact_messages WHERE status = 'unread'").fetchone()
        unread_count = unread_count_row['count'] if unread_count_row else 0

        return render_template('admin_dashboard.html',
                             message=message,
                             total_users=total_users,
                             total_enrollments=total_enrollments,
                             unread_count=unread_count,
                             total_revenue=total_revenue,
                             total_lessons_stat=total_lessons_stat,
                             recent_enrollments=recent_enrollments,
                             unread_messages=unread_messages)
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
        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            log_info(app_logger, "Admin logged in successfully")
            return redirect(url_for('admin_page_bp.admin_dashboard'))
        else:
            message = 'Invalid password.'
            log_warning(app_logger, "Admin login failed")
    return render_template('admin_login.html', message=message, csrf_token=csrf_token)

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
        return render_template('admin_users.html', users=users)
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

        return render_template('admin_analytics.html', monthly_revenue=monthly_revenue, course_performance=course_performance)
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

    csrf_token = generate_csrf_token()
    return render_template('admin_settings.html', message=message, csrf_token=csrf_token)

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
        csrf_token = generate_csrf_token()
        return render_template('admin_announcements.html', anns=anns, message=message, csrf_token=csrf_token)
    except Exception as e:
        log_error(app_logger, "Admin announcements error", error=str(e))
        return "Error", 500
    finally:
        if conn:
            return_db_connection(conn)
