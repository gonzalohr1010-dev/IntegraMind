"""
Database configuration module
Handles connection to PostgreSQL (Render) or SQLite (fallback)
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

def get_db_connection():
    """Get database connection (PostgreSQL or SQLite fallback)"""
    if DATABASE_URL and DATABASE_URL.startswith('postgresql'):
        try:
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
            logger.info("✅ Connected to PostgreSQL")
            return conn, 'postgresql'
        except Exception as e:
            logger.error(f"❌ PostgreSQL connection failed: {e}")
            logger.warning("⚠️ Falling back to SQLite")
            return get_sqlite_connection()
    else:
        return get_sqlite_connection()

def get_sqlite_connection():
    """Fallback to SQLite"""
    import sqlite3
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(BASE_DIR, 'users.sqlite')
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    logger.info("✅ Connected to SQLite (fallback)")
    return conn, 'sqlite'

def ensure_tables():
    """Create tables if they don't exist"""
    conn, db_type = get_db_connection()
    try:
        cur = conn.cursor()
        
        if db_type == 'postgresql':
            # PostgreSQL syntax
            cur.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    company VARCHAR(255),
                    role VARCHAR(255),
                    interest VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    report_generated INTEGER DEFAULT 0,
                    report_sent_at TIMESTAMP,
                    report_file_path TEXT
                )
            """)
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    user_id VARCHAR(255) PRIMARY KEY,
                    profile_json TEXT
                )
            """)
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255),
                    doc_id VARCHAR(255),
                    helpful INTEGER,
                    ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS qa_log (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255),
                    question TEXT,
                    answer TEXT,
                    source VARCHAR(255),
                    url TEXT,
                    learned INTEGER DEFAULT 0,
                    ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255),
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    conversation_id INTEGER REFERENCES conversations(id),
                    role VARCHAR(50),
                    content TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS favorites (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255),
                    message_id INTEGER REFERENCES messages(id),
                    category VARCHAR(255),
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
        else:
            # SQLite syntax (existing code)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    company TEXT,
                    role TEXT,
                    interest TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    report_generated INTEGER DEFAULT 0,
                    report_sent_at DATETIME,
                    report_file_path TEXT
                )
            """)
            
            cur.execute("CREATE TABLE IF NOT EXISTS profiles (user_id TEXT PRIMARY KEY, profile_json TEXT)")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    doc_id TEXT,
                    helpful INTEGER,
                    ts DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS qa_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    question TEXT,
                    answer TEXT,
                    source TEXT,
                    url TEXT,
                    learned INTEGER DEFAULT 0,
                    ts DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    title TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER,
                    role TEXT,
                    content TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                )
            """)
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    message_id INTEGER,
                    category TEXT,
                    notes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (message_id) REFERENCES messages(id)
                )
            """)
        
        conn.commit()
        logger.info(f"✅ Tables created/verified in {db_type}")
        
    except Exception as e:
        logger.error(f"❌ Error creating tables: {e}")
        conn.rollback()
    finally:
        conn.close()
# PostgreSQL migration - 2026-02-06
