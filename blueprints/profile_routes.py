from flask import Blueprint, render_template_string, redirect, url_for, session, request, jsonify
from utils.db_utils import get_db_connection, return_db_connection
from utils.logging_utils import app_logger, log_info, log_error
from utils.security_utils import sanitize_input
from werkzeug.security import generate_password_hash

profile_bp = Blueprint('profile_bp', __name__)

@profile_bp.route('/profile', methods=['GET', 'POST'])
def manage_profile():
    # Check if student or teacher is logged in
    user_id = None
    role = None
    display_name = ""

    if session.get('enrollment'):
        user_id = session['enrollment']['user_id']
        role = 'student'
        display_name = session['enrollment']['full_name']
    elif session.get('teacher_logged_in'):
        user_id = session['teacher_id']
        role = 'teacher'
        display_name = session['teacher_name']

    if not user_id:
        return redirect(url_for('main_bp.student_login'))

    message = ""
    conn = None
    try:
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

        if request.method == 'POST':
            full_name = sanitize_input(request.form.get('full_name'))
            phone = sanitize_input(request.form.get('phone'))
            new_password = request.form.get('new_password')

            cursor = conn.cursor()
            if new_password:
                password_hash = generate_password_hash(new_password)
                cursor.execute("UPDATE users SET full_name = ?, phone = ?, password_hash = ? WHERE id = ?", (full_name, phone, password_hash, user_id))
            else:
                cursor.execute("UPDATE users SET full_name = ?, phone = ? WHERE id = ?", (full_name, phone, user_id))
            conn.commit()

            # Update session
            if role == 'student':
                session['enrollment']['full_name'] = full_name
            else:
                session['teacher_name'] = full_name

            message = "Profile updated successfully!"
            user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

        return render_template_string('''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>My Profile | Vibes University</title>
            <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
            <style>
                :root { --primary: #ff6b35; --bg-dark: #0f172a; --card-bg: #1e293b; --text-main: #f8fafc; --text-muted: #94a3b8; }
                body { font-family: 'Inter', sans-serif; background: var(--bg-dark); color: var(--text-main); margin: 0; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
                .profile-card { background: var(--card-bg); padding: 48px; border-radius: 24px; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5); width: 100%; max-width: 500px; border: 1px solid rgba(255, 255, 255, 0.1); }
                h2 { color: #fff; text-align: center; margin-bottom: 32px; font-size: 2rem; }
                .form-group { margin-bottom: 24px; }
                label { display: block; margin-bottom: 8px; color: var(--text-muted); font-size: 0.85rem; font-weight: 600; text-transform: uppercase; }
                input { width: 100%; padding: 14px; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.1); background: rgba(15, 23, 42, 0.6); color: #fff; box-sizing: border-box; }
                input:focus { border-color: var(--primary); outline: none; box-shadow: 0 0 0 3px rgba(255, 107, 53, 0.3); }
                .btn { background: var(--primary); color: #fff; border: none; padding: 16px; width: 100%; border-radius: 12px; font-size: 1rem; font-weight: 700; cursor: pointer; margin-top: 16px; transition: opacity 0.3s; }
                .btn:disabled { opacity: 0.7; cursor: not-allowed; }
                .message { text-align: center; padding: 12px; border-radius: 8px; background: rgba(16, 185, 129, 0.1); color: #10b981; margin-bottom: 24px; }
                .back-link { display: block; text-align: center; margin-top: 24px; color: var(--text-muted); text-decoration: none; font-size: 0.9rem; }
            </style>
        </head>
        <body>
            <div class="profile-card">
                <h2>Account Settings</h2>
                {% if message %}<div class="message">{{ message }}</div>{% endif %}
                <form method="post" id="profile-form">
                    <div class="form-group">
                        <label for="full_name">Full Name <span style="color: #ef4444;" aria-hidden="true">*</span></label>
                        <input type="text" id="full_name" name="full_name" value="{{ user.full_name }}" required autocomplete="name">
                    </div>
                    <div class="form-group">
                        <label for="email">Email (Permanent)</label>
                        <input type="email" id="email" value="{{ user.email }}" disabled style="opacity: 0.5;" autocomplete="email">
                    </div>
                    <div class="form-group">
                        <label for="phone">Phone Number <span style="color: #ef4444;" aria-hidden="true">*</span></label>
                        <input type="tel" id="phone" name="phone" value="{{ user.phone }}" required autocomplete="tel">
                    </div>
                    <div class="form-group">
                        <label for="new_password">New Password (leave blank to keep current)</label>
                        <input type="password" id="new_password" name="new_password" placeholder="••••••••" autocomplete="new-password">
                    </div>
                    <button type="submit" class="btn" id="submit-btn">Update Profile</button>
                </form>
                <a href="{{ url_for('main_bp.dashboard') if role == 'student' else url_for('teacher_auth_bp.teacher_dashboard') }}" class="back-link">← Back to Dashboard</a>
            </div>
            <script>
                document.getElementById('profile-form').addEventListener('submit', function() {
                    const btn = document.getElementById('submit-btn');
                    btn.disabled = true;
                    btn.innerHTML = 'Updating... <i class="fas fa-spinner fa-spin" style="margin-left: 8px;"></i>';
                });
            </script>
        </body>
        </html>
        ''', user=user, message=message, role=role)
    except Exception as e:
        log_error(app_logger, "Profile error", error=str(e))
        return "Error", 500
    finally:
        if conn:
            return_db_connection(conn)
