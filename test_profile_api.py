import unittest
import time
import random
from app import app
from utils.db_utils import db_manager

class ProfileRouteTest(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        db_manager.initialize_database()

        # Create a test user directly in DB
        with app.app_context():
            conn = db_manager.get_connection()
            cursor = conn.cursor()

            # Use completely random email to avoid ANY possibility of UNIQUE constraint failure
            unique_email = f"test_{int(time.time())}_{random.randint(1000, 9999)}@example.com"
            cursor.execute("INSERT INTO users (email, password_hash, full_name, phone) VALUES (?, 'hash', 'Test User', '123')", (unique_email,))
            self.user_id = cursor.lastrowid

            # Need an enrollment to have a valid session
            cursor.execute("INSERT INTO enrollments (user_id, course_type, price, payment_method, payment_status, payment_reference) VALUES (?, 'course', 100, 'test', 'completed', 'ref123')", (self.user_id,))
            self.enrollment_id = cursor.lastrowid

            # Get the full enrollment object for session
            self.enrollment = conn.execute("SELECT e.*, u.email, u.full_name FROM enrollments e JOIN users u ON e.user_id = u.id WHERE e.id = ?", (self.enrollment_id,)).fetchone()

            conn.commit()
            db_manager.return_connection(conn)

    def test_profile_page_loads(self):
        with self.app.session_transaction() as sess:
            sess['enrollment'] = dict(self.enrollment)

        response = self.app.get('/profile')
        self.assertEqual(response.status_code, 200)

        # Verify the UX changes are present in HTML
        html = response.data.decode()
        self.assertIn('for="full_name"', html)
        self.assertIn('autocomplete="name"', html)
        self.assertIn('type="tel"', html)

    def test_profile_update(self):
        with self.app.session_transaction() as sess:
            sess['enrollment'] = dict(self.enrollment)

        response = self.app.post('/profile', data={
            'full_name': 'Updated Name',
            'phone': '9876543210',
            'new_password': ''
        })
        self.assertEqual(response.status_code, 200)

        # Check if updated in DB
        conn = db_manager.get_connection()
        user = conn.execute("SELECT * FROM users WHERE id = ?", (self.user_id,)).fetchone()
        db_manager.return_connection(conn)

        self.assertEqual(user['full_name'], 'Updated Name')
        self.assertEqual(user['phone'], '9876543210')

if __name__ == '__main__':
    unittest.main()
