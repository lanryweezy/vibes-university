from flask import Blueprint, jsonify
from utils.db_utils import get_db_connection, return_db_connection
from utils.logging_utils import db_logger, log_error
import json

public_data_api_bp = Blueprint('public_data_api_bp', __name__, url_prefix='/api')

@public_data_api_bp.route('/courses', methods=['GET'])
def get_courses():
    conn = None
    try:
        conn = get_db_connection()
        courses_data = conn.execute("SELECT id, name, description, course_settings FROM courses ORDER BY created_at DESC").fetchall()

        output_courses = []
        for course_row in courses_data:
            course_dict = dict(course_row)
            try:
                course_dict['course_settings'] = json.loads(course_row['course_settings']) if course_row['course_settings'] else {}
            except:
                course_dict['course_settings'] = course_row['course_settings'] if course_row['course_settings'] else {}
            output_courses.append(course_dict)
        return jsonify({'courses': output_courses})
    except Exception as e:
        log_error(db_logger, "Failed to retrieve courses", error=str(e))
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            return_db_connection(conn)

@public_data_api_bp.route('/stats', methods=['GET'])
def get_stats():
    conn = None
    try:
        conn = get_db_connection()
        user_count = conn.execute('SELECT COUNT(*) as count FROM users').fetchone()['count']
        enrollment_count = conn.execute("SELECT COUNT(*) as count FROM enrollments WHERE payment_status = 'completed'").fetchone()['count']
        total_revenue = conn.execute("SELECT SUM(price) as total FROM enrollments WHERE payment_status = 'completed'").fetchone()['total'] or 0
        return jsonify({
            'users': user_count,
            'enrollments': enrollment_count,
            'revenue': total_revenue,
            'success_rate': '97%',
            'average_income': '₦1,200,000'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            return_db_connection(conn)

@public_data_api_bp.route('/testimonials', methods=['GET'])
def get_testimonials():
    testimonials = [
        {'name': 'Chioma Okafor', 'age': 24, 'location': 'Lagos', 'income': '₦800,000/month', 'story': 'I was broke 3 months ago...', 'course': 'AI Marketing Mastery', 'timeframe': '3 months'},
        {'name': 'Emeka Nwankwo', 'age': 22, 'location': 'Abuja', 'income': '₦2,500,000/month', 'story': 'Quit university...', 'course': 'AI Coding & Development', 'timeframe': '4 months'},
        {'name': 'Fatima Abdullahi', 'age': 26, 'location': 'Kano', 'income': '₦1,200,000/month', 'story': 'Financial freedom at 26...', 'course': 'AI Content Creation', 'timeframe': '5 months'},
        {'name': 'David Ogundimu', 'age': 23, 'location': 'Port Harcourt', 'income': '₦3,000,000/month', 'story': 'From ₦0 to ₦3M monthly...', 'course': 'AI E-commerce Automation', 'timeframe': '4 months'}
    ]
    return jsonify({'testimonials': testimonials})
