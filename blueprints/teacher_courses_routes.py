from flask import Blueprint, render_template, render_template_string, redirect, url_for, session, request, jsonify
import json
import os
from werkzeug.utils import secure_filename
from datetime import datetime

# Import utilities
from utils.db_utils import get_db_connection, return_db_connection
from utils.logging_utils import app_logger, db_logger, log_info, log_error, log_warning
from utils.security_utils import require_admin_auth, sanitize_input
from utils.security_middleware import csrf_protect

teacher_courses_bp = Blueprint('teacher_courses_bp', __name__, url_prefix='/teacher')

def require_teacher_auth(f):
    """Decorator to require teacher authentication."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('teacher_logged_in'):
            return redirect(url_for('teacher_auth_bp.teacher_login'))
        return f(*args, **kwargs)
    return decorated_function

@teacher_courses_bp.route('/courses')
@require_teacher_auth
def teacher_courses():
    """View teacher's courses."""
    teacher_id = session.get('teacher_id')
    
    conn = None
    try:
        conn = get_db_connection()
        # For now, we'll show all courses (in a real app, you'd filter by teacher)
        courses_data = conn.execute("SELECT id, name, description, course_settings FROM courses ORDER BY created_at DESC").fetchall()
        
        output_courses = []
        for course_row in courses_data:
            course_dict = dict(course_row)
            try:
                course_dict['course_settings'] = json.loads(course_row['course_settings']) if course_row['course_settings'] else {}
            except:
                course_dict['course_settings'] = course_row['course_settings'] if course_row['course_settings'] else {}
            output_courses.append(course_dict)
            
        return render_template_string('''
        <html><head><title>My Courses - Teacher Dashboard</title>
        <style>body{font-family:Arial,sans-serif;background:#111;color:#fff;margin:0;padding:20px;}.header{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;display:flex;justify-content:space-between;align-items:center;}.header h1{color:#4CAF50;margin:0;}.logout-btn{background:#4CAF50;color:#fff;padding:10px 20px;border:none;border-radius:8px;text-decoration:none;font-weight:bold;}.courses-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px;}.course-card{background:#222;border-radius:10px;padding:20px;border-left:4px solid #4CAF50;transition:transform 0.3s;}.course-card:hover{transform:translateY(-5px);}.course-title{color:#4CAF50;font-size:1.5rem;margin-bottom:10px;}.course-desc{color:#ccc;margin-bottom:15px;}.course-meta{display:flex;justify-content:space-between;color:#999;font-size:0.9rem;}.btn{background:#4CAF50;color:#fff;padding:8px 15px;border:none;border-radius:5px;text-decoration:none;font-size:0.9rem;margin-right:10px;}.btn-secondary{background:#555;}</style></head>
        <body><div class="header"><h1>📚 My Courses</h1>
        <div><a href="{{url_for('teacher_auth_bp.teacher_dashboard')}}" class="btn btn-secondary">Dashboard</a><a href="{{url_for('teacher_courses_bp.create_course')}}" class="btn">Create New Course</a><a href="{{url_for('teacher_auth_bp.teacher_logout')}}" class="logout-btn">Logout</a></div></div>
        <div class="courses-grid">
        {% for course in courses %}
        <div class="course-card">
        <div class="course-title">{{course.name}}</div>
        <div class="course-desc">{{course.description or 'No description available.'}}</div>
        <div class="course-meta">
        <span>Created: {{course.course_settings.created_date if course.course_settings.created_date else 'N/A'}}</span>
        <span>Lessons: {{course.course_settings.lesson_count if course.course_settings.lesson_count else 0}}</span>
        </div>
        <div style="margin-top:15px;">
        <a href="{{url_for('teacher_courses_bp.edit_course', course_id=course.id)}}" class="btn">Edit Course</a>
        <a href="{{url_for('teacher_courses_bp.manage_course_content', course_id=course.id)}}" class="btn btn-secondary">Manage Content</a>
        </div>
        </div>
        {% endfor %}
        </div>
        {% if not courses %}
        <div style="text-align:center;padding:60px;color:#777;">
        <h3>You haven't created any courses yet.</h3>
        <p><a href="{{url_for('teacher_courses_bp.create_course')}}" class="btn">Create Your First Course</a></p>
        </div>
        {% endif %}
        </body></html>
        ''', courses=output_courses)
    except Exception as e:
        if conn:
            return_db_connection(conn)
        log_error(db_logger, "Failed to retrieve teacher courses", error=str(e))
        return render_template_string('''
        <html><head><title>Error</title></head><body style="background:#111;color:#fff;font-family:Arial;padding:40px;">
        <h2>Error Loading Courses</h2>
        <p>There was an error loading your courses. Please try again later.</p>
        <a href="{{url_for('teacher_auth_bp.teacher_dashboard')}}" style="color:#4CAF50;">← Back to Dashboard</a>
        </body></html>
        ''')
    finally:
        if conn:
            return_db_connection(conn)

@teacher_courses_bp.route('/courses/create', methods=['GET', 'POST'])
@require_teacher_auth
@csrf_protect
def create_course():
    """Create a new course."""
    from utils.security_middleware import generate_csrf_token
    csrf_token = generate_csrf_token()
    
    message = ''
    if request.method == 'POST':
        # Validate CSRF token (handled by decorator)
        course_name = sanitize_input(request.form.get('course_name'))
        course_description = sanitize_input(request.form.get('course_description', ''))
        
        if not course_name:
            message = 'Course name is required.'
        else:
            conn = None
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('INSERT INTO courses (name, description) VALUES (?, ?)',
                               (course_name, course_description))
                course_id = cursor.lastrowid
                conn.commit()
                log_info(app_logger, "Course created successfully", course_id=course_id, course_name=course_name)
                return redirect(url_for('teacher_courses_bp.teacher_courses', message='Course created successfully!'))
            except Exception as e:
                log_error(db_logger, "Failed to create course", error=str(e))
                message = 'Failed to create course. Please try again.'
            finally:
                if conn:
                    return_db_connection(conn)
    
    return render_template_string('''
    <html><head><title>Create Course - Teacher Dashboard</title>
    <style>body{font-family:Arial,sans-serif;background:#111;color:#fff;margin:0;padding:20px;}.header{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;display:flex;justify-content:space-between;align-items:center;}.header h1{color:#4CAF50;margin:0;}.logout-btn{background:#4CAF50;color:#fff;padding:10px 20px;border:none;border-radius:8px;text-decoration:none;font-weight:bold;}.form-container{background:#222;padding:30px;border-radius:10px;max-width:600px;margin:0 auto;}.form-group{margin-bottom:20px;}.form-group label{display:block;margin-bottom:5px;color:#4CAF50;font-weight:bold;}.form-group input,.form-group textarea{width:100%;padding:12px;border-radius:8px;border:none;background:#333;color:#fff;}.form-group textarea{height:120px;resize:vertical;}.btn{background:#4CAF50;color:#fff;padding:12px 25px;border:none;border-radius:8px;font-size:1rem;cursor:pointer;font-weight:bold;}.btn-secondary{background:#555;text-decoration:none;display:inline-block;text-align:center;}.msg{padding:15px;border-radius:8px;margin-bottom:20px;}.error{background:rgba(244,67,54,0.1);color:#f44336;}.success{background:rgba(76,175,80,0.1);color:#4CAF50;}</style></head>
    <body><div class="header"><h1>🆕 Create New Course</h1>
    <div><a href="{{url_for('teacher_courses_bp.teacher_courses')}}" class="btn btn-secondary">← My Courses</a><a href="{{url_for('teacher_auth_bp.teacher_logout')}}" class="logout-btn">Logout</a></div></div>
    <div class="form-container">
    <form method="post">
    <input type="hidden" name="csrf_token" value="{{csrf_token}}">
    <div class="form-group">
    <label for="course_name">Course Name *</label>
    <input type="text" id="course_name" name="course_name" required>
    </div>
    <div class="form-group">
    <label for="course_description">Course Description</label>
    <textarea id="course_description" name="course_description"></textarea>
    </div>
    <button type="submit" class="btn">Create Course</button>
    </form>
    {% if message %}<div class="msg {% if 'successfully' in message %}success{% else %}error{% endif %}">{{message}}</div>{% endif %}
    </div>
    </body></html>
    ''', message=message, csrf_token=csrf_token)

@teacher_courses_bp.route('/courses/<int:course_id>/edit', methods=['GET', 'POST'])
@require_teacher_auth
@csrf_protect
def edit_course(course_id):
    """Edit an existing course."""
    from utils.security_middleware import generate_csrf_token
    csrf_token = generate_csrf_token()
    
    # Check if course exists
    conn = None
    try:
        conn = get_db_connection()
        course = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
        if not course:
            return "Course not found", 404
        
        message = ''
        if request.method == 'POST':
            # Validate CSRF token (handled by decorator)
            course_name = sanitize_input(request.form.get('course_name'))
            course_description = sanitize_input(request.form.get('course_description', ''))
            
            if not course_name:
                message = 'Course name is required.'
            else:
                try:
                    cursor = conn.cursor()
                    cursor.execute('UPDATE courses SET name = ?, description = ? WHERE id = ?',
                                   (course_name, course_description, course_id))
                    conn.commit()
                    log_info(app_logger, "Course updated successfully", course_id=course_id, course_name=course_name)
                    message = 'Course updated successfully!'
                except Exception as e:
                    log_error(db_logger, "Failed to update course", error=str(e))
                    message = 'Failed to update course. Please try again.'
        
        return render_template_string('''
        <html><head><title>Edit Course - Teacher Dashboard</title>
        <style>body{font-family:Arial,sans-serif;background:#111;color:#fff;margin:0;padding:20px;}.header{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;display:flex;justify-content:space-between;align-items:center;}.header h1{color:#4CAF50;margin:0;}.logout-btn{background:#4CAF50;color:#fff;padding:10px 20px;border:none;border-radius:8px;text-decoration:none;font-weight:bold;}.form-container{background:#222;padding:30px;border-radius:10px;max-width:600px;margin:0 auto;}.form-group{margin-bottom:20px;}.form-group label{display:block;margin-bottom:5px;color:#4CAF50;font-weight:bold;}.form-group input,.form-group textarea{width:100%;padding:12px;border-radius:8px;border:none;background:#333;color:#fff;}.form-group textarea{height:120px;resize:vertical;}.btn{background:#4CAF50;color:#fff;padding:12px 25px;border:none;border-radius:8px;font-size:1rem;cursor:pointer;font-weight:bold;}.btn-secondary{background:#555;text-decoration:none;display:inline-block;text-align:center;}.msg{padding:15px;border-radius:8px;margin-bottom:20px;}.error{background:rgba(244,67,54,0.1);color:#f44336;}.success{background:rgba(76,175,80,0.1);color:#4CAF50;}</style></head>
        <body><div class="header"><h1>✏️ Edit Course</h1>
        <div><a href="{{url_for('teacher_courses_bp.teacher_courses')}}" class="btn btn-secondary">← My Courses</a><a href="{{url_for('teacher_auth_bp.teacher_logout')}}" class="logout-btn">Logout</a></div></div>
        <div class="form-container">
        <form method="post">
        <input type="hidden" name="csrf_token" value="{{csrf_token}}">
        <div class="form-group">
        <label for="course_name">Course Name *</label>
        <input type="text" id="course_name" name="course_name" value="{{course.name}}" required>
        </div>
        <div class="form-group">
        <label for="course_description">Course Description</label>
        <textarea id="course_description" name="course_description">{{course.description or ''}}</textarea>
        </div>
        <button type="submit" class="btn">Update Course</button>
        </form>
        {% if message %}<div class="msg {% if 'successfully' in message %}success{% else %}error{% endif %}">{{message}}</div>{% endif %}
        </div>
        </body></html>
        ''', course=dict(course), message=message, csrf_token=csrf_token)
    except Exception as e:
        if conn:
            return_db_connection(conn)
        return "Error loading course", 500
    finally:
        if conn:
            return_db_connection(conn)

@teacher_courses_bp.route('/courses/<int:course_id>/content')
@require_teacher_auth
def manage_course_content(course_id):
    """Manage course content (modules and lessons)."""
    conn = None
    try:
        conn = get_db_connection()
        # Check if course exists
        course = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
        if not course:
            return "Course not found", 404
        
        # Get modules for this course
        modules_data = conn.execute("SELECT * FROM modules WHERE course_id = ? ORDER BY order_index", (course_id,)).fetchall()
        
        # Get lessons for this course
        lessons_data = conn.execute("""
            SELECT l.*, m.name as module_name
            FROM lessons l 
            JOIN modules m ON l.module_id = m.id
            WHERE l.course_id = ? 
            ORDER BY m.order_index, l.order_index
        """, (course_id,)).fetchall()
        
        modules = [dict(row) for row in modules_data]
        lessons = []
        for lesson_row in lessons_data:
            lesson_dict = dict(lesson_row)
            try:
                lesson_dict['element_properties'] = json.loads(lesson_row['element_properties']) if lesson_row['element_properties'] else {}
            except:
                lesson_dict['element_properties'] = {}
            lessons.append(lesson_dict)
        
        return render_template_string('''
        <html><head><title>Manage Course Content - Teacher Dashboard</title>
        <style>body{font-family:Arial,sans-serif;background:#111;color:#fff;margin:0;padding:20px;}.header{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;display:flex;justify-content:space-between;align-items:center;}.header h1{color:#4CAF50;margin:0;}.logout-btn{background:#4CAF50;color:#fff;padding:10px 20px;border:none;border-radius:8px;text-decoration:none;font-weight:bold;}.section{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;}.section h2{color:#4CAF50;margin-top:0;}.modules-list,.lessons-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:15px;}.module-card,.lesson-card{background:#333;padding:15px;border-radius:8px;}.module-card{border-left:3px solid #4CAF50;}.lesson-card{border-left:3px solid #2196F3;}.btn{background:#4CAF50;color:#fff;padding:8px 15px;border:none;border-radius:5px;text-decoration:none;font-size:0.9rem;margin-right:10px;}.btn-secondary{background:#555;}.btn-info{background:#2196F3;}</style></head>
        <body><div class="header"><h1>📝 Manage Course Content</h1>
        <div><a href="{{url_for('teacher_courses_bp.teacher_courses')}}" class="btn btn-secondary">← My Courses</a><a href="{{url_for('teacher_courses_bp.create_module', course_id=course.id)}}" class="btn">Add Module</a><a href="{{url_for('teacher_auth_bp.teacher_logout')}}" class="logout-btn">Logout</a></div></div>
        
        <div class="section">
        <h2>📚 Modules</h2>
        <div class="modules-list">
        {% for module in modules %}
        <div class="module-card">
        <strong>{{module.name}}</strong><br>
        <small>{{module.description or 'No description'}}</small><br>
        <div style="margin-top:10px;">
        <a href="{{url_for('teacher_courses_bp.edit_module', module_id=module.id)}}" class="btn">Edit</a>
        <a href="{{url_for('teacher_courses_bp.delete_module', module_id=module.id)}}" class="btn btn-secondary" onclick="return confirm('Are you sure you want to delete this module?')">Delete</a>
        <a href="{{url_for('teacher_courses_bp.add_lesson', module_id=module.id)}}" class="btn btn-info">Add Lesson</a>
        </div>
        </div>
        {% else %}
        <p>No modules created yet. <a href="{{url_for('teacher_courses_bp.create_module', course_id=course.id)}}" class="btn">Create First Module</a></p>
        {% endfor %}
        </div>
        </div>
        
        <div class="section">
        <h2>📖 Lessons</h2>
        <div class="lessons-list">
        {% for lesson in lessons %}
        <div class="lesson-card">
        <strong>{{lesson.lesson}}</strong><br>
        <small>In module: {{lesson.module_name}}</small><br>
        <small>Type: {{lesson.content_type}}</small><br>
        <div style="margin-top:10px;">
        <a href="{{url_for('teacher_courses_bp.edit_lesson', lesson_id=lesson.id)}}" class="btn">Edit</a>
        <a href="{{url_for('teacher_courses_bp.delete_lesson', lesson_id=lesson.id)}}" class="btn btn-secondary" onclick="return confirm('Are you sure you want to delete this lesson?')">Delete</a>
        </div>
        </div>
        {% else %}
        <p>No lessons created yet.</p>
        {% endfor %}
        </div>
        </div>
        </body></html>
        ''', course=dict(course), modules=modules, lessons=lessons)
    except Exception as e:
        if conn:
            return_db_connection(conn)
        log_error(db_logger, "Failed to manage course content", error=str(e))
        return "Error loading course content", 500
    finally:
        if conn:
            return_db_connection(conn)

@teacher_courses_bp.route('/courses/<int:course_id>/modules/create', methods=['GET', 'POST'])
@require_teacher_auth
@csrf_protect
def create_module(course_id):
    """Create a new module for a course."""
    from utils.security_middleware import generate_csrf_token
    csrf_token = generate_csrf_token()
    
    conn = None
    try:
        conn = get_db_connection()
        # Check if course exists
        course = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
        if not course:
            return "Course not found", 404
        
        message = ''
        if request.method == 'POST':
            # Validate CSRF token (handled by decorator)
            module_name = sanitize_input(request.form.get('module_name'))
            module_description = sanitize_input(request.form.get('module_description', ''))
            order_index = request.form.get('order_index', 1)
            
            if not module_name:
                message = 'Module name is required.'
            else:
                try:
                    order_index = int(order_index)
                except ValueError:
                    order_index = 1
                
                try:
                    cursor = conn.cursor()
                    cursor.execute('INSERT INTO modules (course_id, name, description, order_index) VALUES (?, ?, ?, ?)',
                                   (course_id, module_name, module_description, order_index))
                    module_id = cursor.lastrowid
                    conn.commit()
                    log_info(app_logger, "Module created successfully", module_id=module_id, module_name=module_name)
                    return redirect(url_for('teacher_courses_bp.manage_course_content', course_id=course_id))
                except Exception as e:
                    log_error(db_logger, "Failed to create module", error=str(e))
                    message = 'Failed to create module. Please try again.'
        
        return render_template_string('''
        <html><head><title>Create Module - Teacher Dashboard</title>
        <style>body{font-family:Arial,sans-serif;background:#111;color:#fff;margin:0;padding:20px;}.header{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;display:flex;justify-content:space-between;align-items:center;}.header h1{color:#4CAF50;margin:0;}.logout-btn{background:#4CAF50;color:#fff;padding:10px 20px;border:none;border-radius:8px;text-decoration:none;font-weight:bold;}.form-container{background:#222;padding:30px;border-radius:10px;max-width:600px;margin:0 auto;}.form-group{margin-bottom:20px;}.form-group label{display:block;margin-bottom:5px;color:#4CAF50;font-weight:bold;}.form-group input,.form-group textarea{width:100%;padding:12px;border-radius:8px;border:none;background:#333;color:#fff;}.form-group textarea{height:120px;resize:vertical;}.btn{background:#4CAF50;color:#fff;padding:12px 25px;border:none;border-radius:8px;font-size:1rem;cursor:pointer;font-weight:bold;}.btn-secondary{background:#555;text-decoration:none;display:inline-block;text-align:center;}.msg{padding:15px;border-radius:8px;margin-bottom:20px;}.error{background:rgba(244,67,54,0.1);color:#f44336;}.success{background:rgba(76,175,80,0.1);color:#4CAF50;}</style></head>
        <body><div class="header"><h1>🆕 Create New Module</h1>
        <div><a href="{{url_for('teacher_courses_bp.manage_course_content', course_id=course.id)}}" class="btn btn-secondary">← Course Content</a><a href="{{url_for('teacher_auth_bp.teacher_logout')}}" class="logout-btn">Logout</a></div></div>
        <div class="form-container">
        <form method="post">
        <input type="hidden" name="csrf_token" value="{{csrf_token}}">
        <div class="form-group">
        <label for="module_name">Module Name *</label>
        <input type="text" id="module_name" name="module_name" required>
        </div>
        <div class="form-group">
        <label for="module_description">Module Description</label>
        <textarea id="module_description" name="module_description"></textarea>
        </div>
        <div class="form-group">
        <label for="order_index">Order Index</label>
        <input type="number" id="order_index" name="order_index" value="1" min="1">
        </div>
        <button type="submit" class="btn">Create Module</button>
        </form>
        {% if message %}<div class="msg {% if 'successfully' in message %}success{% else %}error{% endif %}">{{message}}</div>{% endif %}
        </div>
        </body></html>
        ''', course=dict(course), message=message, csrf_token=csrf_token)
    except Exception as e:
        if conn:
            return_db_connection(conn)
        return "Error creating module", 500
    finally:
        if conn:
            return_db_connection(conn)

@teacher_courses_bp.route('/modules/<int:module_id>/edit', methods=['GET', 'POST'])
@require_teacher_auth
@csrf_protect
def edit_module(module_id):
    """Edit an existing module."""
    from utils.security_middleware import generate_csrf_token
    csrf_token = generate_csrf_token()
    
    conn = None
    try:
        conn = get_db_connection()
        # Check if module exists
        module = conn.execute("SELECT * FROM modules WHERE id = ?", (module_id,)).fetchone()
        if not module:
            return "Module not found", 404
        
        # Get course for navigation
        course = conn.execute("SELECT * FROM courses WHERE id = ?", (module['course_id'],)).fetchone()
        
        message = ''
        if request.method == 'POST':
            # Validate CSRF token (handled by decorator)
            module_name = sanitize_input(request.form.get('module_name'))
            module_description = sanitize_input(request.form.get('module_description', ''))
            order_index = request.form.get('order_index', module['order_index'])
            
            if not module_name:
                message = 'Module name is required.'
            else:
                try:
                    order_index = int(order_index)
                except ValueError:
                    order_index = module['order_index']
                
                try:
                    cursor = conn.cursor()
                    cursor.execute('UPDATE modules SET name = ?, description = ?, order_index = ? WHERE id = ?',
                                   (module_name, module_description, order_index, module_id))
                    conn.commit()
                    log_info(app_logger, "Module updated successfully", module_id=module_id, module_name=module_name)
                    message = 'Module updated successfully!'
                except Exception as e:
                    log_error(db_logger, "Failed to update module", error=str(e))
                    message = 'Failed to update module. Please try again.'
        
        return render_template_string('''
        <html><head><title>Edit Module - Teacher Dashboard</title>
        <style>body{font-family:Arial,sans-serif;background:#111;color:#fff;margin:0;padding:20px;}.header{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;display:flex;justify-content:space-between;align-items:center;}.header h1{color:#4CAF50;margin:0;}.logout-btn{background:#4CAF50;color:#fff;padding:10px 20px;border:none;border-radius:8px;text-decoration:none;font-weight:bold;}.form-container{background:#222;padding:30px;border-radius:10px;max-width:600px;margin:0 auto;}.form-group{margin-bottom:20px;}.form-group label{display:block;margin-bottom:5px;color:#4CAF50;font-weight:bold;}.form-group input,.form-group textarea{width:100%;padding:12px;border-radius:8px;border:none;background:#333;color:#fff;}.form-group textarea{height:120px;resize:vertical;}.btn{background:#4CAF50;color:#fff;padding:12px 25px;border:none;border-radius:8px;font-size:1rem;cursor:pointer;font-weight:bold;}.btn-secondary{background:#555;text-decoration:none;display:inline-block;text-align:center;}.msg{padding:15px;border-radius:8px;margin-bottom:20px;}.error{background:rgba(244,67,54,0.1);color:#f44336;}.success{background:rgba(76,175,80,0.1);color:#4CAF50;}</style></head>
        <body><div class="header"><h1>✏️ Edit Module</h1>
        <div><a href="{{url_for('teacher_courses_bp.manage_course_content', course_id=course.id)}}" class="btn btn-secondary">← Course Content</a><a href="{{url_for('teacher_auth_bp.teacher_logout')}}" class="logout-btn">Logout</a></div></div>
        <div class="form-container">
        <form method="post">
        <input type="hidden" name="csrf_token" value="{{csrf_token}}">
        <div class="form-group">
        <label for="module_name">Module Name *</label>
        <input type="text" id="module_name" name="module_name" value="{{module.name}}" required>
        </div>
        <div class="form-group">
        <label for="module_description">Module Description</label>
        <textarea id="module_description" name="module_description">{{module.description or ''}}</textarea>
        </div>
        <div class="form-group">
        <label for="order_index">Order Index</label>
        <input type="number" id="order_index" name="order_index" value="{{module.order_index}}" min="1">
        </div>
        <button type="submit" class="btn">Update Module</button>
        </form>
        {% if message %}<div class="msg {% if 'successfully' in message %}success{% else %}error{% endif %}">{{message}}</div>{% endif %}
        </div>
        </body></html>
        ''', course=dict(course), module=dict(module), message=message, csrf_token=csrf_token)
    except Exception as e:
        if conn:
            return_db_connection(conn)
        return "Error editing module", 500
    finally:
        if conn:
            return_db_connection(conn)

@teacher_courses_bp.route('/modules/<int:module_id>/delete', methods=['POST'])
@require_teacher_auth
@csrf_protect
def delete_module(module_id):
    """Delete a module."""
    conn = None
    try:
        conn = get_db_connection()
        # Check if module exists
        module = conn.execute("SELECT course_id FROM modules WHERE id = ?", (module_id,)).fetchone()
        if not module:
            return "Module not found", 404
        
        course_id = module['course_id']
        
        # Check if module has lessons
        lesson_count = conn.execute("SELECT COUNT(*) as count FROM lessons WHERE module_id = ?", (module_id,)).fetchone()['count']
        if lesson_count > 0:
            return "Cannot delete module with lessons. Delete lessons first.", 400
        
        # Delete module
        cursor = conn.cursor()
        cursor.execute("DELETE FROM modules WHERE id = ?", (module_id,))
        conn.commit()
        log_info(app_logger, "Module deleted successfully", module_id=module_id)
        
        return redirect(url_for('teacher_courses_bp.manage_course_content', course_id=course_id))
    except Exception as e:
        if conn:
            return_db_connection(conn)
        log_error(db_logger, "Failed to delete module", error=str(e))
        return "Error deleting module", 500
    finally:
        if conn:
            return_db_connection(conn)

@teacher_courses_bp.route('/modules/<int:module_id>/lessons/add', methods=['GET', 'POST'])
@require_teacher_auth
@csrf_protect
def add_lesson(module_id):
    """Add a lesson to a module."""
    from utils.security_middleware import generate_csrf_token
    csrf_token = generate_csrf_token()
    
    conn = None
    try:
        conn = get_db_connection()
        # Check if module exists
        module = conn.execute("SELECT * FROM modules WHERE id = ?", (module_id,)).fetchone()
        if not module:
            return "Module not found", 404
        
        # Get course for navigation
        course = conn.execute("SELECT * FROM courses WHERE id = ?", (module['course_id'],)).fetchone()
        
        message = ''
        if request.method == 'POST':
            # Validate CSRF token (handled by decorator)
            lesson_title = sanitize_input(request.form.get('lesson_title'))
            content_type = request.form.get('content_type', 'file')
            order_index = request.form.get('order_index', 1)
            
            if not lesson_title:
                message = 'Lesson title is required.'
            else:
                try:
                    order_index = int(order_index)
                except ValueError:
                    order_index = 1
                
                try:
                    cursor = conn.cursor()
                    cursor.execute('''INSERT INTO lessons (course_id, module_id, lesson, content_type, order_index) 
                                      VALUES (?, ?, ?, ?, ?)''',
                                   (module['course_id'], module_id, lesson_title, content_type, order_index))
                    lesson_id = cursor.lastrowid
                    conn.commit()
                    log_info(app_logger, "Lesson created successfully", lesson_id=lesson_id, lesson_title=lesson_title)
                    return redirect(url_for('teacher_courses_bp.manage_course_content', course_id=module['course_id']))
                except Exception as e:
                    log_error(db_logger, "Failed to create lesson", error=str(e))
                    message = 'Failed to create lesson. Please try again.'
        
        return render_template_string('''
        <html><head><title>Add Lesson - Teacher Dashboard</title>
        <style>body{font-family:Arial,sans-serif;background:#111;color:#fff;margin:0;padding:20px;}.header{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;display:flex;justify-content:space-between;align-items:center;}.header h1{color:#4CAF50;margin:0;}.logout-btn{background:#4CAF50;color:#fff;padding:10px 20px;border:none;border-radius:8px;text-decoration:none;font-weight:bold;}.form-container{background:#222;padding:30px;border-radius:10px;max-width:600px;margin:0 auto;}.form-group{margin-bottom:20px;}.form-group label{display:block;margin-bottom:5px;color:#4CAF50;font-weight:bold;}.form-group input,.form-group select{width:100%;padding:12px;border-radius:8px;border:none;background:#333;color:#fff;}.form-group textarea{width:100%;padding:12px;border-radius:8px;border:none;background:#333;color:#fff;height:120px;resize:vertical;}.btn{background:#4CAF50;color:#fff;padding:12px 25px;border:none;border-radius:8px;font-size:1rem;cursor:pointer;font-weight:bold;}.btn-secondary{background:#555;text-decoration:none;display:inline-block;text-align:center;}.msg{padding:15px;border-radius:8px;margin-bottom:20px;}.error{background:rgba(244,67,54,0.1);color:#f44336;}.success{background:rgba(76,175,80,0.1);color:#4CAF50;}</style></head>
        <body><div class="header"><h1>🆕 Add New Lesson</h1>
        <div><a href="{{url_for('teacher_courses_bp.manage_course_content', course_id=course.id)}}" class="btn btn-secondary">← Course Content</a><a href="{{url_for('teacher_auth_bp.teacher_logout')}}" class="logout-btn">Logout</a></div></div>
        <div class="form-container">
        <form method="post">
        <input type="hidden" name="csrf_token" value="{{csrf_token}}">
        <div class="form-group">
        <label for="lesson_title">Lesson Title *</label>
        <input type="text" id="lesson_title" name="lesson_title" required>
        </div>
        <div class="form-group">
        <label for="content_type">Content Type</label>
        <select id="content_type" name="content_type">
        <option value="file">File Upload</option>
        <option value="video">Video</option>
        <option value="text">Text Content</option>
        <option value="quiz">Quiz</option>
        </select>
        </div>
        <div class="form-group">
        <label for="order_index">Order Index</label>
        <input type="number" id="order_index" name="order_index" value="1" min="1">
        </div>
        <button type="submit" class="btn">Add Lesson</button>
        </form>
        {% if message %}<div class="msg {% if 'successfully' in message %}success{% else %}error{% endif %}">{{message}}</div>{% endif %}
        </div>
        </body></html>
        ''', course=dict(course), module=dict(module), message=message, csrf_token=csrf_token)
    except Exception as e:
        if conn:
            return_db_connection(conn)
        return "Error adding lesson", 500
    finally:
        if conn:
            return_db_connection(conn)

@teacher_courses_bp.route('/lessons/<int:lesson_id>/edit', methods=['GET', 'POST'])
@require_teacher_auth
@csrf_protect
def edit_lesson(lesson_id):
    """Edit an existing lesson."""
    from utils.security_middleware import generate_csrf_token
    csrf_token = generate_csrf_token()
    
    conn = None
    try:
        conn = get_db_connection()
        # Check if lesson exists
        lesson = conn.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
        if not lesson:
            return "Lesson not found", 404
        
        # Get module and course for navigation
        module = conn.execute("SELECT * FROM modules WHERE id = ?", (lesson['module_id'],)).fetchone()
        course = conn.execute("SELECT * FROM courses WHERE id = ?", (lesson['course_id'],)).fetchone()
        
        message = ''
        if request.method == 'POST':
            # Validate CSRF token (handled by decorator)
            lesson_title = sanitize_input(request.form.get('lesson_title'))
            content_type = request.form.get('content_type', lesson['content_type'])
            order_index = request.form.get('order_index', lesson['order_index'])
            
            if not lesson_title:
                message = 'Lesson title is required.'
            else:
                try:
                    order_index = int(order_index)
                except ValueError:
                    order_index = lesson['order_index']
                
                try:
                    cursor = conn.cursor()
                    cursor.execute('''UPDATE lessons SET lesson = ?, content_type = ?, order_index = ? 
                                      WHERE id = ?''',
                                   (lesson_title, content_type, order_index, lesson_id))
                    conn.commit()
                    log_info(app_logger, "Lesson updated successfully", lesson_id=lesson_id, lesson_title=lesson_title)
                    message = 'Lesson updated successfully!'
                except Exception as e:
                    log_error(db_logger, "Failed to update lesson", error=str(e))
                    message = 'Failed to update lesson. Please try again.'
        
        return render_template_string('''
        <html><head><title>Edit Lesson - Teacher Dashboard</title>
        <style>body{font-family:Arial,sans-serif;background:#111;color:#fff;margin:0;padding:20px;}.header{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;display:flex;justify-content:space-between;align-items:center;}.header h1{color:#4CAF50;margin:0;}.logout-btn{background:#4CAF50;color:#fff;padding:10px 20px;border:none;border-radius:8px;text-decoration:none;font-weight:bold;}.form-container{background:#222;padding:30px;border-radius:10px;max-width:600px;margin:0 auto;}.form-group{margin-bottom:20px;}.form-group label{display:block;margin-bottom:5px;color:#4CAF50;font-weight:bold;}.form-group input,.form-group select{width:100%;padding:12px;border-radius:8px;border:none;background:#333;color:#fff;}.form-group textarea{width:100%;padding:12px;border-radius:8px;border:none;background:#333;color:#fff;height:120px;resize:vertical;}.btn{background:#4CAF50;color:#fff;padding:12px 25px;border:none;border-radius:8px;font-size:1rem;cursor:pointer;font-weight:bold;}.btn-secondary{background:#555;text-decoration:none;display:inline-block;text-align:center;}.msg{padding:15px;border-radius:8px;margin-bottom:20px;}.error{background:rgba(244,67,54,0.1);color:#f44336;}.success{background:rgba(76,175,80,0.1);color:#4CAF50;}</style></head>
        <body><div class="header"><h1>✏️ Edit Lesson</h1>
        <div><a href="{{url_for('teacher_courses_bp.manage_course_content', course_id=course.id)}}" class="btn btn-secondary">← Course Content</a><a href="{{url_for('teacher_auth_bp.teacher_logout')}}" class="logout-btn">Logout</a></div></div>
        <div class="form-container">
        <form method="post">
        <input type="hidden" name="csrf_token" value="{{csrf_token}}">
        <div class="form-group">
        <label for="lesson_title">Lesson Title *</label>
        <input type="text" id="lesson_title" name="lesson_title" value="{{lesson.lesson}}" required>
        </div>
        <div class="form-group">
        <label for="content_type">Content Type</label>
        <select id="content_type" name="content_type">
        <option value="file" {% if lesson.content_type == 'file' %}selected{% endif %}>File Upload</option>
        <option value="video" {% if lesson.content_type == 'video' %}selected{% endif %}>Video</option>
        <option value="text" {% if lesson.content_type == 'text' %}selected{% endif %}>Text Content</option>
        <option value="quiz" {% if lesson.content_type == 'quiz' %}selected{% endif %}>Quiz</option>
        </select>
        </div>
        <div class="form-group">
        <label for="order_index">Order Index</label>
        <input type="number" id="order_index" name="order_index" value="{{lesson.order_index}}" min="1">
        </div>
        <button type="submit" class="btn">Update Lesson</button>
        </form>
        {% if message %}<div class="msg {% if 'successfully' in message %}success{% else %}error{% endif %}">{{message}}</div>{% endif %}
        </div>
        </body></html>
        ''', course=dict(course), module=dict(module), lesson=dict(lesson), message=message, csrf_token=csrf_token)
    except Exception as e:
        if conn:
            return_db_connection(conn)
        return "Error editing lesson", 500
    finally:
        if conn:
            return_db_connection(conn)

@teacher_courses_bp.route('/lessons/<int:lesson_id>/delete', methods=['POST'])
@require_teacher_auth
@csrf_protect
def delete_lesson(lesson_id):
    """Delete a lesson."""
    conn = None
    try:
        conn = get_db_connection()
        # Check if lesson exists
        lesson = conn.execute("SELECT course_id FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
        if not lesson:
            return "Lesson not found", 404
        
        course_id = lesson['course_id']
        
        # Delete lesson
        cursor = conn.cursor()
        cursor.execute("DELETE FROM lessons WHERE id = ?", (lesson_id,))
        conn.commit()
        log_info(app_logger, "Lesson deleted successfully", lesson_id=lesson_id)
        
        return redirect(url_for('teacher_courses_bp.manage_course_content', course_id=course_id))
    except Exception as e:
        if conn:
            return_db_connection(conn)
        log_error(db_logger, "Failed to delete lesson", error=str(e))
        return "Error deleting lesson", 500
    finally:
        if conn:
            return_db_connection(conn)