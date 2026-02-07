"""
Database configuration module (Renamed to force cache invalidation)
SOLO PostgreSQL - Sin fallback a SQLite
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
    """Get PostgreSQL database connection"""
    if not DATABASE_URL:
        # Fallback para debug: intentar os.environ directo si dotenv falla
        url = os.environ.get('DATABASE_URL')
        if not url:
            raise Exception("❌ DATABASE_URL no está configurada. Configura tu archivo .env con la URL de PostgreSQL de Render.")
        DATABASE_URL = url
    
    if not DATABASE_URL.startswith('postgresql'):
        raise Exception(f"❌ DATABASE_URL debe ser PostgreSQL, recibido: {DATABASE_URL[:20]}...")
    
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        logger.info("✅ Connected to PostgreSQL")
        return conn, 'postgresql'
    except Exception as e:
        logger.error(f"❌ PostgreSQL connection failed: {e}")
        raise

def ensure_tables():
    """Create tables if they don't exist (PostgreSQL only)"""
    conn, db_type = get_db_connection()
    try:
        cur = conn.cursor()
        
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
        
        conn.commit()
        logger.info(f"✅ Tables created/verified in PostgreSQL")
        
    except Exception as e:
        logger.error(f"❌ Error creating tables: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()
