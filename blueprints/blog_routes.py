from flask import Blueprint, render_template, abort
from utils.db_utils import get_db_connection, return_db_connection

blog_bp = Blueprint('blog_bp', __name__)

@blog_bp.route('/blogs')
def list_blogs():
    conn = None
    try:
        conn = get_db_connection()
        blogs = conn.execute('SELECT * FROM blogs ORDER BY created_at DESC').fetchall()
        return render_template('blog_list.html', blogs=blogs)
    except Exception as e:
        return str(e), 500
    finally:
        if conn:
            return_db_connection(conn)

@blog_bp.route('/blog/<slug>')
def view_blog(slug):
    conn = None
    try:
        conn = get_db_connection()
        blog = conn.execute('SELECT * FROM blogs WHERE slug = ?', (slug,)).fetchone()
        if blog is None:
            abort(404)
        return render_template('blog_post.html', blog=blog)
    except Exception as e:
        return str(e), 500
    finally:
        if conn:
            return_db_connection(conn)
