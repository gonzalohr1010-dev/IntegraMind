"""
db.py - Database Connection Manager

Maneja conexiones a PostgreSQL y SQLite con soporte para migración gradual
"""
from __future__ import annotations

import os
import logging
from typing import Optional, Any, Dict, List
from contextlib import contextmanager
import sqlite3

logger = logging.getLogger(__name__)

# Intentar imports opcionales
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor, Json
    from psycopg2.pool import SimpleConnectionPool
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False
    logger.warning("psycopg2 not installed. PostgreSQL support disabled.")

try:
    from sqlalchemy import create_engine, MetaData, Table
    from sqlalchemy.orm import sessionmaker, Session
    from sqlalchemy.pool import QueuePool
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False
    logger.warning("SQLAlchemy not installed. ORM support disabled.")


class DatabaseConfig:
    """Configuración de base de datos desde variables de entorno"""
    
    def __init__(self):
        # Tipo de base de datos
        self.db_type = os.getenv('DATABASE_TYPE', 'sqlite').lower()
        
        # PostgreSQL config
        self.pg_host = os.getenv('POSTGRES_HOST', 'localhost')
        self.pg_port = int(os.getenv('POSTGRES_PORT', '5432'))
        self.pg_database = os.getenv('POSTGRES_DB', 'erp_ia')
        self.pg_user = os.getenv('POSTGRES_USER', 'erp_user')
        self.pg_password = os.getenv('POSTGRES_PASSWORD', 'erp_password_2024')
        
        # SQLite config (legacy)
        self.sqlite_db_path = os.getenv('SQLITE_DB_PATH', './users.sqlite')
        self.sqlite_memory_db = os.getenv('SQLITE_MEMORY_DB', './memory.db')
        self.sqlite_kg_db = os.getenv('SQLITE_KG_DB', './knowledge_graph.db')
        
        # Pool config
        self.pool_min_size = int(os.getenv('DB_POOL_MIN', '2'))
        self.pool_max_size = int(os.getenv('DB_POOL_MAX', '10'))
    
    @property
    def postgres_dsn(self) -> str:
        """PostgreSQL connection string"""
        return f"postgresql://{self.pg_user}:{self.pg_password}@{self.pg_host}:{self.pg_port}/{self.pg_database}"
    
    @property
    def use_postgres(self) -> bool:
        """Retorna True si debemos usar PostgreSQL"""
        return self.db_type == 'postgresql' and HAS_POSTGRES


class DatabaseManager:
    """Administrador de conexiones a base de datos con soporte dual SQLite/PostgreSQL"""
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig()
        self._pg_pool: Optional[SimpleConnectionPool] = None
        self._sqlalchemy_engine = None
        self._sqlalchemy_session_factory = None
        
        if self.config.use_postgres:
            self._init_postgres()
        else:
            logger.info(f"Using SQLite: {self.config.sqlite_db_path}")
    
    def _init_postgres(self):
        """Inicializar pool de conexiones PostgreSQL"""
        if not HAS_POSTGRES:
            raise RuntimeError("psycopg2 not installed. Install with: pip install psycopg2-binary")
        
        try:
            self._pg_pool = SimpleConnectionPool(
                self.config.pool_min_size,
                self.config.pool_max_size,
                host=self.config.pg_host,
                port=self.config.pg_port,
                database=self.config.pg_database,
                user=self.config.pg_user,
                password=self.config.pg_password,
                connect_timeout=10
            )
            logger.info(f"✅ PostgreSQL pool created: {self.config.pg_host}:{self.config.pg_port}/{self.config.pg_database}")
            
            # Test connection
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT version();")
                    version = cur.fetchone()[0]
                    logger.info(f"PostgreSQL version: {version}")
        
        except Exception as e:
            logger.error(f"❌ Failed to connect to PostgreSQL: {e}")
            logger.info("Falling back to SQLite")
            self.config.db_type = 'sqlite'
            self._pg_pool = None
    
    def _init_sqlalchemy(self):
        """Inicializar SQLAlchemy ORM (opcional)"""
        if not HAS_SQLALCHEMY:
            return
        
        if self.config.use_postgres:
            engine_url = self.config.postgres_dsn
        else:
            engine_url = f"sqlite:///{self.config.sqlite_db_path}"
        
        self._sqlalchemy_engine = create_engine(
            engine_url,
            poolclass=QueuePool,
            pool_size=self.config.pool_max_size,
            max_overflow=5,
            echo=False  # Set True for SQL debugging
        )
        
        self._sqlalchemy_session_factory = sessionmaker(bind=self._sqlalchemy_engine)
        logger.info(f"SQLAlchemy engine created: {engine_url}")
    
    @contextmanager
    def get_connection(self):
        """
        Context manager para obtener una conexión a la base de datos
        
        Uso:
            with db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM users")
                    results = cur.fetchall()
        """
        if self.config.use_postgres:
            conn = self._pg_pool.getconn()
            try:
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise
            finally:
                self._pg_pool.putconn(conn)
        else:
            # SQLite fallback
            conn = sqlite3.connect(self.config.sqlite_db_path)
            conn.row_factory = sqlite3.Row  # Return dict-like rows
            try:
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise
            finally:
                conn.close()
    
    @contextmanager
    def get_dict_cursor(self):
        """
        Context manager para cursor que retorna dicts (útil para JSON APIs)
        
        Uso:
            with db_manager.get_dict_cursor() as cur:
                cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                user = cur.fetchone()  # Returns dict
        """
        with self.get_connection() as conn:
            if self.config.use_postgres:
                cur = conn.cursor(cursor_factory=RealDictCursor)
            else:
                cur = conn.cursor()
            
            try:
                yield cur
            finally:
                cur.close()
    
    @contextmanager
    def get_session(self) -> Session:
        """
        Context manager for SQLAlchemy ORM session
        
        Usage:
            with db_manager.get_session() as session:
                user = session.query(User).filter_by(username='admin').first()
        """
        if not HAS_SQLALCHEMY:
            raise RuntimeError("SQLAlchemy not installed")
        
        if not self._sqlalchemy_engine:
            self._init_sqlalchemy()
        
        session = self._sqlalchemy_session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """
        Ejecutar query y retornar resultados como lista de dicts
        
        Args:
            query: SQL query with placeholders
            params: Query parameters
        
        Returns:
            List of dicts with query results
        """
        with self.get_dict_cursor() as cur:
            if self.config.use_postgres:
                # PostgreSQL uses %s placeholders
                cur.execute(query, params or ())
            else:
                # SQLite uses ? placeholders
                query_sqlite = query.replace('%s', '?')
                cur.execute(query_sqlite, params or ())
            
            if cur.description:  # SELECT query
                if self.config.use_postgres:
                    return [dict(row) for row in cur.fetchall()]
                else:
                    return [dict(row) for row in cur.fetchall()]
            else:  # INSERT/UPDATE/DELETE
                return []
    
    def execute_many(self, query: str, params_list: List[tuple]) -> int:
        """
        Ejecutar query múltiples veces (batch insert/update)
        
        Args:
            query: SQL query
            params_list: List of parameter tuples
        
        Returns:
            Number of affected rows
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                if self.config.use_postgres:
                    cur.executemany(query, params_list)
                else:
                    query_sqlite = query.replace('%s', '?')
                    cur.executemany(query_sqlite, params_list)
                return cur.rowcount
    
    def get_table_exists(self, table_name: str) -> bool:
        """Verificar si una tabla existe"""
        if self.config.use_postgres:
            query = """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = %s
                );
            """
        else:
            query = """
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name=?;
            """
        
        with self.get_dict_cursor() as cur:
            if self.config.use_postgres:
                cur.execute(query, (table_name,))
                return cur.fetchone()['exists']
            else:
                cur.execute(query, (table_name,))
                return cur.fetchone() is not None
    
    def get_table_count(self, table_name: str) -> int:
        """Obtener número de registros en una tabla"""
        query = f"SELECT COUNT(*) as count FROM {table_name}"
        result = self.execute_query(query)
        return result[0]['count'] if result else 0
    
    def close(self):
        """Cerrar pool de conexiones"""
        if self._pg_pool:
            self._pg_pool.closeall()
            logger.info("PostgreSQL connection pool closed")
        
        if self._sqlalchemy_engine:
            self._sqlalchemy_engine.dispose()
            logger.info("SQLAlchemy engine disposed")


# Instancia global (singleton pattern)
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """Obtener instancia global del DatabaseManager (singleton)"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def init_db(config: Optional[DatabaseConfig] = None):
    """Inicializar database manager con configuración personalizada"""
    global _db_manager
    _db_manager = DatabaseManager(config)
    return _db_manager


# Convenience functions
def execute_query(query: str, params: tuple = None) -> List[Dict[str, Any]]:
    """Shortcut para ejecutar queries"""
    return get_db_manager().execute_query(query, params)


def execute_many(query: str, params_list: List[tuple]) -> int:
    """Shortcut para batch operations"""
    return get_db_manager().execute_many(query, params_list)


if __name__ == '__main__':
    # Test the database manager
    logging.basicConfig(level=logging.INFO)
    
    print("\n🔍 Testing Database Manager\n")
    
    config = DatabaseConfig()
    print(f"Database Type: {config.db_type}")
    print(f"Use PostgreSQL: {config.use_postgres}")
    
    if config.use_postgres:
        print(f"PostgreSQL DSN: {config.postgres_dsn}")
    else:
        print(f"SQLite Path: {config.sqlite_db_path}")
    
    # Initialize
    db = init_db()
    
    # Test query
    try:
        with db.get_dict_cursor() as cur:
            if config.use_postgres:
                cur.execute("SELECT current_database(), current_user;")
                result = cur.fetchone()
                print(f"\n✅ Connected to: {result['current_database']} as {result['current_user']}")
            else:
                cur.execute("SELECT sqlite_version();")
                result = cur.fetchone()
                print(f"\n✅ SQLite version: {result[0]}")
        
        # Check if users table exists
        if db.get_table_exists('users'):
            count = db.get_table_count('users')
            print(f"📊 Users table exists with {count} records")
        else:
            print("⚠️  Users table not found - run init schema first")
    
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        db.close()
