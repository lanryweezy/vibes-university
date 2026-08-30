from flask import Blueprint, render_template, render_template_string, redirect, url_for, session, request, jsonify
import json
import sqlite3
import markdown
import re
import html
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

    return render_template('student_courses.html',
                           enrollment=enrollment,
                           modules=modules,
                           lessons=lessons,
                           progress_lookup=progress_lookup,
                           get_file_icon=get_file_icon,
                           course_details=course_details,
                           completed_count_for_this_course=completed_count_for_this_course,
                           total_lessons_for_this_course=total_lessons_for_this_course,
                           overall_progress_percent=overall_progress_percent)

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
        lesson_render_content = f'<div class="markdown-body">{render_markdown_content(md_content if md_content else "No text content provided.")}</div>'
    elif content_type == 'video':
        video_url_prop = element_props.get('url')
        file_path = lesson.get('file_path')
        if video_url_prop and video_url_prop.strip():
             if "youtube.com/watch?v=" in video_url_prop or "youtu.be/" in video_url_prop:
                video_id = video_url_prop.split("v=")[-1].split("&")[0].split("youtu.be/")[-1].split("?")[0]
                lesson_render_content = f'''<div class="video-wrapper"><iframe src="https://www.youtube.com/embed/{video_id}" allowfullscreen></iframe></div>'''
             else: lesson_render_content = f'''<div class="video-wrapper"><video controls><source src="{video_url_prop}">Not supported.</video></div>'''
        elif file_path:
            file_url = url_for('static', filename=file_path.split('static/')[-1])
            lesson_render_content = f'''<div class="video-wrapper"><video controls><source src="{file_url}" type="video/{file_path.split('.')[-1].lower()}">Not supported.</video></div>'''
        else: lesson_render_content = '<p>Video content not available.</p>'
    elif content_type == 'quiz':
        quiz_question = html.escape(str(element_props.get('question', 'N/A')))
        options_list = element_props.get('options', [])
        if not isinstance(options_list, list): options_list = []
        options_html = "".join([f"<div class='quiz-option' data-index='{i}'>{html.escape(str(opt))}</div>" for i, opt in enumerate(options_list)])
        lesson_render_content = f'''
            <div class='quiz-container'>
                <h3 style="margin-bottom: 24px;">{quiz_question}</h3>
                <div id="quiz-options-list-{lesson['id']}">{options_html}</div>
                <button onclick='submitStudentQuiz({lesson['id']})' class="download-btn" style="border:none; cursor:pointer; width: 100%; justify-content: center;">Verify Mastery <i class="fas fa-check-circle" style="margin-left: 8px;"></i></button>
                <div id="quiz-feedback-{lesson['id']}"></div>
            </div>'''
    elif content_type == 'download' and lesson.get('file_path'):
        file_url = url_for('static', filename=lesson['file_path'].split('static/')[-1])
        filename = html.escape(lesson['file_path'].split('/')[-1])
        lesson_render_content = f'''<div class="download-section"><h3>{get_file_icon(filename)} {filename}</h3><p style="color: var(--text-muted);">Ready to download and implement.</p><a href="{file_url}" class="download-btn" download><i class="fas fa-cloud-download-alt"></i> Download Material</a></div>'''
    elif lesson.get('file_path'):
         file_url = url_for('static', filename=lesson['file_path'].split('static/')[-1])
         filename = html.escape(lesson['file_path'].split('/')[-1])
         if filename.split('.')[-1].lower() in ['jpg','png','gif','svg']: html_content = f"<img src='{file_url}' style='max-width:100%; border-radius: 20px;'>"
         else: html_content = f"<div class='download-section'><a href='{file_url}' download class='download-btn'><i class='fas fa-file-download'></i> Download {filename}</a></div>"
         lesson_render_content = html_content

    return render_template('student_lesson.html',
                           lesson=lesson,
                           enrollment=enrollment,
                           next_l=next_l,
                           prev_l=prev_l,
                           lesson_render_content=lesson_render_content)
