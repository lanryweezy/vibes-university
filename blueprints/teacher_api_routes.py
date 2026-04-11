from flask import Blueprint, jsonify, request, session
import sqlite3
import json
import os

# Import utilities
from utils.db_utils import get_db_connection, return_db_connection
from utils.logging_utils import app_logger, db_logger, security_logger, payment_logger, log_info, log_error, log_warning
# Import security utilities
from utils.security_utils import require_teacher_auth, validate_email, validate_phone, sanitize_input
# Import rate limiter
from utils.rate_limiter import rate_limit

teacher_api_bp = Blueprint('teacher_api_bp', __name__, url_prefix='/api/teacher')

# --- Course Management APIs ---
@teacher_api_bp.route('/courses', methods=['POST'])
@require_teacher_auth
@rate_limit('api')
def api_teacher_create_course():
    data = request.get_json()
    if not data or not data.get('name'):
        log_warning(app_logger, "Course creation failed - missing name")
        return jsonify({'error': 'Course name is required'}), 400
    
    # Sanitize course name and description
    course_name = sanitize_input(data['name'])
    course_description = sanitize_input(data.get('description', ''))
    
    name = course_name
    description = course_description
    settings = data.get('settings', {})
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO courses (name, description, course_settings) VALUES (?, ?, ?)',
                      (name, description, json.dumps(settings)))
        course_id = cursor.lastrowid
        conn.commit()
        log_info(app_logger, "Course created successfully", course_id=course_id, course_name=name)
    except sqlite3.IntegrityError:
        if conn:
            return_db_connection(conn)
        log_warning(app_logger, "Course creation failed - course already exists", course_name=name)
        return jsonify({'error': 'Course with this name already exists'}), 400
    except Exception as e:
        if conn:
            return_db_connection(conn)
        log_error(db_logger, "Course creation failed with database error", error=str(e))
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        if conn:
            return_db_connection(conn)
    
    return jsonify({'message': 'Course created successfully', 'course_id': course_id}), 201

@teacher_api_bp.route('/courses', methods=['GET'])
def api_teacher_get_courses():
    if not session.get('teacher_logged_in'):
        return jsonify({'error': 'Not authorized'}), 401
    
    conn = None
    try:
        conn = get_db_connection()
        courses_data = conn.execute("SELECT id, name, description, course_settings, created_at FROM courses ORDER BY created_at DESC").fetchall()
    except Exception as e:
        if conn:
            return_db_connection(conn)
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        if conn:
            return_db_connection(conn)
    
    courses = []
    for course_row in courses_data:
        course_dict = dict(course_row)
        try:
            course_dict['course_settings'] = json.loads(course_row['course_settings']) if course_row['course_settings'] else {}
        except:
            course_dict['course_settings'] = {}
        courses.append(course_dict)
    
    return jsonify(courses)

@teacher_api_bp.route('/courses/<int:course_id>', methods=['GET'])
def api_teacher_get_course(course_id):
    if not session.get('teacher_logged_in'):
        return jsonify({'error': 'Not authorized'}), 401
    
    conn = None
    try:
        conn = get_db_connection()
        course_data = conn.execute("SELECT id, name, description, course_settings FROM courses WHERE id = ?", (course_id,)).fetchone()
        
        if not course_data:
            if conn:
                return_db_connection(conn)
            return jsonify({'error': 'Course not found'}), 404
        
        # Get modules for this course
        modules_data = conn.execute("SELECT id, name, description, order_index FROM modules WHERE course_id = ? ORDER BY order_index", (course_id,)).fetchall()
        
        # Get lessons for this course
        lessons_data = conn.execute("""
            SELECT l.id, l.lesson, l.description, l.content_type, l.element_properties, 
                   l.file_path, l.order_index, l.module_id, m.name as module_name
            FROM lessons l 
            JOIN modules m ON l.module_id = m.id
            WHERE l.course_id = ? 
            ORDER BY m.order_index, l.order_index
        """, (course_id,)).fetchall()
    except Exception as e:
        if conn:
            return_db_connection(conn)
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        if conn:
            return_db_connection(conn)
    
    course = dict(course_data)
    try:
        course['course_settings'] = json.loads(course_data['course_settings']) if course_data['course_settings'] else {}
    except:
        course['course_settings'] = {}
    
    course['modules'] = [dict(module) for module in modules_data]
    course['lessons'] = []
    
    for lesson_row in lessons_data:
        lesson_dict = dict(lesson_row)
        try:
            lesson_dict['element_properties'] = json.loads(lesson_row['element_properties']) if lesson_row['element_properties'] else {}
        except:
            lesson_dict['element_properties'] = {}
        course['lessons'].append(lesson_dict)
    
    return jsonify(course)

@teacher_api_bp.route('/courses/<int:course_id>', methods=['PUT'])
def api_teacher_update_course(course_id):
    if not session.get('teacher_logged_in'):
        return jsonify({'error': 'Not authorized'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    conn = None
    try:
        conn = get_db_connection()
        # Check if course exists
        existing_course = conn.execute("SELECT id FROM courses WHERE id = ?", (course_id,)).fetchone()
        if not existing_course:
            if conn:
                return_db_connection(conn)
            return jsonify({'error': 'Course not found'}), 404
        
        # Build update query dynamically
        fields_to_update = []
        params = []
        
        if 'name' in data:
            fields_to_update.append("name = ?")
            params.append(data['name'])
        
        if 'description' in data:
            fields_to_update.append("description = ?")
            params.append(data['description'])
        
        if 'settings' in data:
            fields_to_update.append("course_settings = ?")
            params.append(json.dumps(data['settings']))
        
        if not fields_to_update:
            if conn:
                return_db_connection(conn)
            return jsonify({'message': 'No fields to update'}), 200
        
        params.append(course_id)
        query = f"UPDATE courses SET {', '.join(fields_to_update)} WHERE id = ?"
        
        cursor = conn.cursor()
        cursor.execute(query, tuple(params))
        conn.commit()
    except sqlite3.IntegrityError:
        if conn:
            return_db_connection(conn)
        return jsonify({'error': 'Course with this name already exists'}), 400
    except Exception as e:
        if conn:
            return_db_connection(conn)
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        if conn:
            return_db_connection(conn)
    
    return jsonify({'message': 'Course updated successfully'})

# --- Module Management APIs ---
@teacher_api_bp.route('/courses/<int:course_id>/modules', methods=['POST'])
def api_teacher_create_module(course_id):
    if not session.get('teacher_logged_in'):
        return jsonify({'error': 'Not authorized'}), 401
    
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'Missing module name'}), 400
    
    name = data['name']
    description = data.get('description', '')
    order_index = data.get('order_index', 1)
    
    conn = None
    try:
        conn = get_db_connection()
        # Verify course exists
        if not conn.execute("SELECT id FROM courses WHERE id = ?", (course_id,)).fetchone():
            if conn:
                return_db_connection(conn)
            return jsonify({'error': 'Course not found'}), 404
        
        cursor = conn.cursor()
        cursor.execute('INSERT INTO modules (course_id, name, description, order_index) VALUES (?, ?, ?, ?)',
                      (course_id, name, description, order_index))
        module_id = cursor.lastrowid
        conn.commit()
    except Exception as e:
        if conn:
            return_db_connection(conn)
        return jsonify({'error': f'DB error: {str(e)}'}), 500
    finally:
        if conn:
            return_db_connection(conn)
    
    return jsonify({'message': 'Module created', 'module_id': module_id}), 201

@teacher_api_bp.route('/courses/<int:course_id>/modules', methods=['GET'])
def api_teacher_get_modules(course_id):
    if not session.get('teacher_logged_in'):
        return jsonify({'error': 'Not authorized'}), 401
    
    conn = None
    try:
        conn = get_db_connection()
        # Verify course exists
        if not conn.execute("SELECT id FROM courses WHERE id = ?", (course_id,)).fetchone():
            if conn:
                return_db_connection(conn)
            return jsonify({'error': 'Course not found'}), 404
        
        modules_data = conn.execute("SELECT id, name, description, order_index FROM modules WHERE course_id = ? ORDER BY order_index", (course_id,)).fetchall()
    except Exception as e:
        if conn:
            return_db_connection(conn)
        return jsonify({'error': f'DB error: {str(e)}'}), 500
    finally:
        if conn:
            return_db_connection(conn)
    
    return jsonify([dict(row) for row in modules_data])

@teacher_api_bp.route('/modules/<int:module_id>', methods=['PUT'])
def api_teacher_update_module(module_id):
    if not session.get('teacher_logged_in'):
        return jsonify({'error': 'Not authorized'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data'}), 400
    
    fields = []
    params_list = []
    if 'name' in data:
        fields.append("name = ?")
        params_list.append(data['name'])
    if 'description' in data:
        fields.append("description = ?")
        params_list.append(data['description'])
    if 'order_index' in data:
        fields.append("order_index = ?")
        params_list.append(data['order_index'])
    if not fields:
        return jsonify({'message': 'No fields to update'}), 200
    
    params_list.append(module_id)
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"UPDATE modules SET {','.join(fields)} WHERE id = ?", tuple(params_list))
        updated_rows = cursor.rowcount
        conn.commit()
    except Exception as e:
        if conn:
            return_db_connection(conn)
        return jsonify({'error': f'DB error: {str(e)}'}), 500
    finally:
        if conn:
            return_db_connection(conn)
    
    return jsonify({'message': 'Module updated'}) if updated_rows > 0 else jsonify({'error': 'Module not found or no change'}), 404

@teacher_api_bp.route('/modules/<int:module_id>', methods=['DELETE'])
def api_teacher_delete_module(module_id):
    if not session.get('teacher_logged_in'):
        return jsonify({'error': 'Not authorized'}), 401
    
    conn = None
    try:
        conn = get_db_connection()
        if conn.execute("SELECT COUNT(id) FROM lessons WHERE module_id = ?", (module_id,)).fetchone()['count'] > 0:
            if conn:
                return_db_connection(conn)
            return jsonify({'error': 'Module has lessons. Delete them first.'}), 400
        
        cursor = conn.cursor()
        cursor.execute("DELETE FROM modules WHERE id = ?", (module_id,))
        deleted_rows = cursor.rowcount
        conn.commit()
    except Exception as e:
        if conn:
            return_db_connection(conn)
        return jsonify({'error': f'DB error: {str(e)}'}), 500
    finally:
        if conn:
            return_db_connection(conn)
    
    return jsonify({'message': 'Module deleted'}) if deleted_rows > 0 else jsonify({'error': 'Module not found'}), 404

# --- Lesson Management APIs ---
@teacher_api_bp.route('/courses/<int:course_id>/lessons', methods=['POST'])
def api_teacher_create_lesson_in_course(course_id):
    if not session.get('teacher_logged_in'):
        return jsonify({'error': 'Not authorized'}), 401

    conn = None
    try:
        conn = get_db_connection()
        # Verify course exists
        course = conn.execute('SELECT id, name FROM courses WHERE id = ?', (course_id,)).fetchone()
        if not course:
            if conn:
                return_db_connection(conn)
            return jsonify({'error': 'Course not found'}), 404

        form_data = request.form  # For multipart/form-data

        lesson_title = form_data.get('lesson_title')
        module_id_str = form_data.get('module_id')
        content_type = form_data.get('content_type')
        order_index_str = form_data.get('order_index')
        element_properties_json = form_data.get('element_properties')  # Should be a JSON string

        if not all([lesson_title, module_id_str, content_type, order_index_str, element_properties_json]):
            return jsonify({'error': 'Missing required fields: lesson_title, module_id, content_type, order_index, element_properties'}), 400

        try:
            module_id = int(module_id_str)
            order_index = int(order_index_str)
        except ValueError:
            if conn:
                return_db_connection(conn)
            return jsonify({'error': 'module_id and order_index must be integers'}), 400

        # Verify module belongs to this course
        module = conn.execute('SELECT id FROM modules WHERE id = ? AND course_id = ?', (module_id, course_id)).fetchone()
        if not module:
            if conn:
                return_db_connection(conn)
            return jsonify({'error': 'Invalid module for this course'}), 400

        # Handle file upload if present
        file_path = None
        if 'file' in request.files:
            file = request.files['file']
            if file.filename != '':
                if allowed_file(file.filename):
                    # Save file with course_id/module_id prefix
                    filename = f"{course_id}_{module_id}_{file.filename}"
                    file_path = os.path.join('uploads', filename)
                    os.makedirs('uploads', exist_ok=True)
                    file.save(file_path)

        # Parse element properties
        try:
            element_properties = json.loads(element_properties_json)
        except json.JSONDecodeError:
            if conn:
                return_db_connection(conn)
            return jsonify({'error': 'Invalid element_properties JSON'}), 400

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO lessons (course_id, module_id, lesson, description, file_path, element_properties, content_type, order_index)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            course_id,
            module_id,
            lesson_title,
            form_data.get('description', ''),
            file_path,
            json.dumps(element_properties),
            content_type,
            order_index
        ))
        lesson_id = cursor.lastrowid
        conn.commit()
    except Exception as e:
        if conn:
            return_db_connection(conn)
        return jsonify({'error': f'Failed to create lesson: {str(e)}'}), 500
    finally:
        if conn:
            return_db_connection(conn)

    return jsonify({'message': 'Lesson created successfully', 'lesson_id': lesson_id}), 201

@teacher_api_bp.route('/courses/<int:course_id>/lessons', methods=['GET'])
def api_teacher_get_lessons_in_course(course_id):
    if not session.get('teacher_logged_in'):
        return jsonify({'error': 'Not authorized'}), 401

    conn = None
    try:
        conn = get_db_connection()
        # Verify course exists
        course = conn.execute('SELECT id FROM courses WHERE id = ?', (course_id,)).fetchone()
        if not course:
            if conn:
                return_db_connection(conn)
            return jsonify({'error': 'Course not found'}), 404

        lessons_data = conn.execute('''
            SELECT l.id, l.lesson, l.description, l.content_type, l.file_path, 
                   l.element_properties, l.order_index, l.uploaded_at,
                   m.name as module_name
            FROM lessons l
            JOIN modules m ON l.module_id = m.id
            WHERE l.course_id = ?
            ORDER BY m.order_index, l.order_index
        ''', (course_id,)).fetchall()
    except Exception as e:
        if conn:
            return_db_connection(conn)
        return jsonify({'error': f'DB error: {str(e)}'}), 500
    finally:
        if conn:
            return_db_connection(conn)

    lessons = []
    for lesson_row in lessons_data:
        lesson_dict = dict(lesson_row)
        try:
            lesson_dict['element_properties'] = json.loads(lesson_row['element_properties']) if lesson_row['element_properties'] else {}
        except:
            lesson_dict['element_properties'] = {}
        lessons.append(lesson_dict)

    return jsonify(lessons)

@teacher_api_bp.route('/lessons/<int:lesson_id>', methods=['PUT'])
def api_teacher_update_lesson(lesson_id):
    if not session.get('teacher_logged_in'):
        return jsonify({'error': 'Not authorized'}), 401

    conn = None
    try:
        conn = get_db_connection()
        # Verify lesson exists
        existing_lesson = conn.execute('SELECT id, course_id, module_id FROM lessons WHERE id = ?', (lesson_id,)).fetchone()
        if not existing_lesson:
            if conn:
                return_db_connection(conn)
            return jsonify({'error': 'Lesson not found'}), 404

        course_id = existing_lesson['course_id']
        form_data = request.form

        updates = []
        params = []

        if 'lesson_title' in form_data:
            updates.append("lesson = ?")
            params.append(form_data['lesson_title'])

        if 'description' in form_data:
            updates.append("description = ?")
            params.append(form_data['description'])

        if 'content_type' in form_data:
            updates.append("content_type = ?")
            params.append(form_data['content_type'])

        if 'order_index' in form_data:
            try:
                order_index = int(form_data['order_index'])
                updates.append("order_index = ?")
                params.append(order_index)
            except ValueError:
                if conn:
                    return_db_connection(conn)
                return jsonify({'error': 'order_index must be an integer'}), 400

        if 'element_properties' in form_data:
            try:
                element_properties = json.loads(form_data['element_properties'])
                updates.append("element_properties = ?")
                params.append(json.dumps(element_properties))
            except json.JSONDecodeError:
                if conn:
                    return_db_connection(conn)
                return jsonify({'error': 'Invalid element_properties JSON'}), 400

        # Handle file upload if present
        if 'file' in request.files:
            file = request.files['file']
            if file.filename != '':
                if allowed_file(file.filename):
                    # Save file with course_id/module_id prefix
                    filename = f"{course_id}_{existing_lesson['module_id']}_{file.filename}"
                    file_path = os.path.join('uploads', filename)
                    os.makedirs('uploads', exist_ok=True)
                    file.save(file_path)
                    updates.append("file_path = ?")
                    params.append(file_path)

        if not updates:
            if conn:
                return_db_connection(conn)
            return jsonify({'message': 'No fields to update'}), 200

        params.append(lesson_id)
        cursor = conn.cursor()
        cursor.execute(f"UPDATE lessons SET {', '.join(updates)} WHERE id = ?", tuple(params))
        updated_rows = cursor.rowcount
        conn.commit()
    except Exception as e:
        if conn:
            return_db_connection(conn)
        return jsonify({'error': f'DB error: {str(e)}'}), 500
    finally:
        if conn:
            return_db_connection(conn)

    return jsonify({'message': 'Lesson updated'}) if updated_rows > 0 else jsonify({'error': 'Lesson not found or no change'}), 404

@teacher_api_bp.route('/lessons/<int:lesson_id>', methods=['DELETE'])
def api_teacher_delete_lesson(lesson_id):
    if not session.get('teacher_logged_in'):
        return jsonify({'error': 'Not authorized'}), 401

    conn = None
    try:
        conn = get_db_connection()
        # Verify lesson exists
        existing_lesson = conn.execute('SELECT file_path FROM lessons WHERE id = ?', (lesson_id,)).fetchone()
        if not existing_lesson:
            if conn:
                return_db_connection(conn)
            return jsonify({'error': 'Lesson not found'}), 404

        # Delete file if exists
        if existing_lesson['file_path']:
            try:
                os.remove(existing_lesson['file_path'])
            except OSError:
                pass  # File might not exist

        cursor = conn.cursor()
        cursor.execute("DELETE FROM lessons WHERE id = ?", (lesson_id,))
        deleted_rows = cursor.rowcount
        conn.commit()
    except Exception as e:
        if conn:
            return_db_connection(conn)
        return jsonify({'error': f'DB error: {str(e)}'}), 500
    finally:
        if conn:
            return_db_connection(conn)

    return jsonify({'message': 'Lesson deleted'}) if deleted_rows > 0 else jsonify({'error': 'Lesson not found'}), 404

# --- File handling functions ---
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv', 'pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'txt', 'jpg', 'jpeg', 'png', 'gif', 'svg', 'zip', 'rar', '7z', 'mp3', 'wav', 'aac', 'ogg'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS