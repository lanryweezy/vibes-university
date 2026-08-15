## 2026-08-15 - Inconsistent Authentication Checks
**Learning:** The application had inconsistent implementation of authentication checks. While auth decorators (`@require_admin_auth`, `@require_teacher_auth`) existed and were used in a few creation routes, the majority of the CRUD API routes in `admin_api_routes.py` and `teacher_api_routes.py` still used manual session checks (`if not session.get('..._logged_in')`).
**Action:** Always search for consistent application of cross-cutting concerns like authentication decorators when exploring Flask application blueprints in this repository.
