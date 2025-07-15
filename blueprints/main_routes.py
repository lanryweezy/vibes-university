from flask import Blueprint, render_template_string, redirect, url_for, session, jsonify, request
import os # For home route's file reading

# Placeholder for get_db_connection, etc. - will be resolved during refactoring
# from app import get_db_connection

main_bp = Blueprint('main_bp', __name__)

# Routes to be moved here:
# /
# /health
# /pay
# /payment/callback
# /logout (if not in admin_pages)
# /student/login (page)
# /dashboard (student dashboard page)
# /demo-payment

# Example of one route structure (actual move later)
@main_bp.route('/')
def home_placeholder():
    # Actual logic will be moved from app.py
    try:
        index_path = os.path.join(os.path.dirname(os.path.abspath(__file__)).replace('/blueprints', ''), 'index.html')
        with open(index_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return jsonify({'error': 'Platform not found'}), 404
    except Exception as e:
        return jsonify({'error': f'Error loading platform: {str(e)}'}), 500

# Need datetime for health_check
from datetime import datetime

@main_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

# Add other placeholder routes or leave them to be filled in Step 3 (Move Route Logic)

# Actual home route from app.py
@main_bp.route('/')
def home():
    """Serve the main course platform page"""
    try:
        # Use current directory instead of hardcoded Linux path
        # Adjust path since this file is in 'blueprints' subdirectory
        # os.path.abspath(__file__) is /path/to/repo/blueprints/main_routes.py
        # os.path.dirname(...) is /path/to/repo/blueprints
        # .replace(...) gives /path/to/repo
        base_dir = os.path.dirname(os.path.abspath(__file__)).replace('/blueprints', '')
        index_path = os.path.join(base_dir, 'index.html')
        with open(index_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return jsonify({'error': 'Platform not found'}), 404
    except Exception as e:
        return jsonify({'error': f'Error loading platform: {str(e)}'}), 500
