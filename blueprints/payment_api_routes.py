from flask import Blueprint, jsonify, request, session
import sqlite3
import json
import os
from datetime import datetime

# Import utilities
from utils.db_utils import get_db_connection, return_db_connection
from utils.logging_utils import payment_logger, log_info, log_error, log_warning
from utils.rate_limiter import rate_limit

payment_api_bp = Blueprint('payment_api_bp', __name__, url_prefix='/api')

def initiate_paystack_payment(data, reference):
    return f"https://checkout.paystack.com/demo?reference={reference}"

def initiate_flutterwave_payment(data, reference):
    return f"https://checkout.flutterwave.com/demo?reference={reference}"

def initiate_crypto_payment(data, reference):
    return f"https://vibesuniversity.com/crypto-payment?reference={reference}"

@payment_api_bp.route('/initiate-payment', methods=['POST'])
@rate_limit('api')
def initiate_payment():
    try:
        data = request.get_json()
        required_fields = ['user_id', 'course_type', 'price', 'payment_method']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400

        payment_reference = f"VU_{data['user_id']}_{int(datetime.now().timestamp())}"

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO enrollments (user_id, course_type, price, payment_method, payment_reference) VALUES (?, ?, ?, ?, ?)',
                           (data['user_id'], data['course_type'], data['price'], data['payment_method'], payment_reference))
            enrollment_id = cursor.lastrowid
            conn.commit()
        except Exception as e:
            log_error(payment_logger, "Payment initiation db failed", error=str(e))
            return jsonify({'error': str(e)}), 500
        finally:
            if conn:
                return_db_connection(conn)

        payment_url = ""
        if data['payment_method'] == 'card':
            payment_url = initiate_paystack_payment(data, payment_reference)
        elif data['payment_method'] == 'bank':
            payment_url = initiate_flutterwave_payment(data, payment_reference)
        elif data['payment_method'] == 'crypto':
            payment_url = initiate_crypto_payment(data, payment_reference)
        else:
            return jsonify({'error': 'Invalid payment method'}), 400

        log_info(payment_logger, "Payment initiated successfully", enrollment_id=enrollment_id, payment_reference=payment_reference)
        return jsonify({'success': True, 'payment_reference': payment_reference, 'payment_url': payment_url, 'enrollment_id': enrollment_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@payment_api_bp.route('/verify-payment', methods=['POST'])
@rate_limit('api')
def verify_payment():
    try:
        data = request.get_json()
        reference = data.get('reference')
        if not reference:
            return jsonify({'error': 'Payment reference is required'}), 400

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE enrollments SET payment_status = 'completed' WHERE payment_reference = ?", (reference,))
            enrollment = conn.execute("SELECT e.*, u.email, u.full_name FROM enrollments e JOIN users u ON e.user_id = u.id WHERE e.payment_reference = ?", (reference,)).fetchone()
            conn.commit()

            if enrollment:
                session['enrollment'] = dict(enrollment)
                log_info(payment_logger, "Payment verified successfully", enrollment_id=enrollment['id'])
                return jsonify({'success': True, 'message': 'Payment verified successfully', 'enrollment': dict(enrollment)})
            else:
                return jsonify({'error': 'Enrollment not found'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            if conn:
                return_db_connection(conn)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
