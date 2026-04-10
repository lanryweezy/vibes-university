from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import utilities
from utils.db_utils import db_manager
from utils.security_utils import get_env_variable
from utils.security_middleware import SecurityMiddleware

# Import blueprints
from blueprints.main_routes import main_bp
from blueprints.teacher_auth_routes import teacher_auth_bp
from blueprints.teacher_courses_routes import teacher_courses_bp
from blueprints.teacher_api_routes import teacher_api_bp
from blueprints.blog_routes import blog_bp
from blueprints.student_content_routes import student_content_bp
from blueprints.student_data_api_routes import student_data_api_bp
from blueprints.profile_routes import profile_bp
from blueprints.admin_page_routes import admin_page_bp
from blueprints.public_data_api_routes import public_data_api_bp
from blueprints.admin_api_routes import admin_api_bp
from blueprints.user_auth_api_routes import user_auth_api_bp
from blueprints.payment_api_routes import payment_api_bp

app = Flask(__name__)
CORS(app)

# Initialize security middleware
security_middleware = SecurityMiddleware(app)

# Configuration
app.config['SECRET_KEY'] = get_env_variable('SECRET_KEY', 'vibes-university-secret-key')
app.secret_key = app.config['SECRET_KEY']
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'courses')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Register Blueprints
app.register_blueprint(main_bp)
app.register_blueprint(teacher_auth_bp)
app.register_blueprint(teacher_courses_bp)
app.register_blueprint(teacher_api_bp)
app.register_blueprint(blog_bp)
app.register_blueprint(student_content_bp)
app.register_blueprint(student_data_api_bp)
app.register_blueprint(admin_page_bp)
app.register_blueprint(admin_api_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(user_auth_api_bp)
app.register_blueprint(public_data_api_bp)
app.register_blueprint(payment_api_bp)

def init_db():
    db_manager.initialize_database()

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
