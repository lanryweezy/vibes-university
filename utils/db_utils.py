import sqlite3
import os
from contextlib import contextmanager
from utils.security_utils import get_env_variable
from threading import Lock

# Database configuration
DATABASE_PATH = get_env_variable('DATABASE_PATH', 'vibes_university.db')

class DatabaseManager:
    """Manages database connections and operations for the application with connection pooling."""
    
    def __init__(self, db_path=None, pool_size=10):
        self.db_path = db_path or DATABASE_PATH
        self.pool_size = pool_size
        self.connection_pool = []
        self.lock = Lock()
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize the connection pool with a set number of connections."""
        for _ in range(self.pool_size):
            conn = self._create_connection()
            self.connection_pool.append(conn)
    
    def _create_connection(self):
        """Create a new database connection with proper configuration."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        conn.execute('PRAGMA journal_mode=WAL')  # Enable WAL mode for better concurrency
        conn.execute('PRAGMA foreign_keys=ON')   # Enable foreign key constraints
        return conn
    
    def get_connection(self):
        """Get a database connection from the pool."""
        with self.lock:
            if self.connection_pool:
                return self.connection_pool.pop()
            else:
                # If pool is empty, create a new connection (emergency fallback)
                return self._create_connection()
    
    def return_connection(self, conn):
        """Return a connection to the pool."""
        with self.lock:
            if len(self.connection_pool) < self.pool_size and conn:
                # Reset connection state before returning to pool
                try:
                    conn.rollback()  # Rollback any pending transactions
                except:
                    pass  # Connection might be in an invalid state
                self.connection_pool.append(conn)
            elif conn:
                # If pool is full, close the connection
                try:
                    conn.close()
                except:
                    pass  # Connection might already be closed
    
    @contextmanager
    def get_db_cursor(self):
        """
        Context manager for database operations.
        Automatically handles connection acquisition and return to pool.
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            yield conn, cursor
            conn.commit()
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            raise e
        finally:
            if conn:
                self.return_connection(conn)
    
    def close_all_connections(self):
        """Close all connections in the pool."""
        with self.lock:
            for conn in self.connection_pool:
                try:
                    conn.close()
                except:
                    pass
            self.connection_pool.clear()
    
    def initialize_database(self):
        """Initialize the database with required tables."""
        conn = self._create_connection()
        cursor = conn.cursor()
        
        # Courses table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                course_settings TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                role TEXT DEFAULT 'student',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        # Teachers table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teachers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                specialization TEXT,
                bio TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')
        
        # Enrollments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS enrollments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                course_type TEXT NOT NULL,
                price INTEGER NOT NULL,
                payment_method TEXT NOT NULL,
                payment_status TEXT DEFAULT 'pending',
                payment_reference TEXT,
                enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Course progress table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS course_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                course_id INTEGER NOT NULL,
                lesson_id INTEGER NOT NULL,
                completed BOOLEAN DEFAULT 0,
                completed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE,
                FOREIGN KEY (lesson_id) REFERENCES lessons (id) ON DELETE CASCADE,
                UNIQUE (user_id, course_id, lesson_id)
            )
        ''')
        
        # Payment logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payment_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                payment_method TEXT NOT NULL,
                gateway_response TEXT,
                status TEXT NOT NULL,
                reference TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Modules table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS modules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                order_index INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (course_id) REFERENCES courses (id)
            )
        ''')

        # Lessons table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                module_id INTEGER NOT NULL,
                lesson TEXT,
                description TEXT,
                file_path TEXT,
                element_properties TEXT,
                content_type TEXT DEFAULT 'file',
                order_index INTEGER DEFAULT 1,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (course_id) REFERENCES courses (id),
                FOREIGN KEY (module_id) REFERENCES modules (id)
            )
        ''')

        # Quiz Attempts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quiz_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                lesson_id INTEGER NOT NULL,
                course_id INTEGER NOT NULL,
                attempt_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                submitted_answers TEXT,
                is_correct BOOLEAN,
                score INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (lesson_id) REFERENCES lessons (id),
                FOREIGN KEY (course_id) REFERENCES courses (id)
            )
        ''')
        
        # Announcements table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                priority TEXT DEFAULT 'normal',
                target_audience TEXT DEFAULT 'all',
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP
            )
        ''')
        
        # Add columns if they don't exist (for backward compatibility)
        try:
            cursor.execute('ALTER TABLE lessons ADD COLUMN content_type TEXT DEFAULT "file"')
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute('ALTER TABLE lessons ADD COLUMN order_index INTEGER DEFAULT 1')
        except sqlite3.OperationalError:
            pass
        
        conn.commit()
        conn.close()

# Global instance for the application
db_manager = DatabaseManager()

# Convenience function for backward compatibility
def get_db_connection():
    """Get a database connection from the pool (backward compatibility)."""
    return db_manager.get_connection()

# Context manager for database operations (recommended approach)
@contextmanager
def get_db_cursor():
    """Get a database cursor with automatic connection management (recommended)."""
    with db_manager.get_db_cursor() as (conn, cursor):
        yield conn, cursor

# Function to return connection to pool (for manual connection management)
def return_db_connection(conn):
    """Return a database connection to the pool."""
    db_manager.return_connection(conn)