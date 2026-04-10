from flask import Blueprint, jsonify, request, session
import sqlite3
import json
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# Import utilities
from utils.db_utils import get_db_connection, return_db_connection
from utils.logging_utils import app_logger, log_info, log_error, log_warning
from utils.security_utils import validate_email, validate_phone, sanitize_input
from utils.rate_limiter import rate_limit

user_auth_api_bp = Blueprint('user_auth_api_bp', __name__, url_prefix='/api')

@user_auth_api_bp.route('/register', methods=['POST'])
@rate_limit('auth')
def register():
    try:
        data = request.get_json()
        required_fields = ['email', 'password', 'full_name', 'phone']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400

        if not validate_email(data['email']):
            return jsonify({'error': 'Invalid email format'}), 400

        if not validate_phone(data['phone']):
            return jsonify({'error': 'Invalid phone number format'}), 400

        full_name = sanitize_input(data['full_name'])

        conn = None
        try:
            conn = get_db_connection()
            existing_user = conn.execute('SELECT id FROM users WHERE email = ?', (data['email'],)).fetchone()
            if existing_user:
                return jsonify({'error': 'User already exists'}), 400

            password_hash = generate_password_hash(data['password'])
            cursor = conn.cursor()
            cursor.execute('INSERT INTO users (email, password_hash, full_name, phone) VALUES (?, ?, ?, ?)',
                           (data['email'], password_hash, full_name, data['phone']))
            user_id = cursor.lastrowid
            conn.commit()
            log_info(app_logger, "User registered successfully", user_id=user_id, email=data['email'])
            return jsonify({'success': True, 'message': 'User registered successfully', 'user_id': user_id})
        except Exception as e:
            log_error(app_logger, "Registration failed", error=str(e))
            return jsonify({'error': str(e)}), 500
        finally:
            if conn:
                return_db_connection(conn)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@user_auth_api_bp.route('/login', methods=['POST'])
@rate_limit('auth')
def login():
    try:
        data = request.get_json()
        if not data.get('email') or not data.get('password'):
            return jsonify({'error': 'Email and password are required'}), 400

        if not validate_email(data['email']):
            return jsonify({'error': 'Invalid email format'}), 400

        conn = None
        try:
            conn = get_db_connection()
            user = conn.execute('SELECT * FROM users WHERE email = ?', (data['email'],)).fetchone()

            if not user or not check_password_hash(user['password_hash'], data['password']):
                return jsonify({'error': 'Invalid credentials'}), 401

            # Check if user has active enrollment (for session building)
            enrollment = conn.execute("SELECT e.*, u.email, u.full_name FROM enrollments e JOIN users u ON e.user_id = u.id WHERE e.user_id = ? AND e.payment_status = 'completed' LIMIT 1", (user['id'],)).fetchone()
            if enrollment:
                session['enrollment'] = dict(enrollment)

            log_info(app_logger, "User logged in successfully", user_id=user['id'], email=user['email'])
            return jsonify({
                'success': True,
                'user': {'id': user['id'], 'email': user['email'], 'full_name': user['full_name'], 'phone': user['phone']}
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            if conn:
                return_db_connection(conn)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
