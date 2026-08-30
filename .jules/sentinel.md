## 2026-08-14 - [Sentinel] Fix Path Traversal in File Uploads
**Vulnerability:** Path traversal vulnerability in both `blueprints/admin_api_routes.py` and `blueprints/teacher_api_routes.py` where user-provided `file.filename` was directly used in `os.path.join` without sanitization.
**Learning:** Raw `file.filename` objects from user requests can contain path traversal sequences (like `../../`) which could allow arbitrary files to be overwritten or written outside the intended `uploads/` directory.
**Prevention:** Always use `werkzeug.utils.secure_filename` to sanitize uploaded filenames before using them in the filesystem.
## 2026-08-16 - [Sentinel] Fix Timing Attack in Admin Login
**Vulnerability:** Timing attack vulnerability in `blueprints/admin_page_routes.py` where the admin password was verified using standard string equality (`if password == ADMIN_PASSWORD:`).
**Learning:** Standard string equality checks return `False` as soon as a character mismatch is found. An attacker can theoretically measure the time taken for the comparison to fail and guess the secret string character by character.
**Prevention:** Always use constant-time comparison functions like `secrets.compare_digest` or `hmac.compare_digest` when verifying sensitive strings such as passwords, tokens, or API keys.
## 2026-08-17 - [Sentinel] Fix Stored XSS in student content rendering
**Vulnerability:** Bypassing Jinja2 auto-escaping. HTML was constructed in the backend using `f-strings` and user input without manual sanitization, then rendered in Jinja2 templates using the `|safe` filter. This leads to Stored XSS if the inputs contained malicious scripts.
**Learning:** Jinja2's auto-escaping is ineffective if raw HTML strings containing unsanitized input are constructed on the backend and explicitly passed to the template with the `|safe` modifier.
**Prevention:** If backend strings must be rendered as raw HTML using `|safe`, manually escape all user-controlled components within the string using `html.escape` (or equivalent sanitization) before inserting them into the template variables.
## 2026-08-18 - [Sentinel] Fix Insecure Direct Object Reference (IDOR) in Teacher APIs
**Vulnerability:** IDOR vulnerability in `blueprints/teacher_api_routes.py` where APIs for retrieving and updating courses lacked a check to verify if the course actually belonged to the requesting teacher (missing `AND teacher_id = ?` in SQL query).
**Learning:** If an API takes an object ID (like `course_id`) from a parameter or URL and retrieves/modifies it without verifying ownership against the logged-in user's identity, an attacker could manipulate the ID to access or alter another user's resources.
**Prevention:** Always enforce authorization at the data access level by including the current user's ID (e.g., `teacher_id = session.get('teacher_id')`) in the database query `WHERE` clause.
## 2026-08-19 - [Sentinel] Fix IDOR in Module Update API
**Vulnerability:** Insecure Direct Object Reference (IDOR) in  where the API to update a module () failed to check if the module belonged to a course owned by the currently authenticated teacher.
**Learning:** Even if an endpoint requires authentication (e.g., ), it must independently verify authorization by ensuring that the resource being modified is owned by or accessible to the logged-in user.
**Prevention:** Always include a database query condition that enforces ownership (e.g., ) before executing any UPDATE or DELETE operations on resource identifiers received from client input.
## 2026-08-19 - [Sentinel] Fix IDOR in Module Update API
**Vulnerability:** Insecure Direct Object Reference (IDOR) in blueprints/teacher_api_routes.py where the API to update a module (PUT /modules/<module_id>) failed to check if the module belonged to a course owned by the currently authenticated teacher.
**Learning:** Even if an endpoint requires authentication (e.g., @require_teacher_auth), it must independently verify authorization by ensuring that the resource being modified is owned by or accessible to the logged-in user.
**Prevention:** Always include a database query condition that enforces ownership (e.g., AND teacher_id = ?) before executing any UPDATE or DELETE operations on resource identifiers received from client input.
