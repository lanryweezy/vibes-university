from werkzeug.security import generate_password_hash
from utils.db_utils import get_db_connection

conn = get_db_connection()
password_hash = generate_password_hash("password123")
conn.execute("INSERT INTO users (full_name, email, phone, password_hash, role) VALUES ('Test Student', 'student@example.com', '1234567890', ?, 'student')", (password_hash,))
conn.commit()
conn.close()
print("Student user seeded successfully.")
