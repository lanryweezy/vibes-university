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
        return jsonify({'success': False, 'error': 'Not authenticated or not enrolled'}), 401

    data = request.get_json()
    if not data or 'answer_index' not in data:
        return jsonify({'success': False, 'error': 'Missing answer_index'}), 400

    conn = None
    try:
        conn = get_db_connection()
        lesson = conn.execute('SELECT id, course_id, element_properties FROM lessons WHERE id = ? AND content_type = ?', (lesson_id, 'quiz')).fetchone()
        if not lesson:
            return jsonify({'success': False, 'error': 'Quiz lesson not found'}), 404

        # Authorization: Check if the student's enrollment matches the lesson's course
        enrolled_course_name = enrollment.get('course_type')
        if not enrolled_course_name:
            return jsonify({'success': False, 'error': 'Enrollment course type not found in session'}), 403

        course_of_lesson = conn.execute('SELECT name FROM courses WHERE id = ?', (lesson['course_id'],)).fetchone()
        if not course_of_lesson or course_of_lesson['name'] != enrolled_course_name:
            return jsonify({'success': False, 'error': 'Not authorized to submit quiz for this course'}), 403

        user_id = enrollment['user_id']

        import json
        try:
            props = json.loads(lesson['element_properties']) if lesson['element_properties'] else {}
        except:
            props = {}

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

        return jsonify({
            'success': True,
            'is_correct': is_correct,
            'score': score,
            'message': 'Quiz submitted successfully'
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
