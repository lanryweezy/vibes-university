from flask import Blueprint, render_template, render_template_string, redirect, url_for, session, request, jsonify
import json
import sqlite3
import markdown
import re
from utils.db_utils import get_db_connection, return_db_connection
from utils.logging_utils import db_logger, log_error

student_content_bp = Blueprint('student_content_bp', __name__)

def get_file_icon(filename):
    """Get appropriate icon for file type"""
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    icons = {
        'mp4': '🎥', 'avi': '🎥', 'mov': '🎥', 'wmv': '🎥', 'flv': '🎥', 'webm': '🎥', 'mkv': '🎥',
        'pdf': '📄', 'doc': '📝', 'docx': '📝', 'ppt': '📊', 'pptx': '📊', 'xls': '📊', 'xlsx': '📊', 'txt': '📄',
        'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️', 'gif': '🖼️', 'svg': '🖼️',
        'zip': '📦', 'rar': '📦', '7z': '📦',
        'mp3': '🎵', 'wav': '🎵', 'aac': '🎵', 'ogg': '🎵'
    }
    return icons.get(ext, '📎')

def render_markdown_content(content):
    """Render markdown to HTML"""
    return markdown.markdown(content, extensions=['fenced_code', 'tables'])

@student_content_bp.route('/courses')
def student_courses():
    enrollment = session.get('enrollment')
    if not enrollment:
        return redirect(url_for('main_bp.pay'))

    conn = None
    try:
        conn = get_db_connection()
        target_course_name = enrollment['course_type']
        course_details = conn.execute('SELECT id FROM courses WHERE name = ?', (target_course_name,)).fetchone()

        lessons = []
        modules = {}

        if course_details:
            target_course_id = course_details['id']
            lessons_data = conn.execute('''
                SELECT l.id, l.course_id, l.module_id, m.name as module_name, l.lesson, l.description, l.file_path, l.content_type, l.element_properties,
                       COALESCE(l.order_index, 1) as order_index
                FROM lessons l JOIN modules m ON l.module_id = m.id
                WHERE l.course_id = ?
                ORDER BY m.order_index, l.order_index, l.lesson
            ''', (target_course_id,)).fetchall()

            for lesson_row in lessons_data:
                lesson_dict = dict(lesson_row)
                try:
                    lesson_dict['element_properties'] = json.loads(lesson_row['element_properties']) if lesson_row['element_properties'] else {}
                except (json.JSONDecodeError, TypeError):
                    lesson_dict['element_properties'] = {}
                lessons.append(lesson_dict)

                module_name_from_join = lesson_dict['module_name']
                if module_name_from_join not in modules:
                    modules[module_name_from_join] = []
                modules[module_name_from_join].append(lesson_dict)

        progress_data = conn.execute("SELECT course_id, lesson_id, completed FROM course_progress WHERE user_id = ?", (enrollment['user_id'],)).fetchall()
        progress_lookup = {}
        for p_row in progress_data:
            key = f"{p_row['course_id']}_{p_row['lesson_id']}"
            progress_lookup[key] = p_row['completed']
    except Exception as e:
        log_error(db_logger, "Failed to retrieve student courses data", error=str(e))
        return "Error loading courses", 500
    finally:
        if conn:
            return_db_connection(conn)

    completed_count_for_this_course = 0
    if course_details:
        for lesson_item in lessons:
            progress_key = f"{course_details['id']}_{lesson_item['id']}"
            if progress_lookup.get(progress_key):
                completed_count_for_this_course +=1

    total_lessons_for_this_course = len(lessons)
    overall_progress_percent = int(completed_count_for_this_course / total_lessons_for_this_course * 100) if total_lessons_for_this_course > 0 else 0

    return render_template_string('''
    <html><head><title>My Courses - Vibes University</title>
    <style>body{font-family:Arial,sans-serif;background:#111;color:#fff;margin:0;padding:20px;line-height:1.6;}.header{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;}.welcome{color:#ff6b35;font-size:24px;margin-bottom:10px;}.course-info{color:#ccc;}.modules{display:grid;gap:20px;}.module-card{background:#222;border-radius:10px;padding:20px;border-left:4px solid #ff6b35;}.module-title{color:#ff6b35;font-size:20px;margin-bottom:15px;}.lessons{display:grid;gap:10px;}.lesson-item{background:#333;padding:15px;border-radius:8px;display:flex;justify-content:space-between;align-items:center;transition:all .3s;}.lesson-item:hover{background:#444;transform:translateX(5px);}.lesson-info{flex:1;}.lesson-title{color:#fff;font-weight:bold;margin-bottom:5px;}.lesson-desc{color:#ccc;font-size:14px;}.lesson-status{padding:5px 10px;border-radius:15px;font-size:12px;font-weight:bold;margin-left:15px;}.completed{background:#4CAF50;color:#fff;}.pending{background:#ff9800;color:#fff;}.file-icon{margin-right:8px;}.nav-bar{background:#222;padding:15px;border-radius:8px;margin-bottom:20px;}.nav-bar a{color:#ff6b35;text-decoration:none;margin-right:20px;}.progress-bar{background:#333;height:8px;border-radius:4px;margin:10px 0;overflow:hidden;}.progress-fill{background:linear-gradient(90deg,#ff6b35,#ff8c42);height:100%;transition:width .3s;}</style></head>
    <body><div class="nav-bar"><a href="{{url_for('main_bp.dashboard')}}">← Dashboard</a><a href="{{url_for('student_content_bp.student_courses')}}">My Courses</a><a href="{{url_for('main_bp.logout')}}">Logout</a></div>
    <div class="header"><div class="welcome">Welcome back, {{enrollment['full_name']}}!</div>
    <div class="course-info">You're enrolled in: <strong>{{enrollment['course_type']|title}} Course</strong></div>
    <div class="progress-bar"><div class="progress-fill" style="width: {{overall_progress_percent}}%"></div></div>
    <div style="color:#ccc;font-size:14px;">{{completed_count_for_this_course}} of {{total_lessons_for_this_course}} lessons completed</div></div>
    <div class="modules">
    {% for module_name, module_lessons in modules.items() %}<div class="module-card"><div class="module-title">{{module_name}}</div><div class="lessons">
    {% for lesson_item in module_lessons %}
    {% set lesson_progress_key = (course_details.id if course_details else '') ~ '_' ~ lesson_item.id|string %}
    {% set is_completed = progress_lookup.get(lesson_progress_key, False) %}<div class="lesson-item"><div class="lesson-info">
    <div class="lesson-title">{{get_file_icon((lesson_item['file_path'] or '').split('/')[-1])}} {{lesson_item['lesson']}}</div>
    {% if lesson_item['description'] and lesson_item['content_type'] not in ['text', 'markdown']%}<div class="lesson-desc">{{lesson_item['description']}}</div>{% endif %}</div>
    <div class="lesson-status {{'completed' if is_completed else 'pending'}}">{% if is_completed %}✅ Completed{% else %}<a href="{{url_for('student_content_bp.view_lesson',lesson_id=lesson_item['id'])}}" style="color:inherit;text-decoration:none;">▶️ Start Lesson</a>{% endif %}</div></div>{% endfor %}</div></div>{% endfor %}</div>
    {% if not modules %}<div style="text-align:center;padding:60px;color:#ccc;"><h3>No lessons available yet</h3><p>Your course content is being prepared. Check back soon!</p></div>{% endif %}</body></html>
    ''', enrollment=enrollment, modules=modules, lessons=lessons,
         progress_lookup=progress_lookup, get_file_icon=get_file_icon, course_details=course_details, completed_count_for_this_course=completed_count_for_this_course, total_lessons_for_this_course=total_lessons_for_this_course, overall_progress_percent=overall_progress_percent)

@student_content_bp.route('/lesson/<int:lesson_id>')
def view_lesson(lesson_id):
    enrollment = session.get('enrollment')
    if not enrollment: return redirect(url_for('main_bp.pay'))

    conn = None
    try:
        conn = get_db_connection()
        lesson_data_row = conn.execute("SELECT l.*, m.name as module_name, c.name as course_name FROM lessons l JOIN modules m ON l.module_id = m.id JOIN courses c ON l.course_id = c.id WHERE l.id = ?", (lesson_id,)).fetchone()

        if not lesson_data_row:
            return "Lesson not found", 404

        lesson = dict(lesson_data_row)
        try:
            lesson['element_properties'] = json.loads(lesson_data_row['element_properties']) if lesson_data_row['element_properties'] else {}
        except (json.JSONDecodeError, TypeError):
            lesson['element_properties'] = {}

        enrolled_course_name_from_session = enrollment['course_type']
        enrolled_course_details = conn.execute('SELECT id FROM courses WHERE name = ?', (enrolled_course_name_from_session,)).fetchone()

        if not enrolled_course_details or lesson['course_id'] != enrolled_course_details['id']:
            return "Access denied to this lesson.", 403

        all_lessons_raw = conn.execute("SELECT id, lesson, module_id, COALESCE(order_index, 1) as order_index FROM lessons WHERE course_id = ? ORDER BY module_id, order_index, lesson", (lesson['course_id'],)).fetchall()
        all_lessons = [dict(l) for l in all_lessons_raw]
        current_index = next((i for i, l_item in enumerate(all_lessons) if l_item['id'] == lesson_id), None)
        next_l = all_lessons[current_index + 1] if current_index is not None and current_index + 1 < len(all_lessons) else None
        prev_l = all_lessons[current_index - 1] if current_index is not None and current_index > 0 else None
    except Exception as e:
        log_error(db_logger, "Failed to retrieve lesson data", error=str(e))
        return "Error loading lesson", 500
    finally:
        if conn:
            return_db_connection(conn)

    content_type = lesson.get('content_type', 'file')
    element_props = lesson.get('element_properties', {})
    lesson_render_content = '<p>No content available for this lesson.</p>'

    if content_type == 'text' or content_type == 'markdown':
        md_content = element_props.get('markdown_content', lesson.get('description', ''))
        lesson_render_content = render_markdown_content(md_content if md_content else 'No text content provided.')
    elif content_type == 'video':
        video_url_prop = element_props.get('url')
        file_path = lesson.get('file_path')
        if video_url_prop and video_url_prop.strip():
             if "youtube.com/watch?v=" in video_url_prop or "youtu.be/" in video_url_prop:
                video_id = video_url_prop.split("v=")[-1].split("&")[0].split("youtu.be/")[-1].split("?")[0]
                lesson_render_content = f'''<div style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%;"><iframe src="https://www.youtube.com/embed/{video_id}" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: 0;" allowfullscreen></iframe></div>'''
             else: lesson_render_content = f'''<div><video controls width="100%"><source src="{video_url_prop}">Not supported.</video></div>'''
        elif file_path:
            file_url = url_for('static', filename=file_path.split('static/')[-1])
            lesson_render_content = f'''<div><video controls width="100%"><source src="{file_url}" type="video/{file_path.split('.')[-1].lower()}">Not supported.</video></div>'''
        else: lesson_render_content = '<p>Video content not available.</p>'
    elif content_type == 'quiz':
        quiz_question = element_props.get('question', 'N/A')
        options_list = element_props.get('options', [])
        if not isinstance(options_list, list): options_list = []
        options_html = "".join([f"<div class='quiz-option-student' data-index='{i}' style='padding:8px; margin:5px 0; border:1px solid #555; border-radius:4px; cursor:pointer;'>{opt}</div>" for i, opt in enumerate(options_list)])
        lesson_render_content = f'''
            <div class='quiz-container' id="quiz-container-{lesson.id}">
                <h4>{quiz_question}</h4>
                <div id="quiz-options-list-{lesson.id}">{options_html}</div>
                <button onclick='submitStudentQuiz({lesson.id})' style='margin-top:10px; padding:8px 15px; background:#ff6b35; border:none; color:white; border-radius:4px;'>Submit Answer</button>
                <div id="quiz-feedback-{lesson.id}" style="margin-top:10px;"></div>
            </div>'''
    elif content_type == 'download' and lesson.get('file_path'):
        file_url = url_for('static', filename=lesson['file_path'].split('static/')[-1])
        filename = lesson['file_path'].split('/')[-1]
        lesson_render_content = f'''<div class="file-download"><h3>{get_file_icon(filename)} {filename}</h3><a href="{file_url}" class="download-btn" download>Download File</a></div>'''
    elif lesson.get('file_path'):
         file_url = url_for('static', filename=lesson['file_path'].split('static/')[-1])
         filename = lesson['file_path'].split('/')[-1]
         if filename.split('.')[-1].lower() in ['jpg','png','gif','svg']: html_content = f"<img src='{file_url}' style='max-width:100%;'>"
         else: html_content = f"<a href='{file_url}' download class='download-btn'>Download {filename}</a>"
         lesson_render_content = html_content

    return render_template_string('''
    <html><head><title>{{lesson['lesson']}} - Vibes University</title>
    <style>body{font-family:Arial,sans-serif;background:#111;color:#fff;margin:0;padding:20px;}.header{background:#222;padding:20px;border-radius:10px;margin-bottom:30px;}.lesson-title{color:#ff6b35;font-size:24px;margin-bottom:10px;}.lesson-meta{color:#ccc;margin-bottom:20px;}.content{background:#222;border-radius:10px;padding:30px;margin-bottom:30px;}.video-container iframe,.video-container video{width:100%;border-radius:8px;}.file-download{background:#333;padding:20px;border-radius:8px;text-align:center;border:2px dashed #ff6b35;}.download-btn{background:#ff6b35;color:#fff;padding:15px 30px;border:none;border-radius:8px;font-size:16px;font-weight:bold;text-decoration:none;display:inline-block;margin-top:10px;}.navigation{display:flex;justify-content:space-between;margin-top:30px;}.nav-btn{background:#333;color:#fff;padding:12px 20px;border:none;border-radius:8px;text-decoration:none;}.nav-btn:disabled{background:#666;}.back-link{color:#ff6b35;text-decoration:none;margin-bottom:20px;display:inline-block;}.quiz-option-student.selected{background-color:rgba(255,107,53,0.3); border-color:#ff6b35;}</style></head>
    <body><a href="{{url_for('student_content_bp.student_courses')}}" class="back-link">← Back to Courses</a>
    <div class="header"><div class="lesson-title">{{lesson['lesson']}}</div><div class="lesson-meta">Course: {{lesson.course_name|title}} | Module: {{lesson.module_name|title}} {% if lesson['order_index'] %}| Order: {{lesson['order_index']}}{% endif %}</div></div>
    <div class="content">{{lesson_render_content|safe}}</div>
    <div class="navigation">
    {% if prev_l %}<a href="{{url_for('student_content_bp.view_lesson',lesson_id=prev_l.id)}}" class="nav-btn">← Previous: {{prev_l.lesson}}</a>{% else %}<button class="nav-btn" disabled>← Previous</button>{% endif %}
    <a href="{{url_for('student_content_bp.student_courses')}}" class="nav-btn">Back to Courses</a>
    {% if next_l %}<a href="{{url_for('student_content_bp.view_lesson',lesson_id=next_l.id)}}" class="nav-btn">Next: {{next_l.lesson}} →</a>{% else %}<button class="nav-btn" disabled>Next →</button>{% endif %}
    </div><script>
        function markCompleted() {
            fetch('/api/mark-completed', { method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ user_id: {{enrollment['user_id']}}, course_id: {{lesson['course_id']}}, lesson_id: {{lesson['id']}} })
            }).then(r => r.json()).then(d => { if(d.success) console.log('Lesson marked completed'); });
        }
        document.querySelectorAll('video').forEach(v => v.addEventListener('ended', markCompleted));
        document.querySelectorAll('.download-btn[download]').forEach(b => b.addEventListener('click', markCompleted));
        {% if lesson['content_type'] == 'markdown' or lesson['content_type'] == 'text' %} setTimeout(markCompleted, 30000); {% endif %}

        {% if lesson['content_type'] == 'quiz' %}
        document.querySelectorAll('#quiz-options-list-{{lesson.id}} .quiz-option-student').forEach(opt => {
            opt.addEventListener('click', function() {
                document.querySelectorAll('#quiz-options-list-{{lesson.id}} .quiz-option-student').forEach(o => o.classList.remove('selected'));
                this.classList.add('selected');
            });
        });
        function submitStudentQuiz(lessonId) {
            const optionsContainer = document.getElementById('quiz-options-list-' + lessonId);
            if (!optionsContainer) return;
            const options = optionsContainer.querySelectorAll('.quiz-option-student');
            let selectedAnswerIndex = -1;
            options.forEach((opt, index) => {
                if (opt.classList.contains('selected')) {
                    selectedAnswerIndex = index;
                }
                opt.style.pointerEvents = 'none';
                opt.style.opacity = '0.7';
            });
            if (selectedAnswerIndex === -1) {
                alert("Please select an answer.");
                options.forEach(opt => { opt.style.pointerEvents = 'auto'; opt.style.opacity = '1';});
                return;
            }
            fetch(`/api/student/submit-quiz/` + lessonId, {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ answer_index: selectedAnswerIndex })
            })
            .then(response => response.json())
            .then(data => {
                const feedbackEl = document.getElementById('quiz-feedback-' + lessonId);
                if (feedbackEl) {
                    if (data.success) {
                        feedbackEl.textContent = data.is_correct ? "Correct!" : "Incorrect.";
                        feedbackEl.style.color = data.is_correct ? 'lightgreen' : 'salmon';
                        if (data.is_correct) markCompleted();
                    } else {
                        feedbackEl.textContent = "Error: " + data.error;
                        feedbackEl.style.color = 'salmon';
                        options.forEach(opt => { opt.style.pointerEvents = 'auto'; opt.style.opacity = '1';});
                    }
                }
            }).catch(error => {
                console.error("Quiz submission error:", error);
                const feedbackEl = document.getElementById('quiz-feedback-' + lessonId);
                if (feedbackEl) feedbackEl.textContent = "Network error.";
                options.forEach(opt => { opt.style.pointerEvents = 'auto'; opt.style.opacity = '1';});
            });
        }
        {% endif %}
    </script></body></html>
    ''', lesson=lesson, enrollment=enrollment, next_l=next_l, prev_l=prev_l, lesson_render_content=lesson_render_content, get_file_icon=get_file_icon)
