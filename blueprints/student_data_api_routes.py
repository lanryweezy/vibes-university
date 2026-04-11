from flask import Blueprint, jsonify, request, session
from utils.db_utils import get_db_connection, return_db_connection
from utils.logging_utils import app_logger, security_logger, log_info, log_error, log_warning

student_data_api_bp = Blueprint('student_data_api_bp', __name__, url_prefix='/api')

@student_data_api_bp.route('/user-progress/<int:user_id>', methods=['GET'])
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

@student_data_api_bp.route('/student/submit-quiz/<int:lesson_id>', methods=['POST'])
def submit_quiz(lesson_id):
    enrollment = session.get('enrollment')
    if not enrollment:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    data = request.get_json()
    answer_index = data.get('answer_index')

    if answer_index is None:
        return jsonify({'success': False, 'error': 'No answer provided'}), 400

    conn = None
    try:
        conn = get_db_connection()
        lesson_row = conn.execute("SELECT element_properties FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
        if not lesson_row:
            return jsonify({'success': False, 'error': 'Lesson not found'}), 404

        import json
        try:
            props = json.loads(lesson_row['element_properties']) if lesson_row['element_properties'] else {}
        except:
            props = {}

        correct_index = props.get('correct_answer_index', 0)
        is_correct = int(answer_index) == int(correct_index)

        return jsonify({
            'success': True,
            'is_correct': is_correct,
            'correct_index': correct_index
        })
    except Exception as e:
        log_error(app_logger, "Quiz submission error", error=str(e))
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            return_db_connection(conn)

@student_data_api_bp.route('/mark-completed', methods=['POST'])
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
        # Using INSERT OR REPLACE to handle duplicates gracefully
        cursor.execute("INSERT OR REPLACE INTO course_progress (user_id, course_id, lesson_id, completed, completed_at) VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)", (user_id, course_id, lesson_id))
        conn.commit()
        return jsonify({'success': True, 'message': 'Lesson marked as completed'})
    except Exception as e:
        log_error(app_logger, "Failed to mark lesson as completed", error=str(e))
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            return_db_connection(conn)
