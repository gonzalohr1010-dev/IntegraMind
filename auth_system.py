"""
🔐 INTEGRA MIND - SISTEMA DE AUTENTICACIÓN Y SEGURIDAD
Sistema completo de autenticación con JWT, roles y encriptación
"""

import jwt
import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
import os
from cryptography.fernet import Fernet
import base64

# Configuración de seguridad
SECRET_KEY = os.getenv('JWT_SECRET_KEY', secrets.token_urlsafe(32))
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24
REFRESH_TOKEN_DAYS = 30

# Clave de encriptación para datos sensibles
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', Fernet.generate_key())
cipher_suite = Fernet(ENCRYPTION_KEY)

class AuthSystem:
    """Sistema de autenticación y autorización"""
    
    def __init__(self, db_path='users.sqlite'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Inicializa las tablas de seguridad"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabla de usuarios con campos de seguridad
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT DEFAULT 'viewer',
                company TEXT,
                is_active INTEGER DEFAULT 1,
                is_verified INTEGER DEFAULT 0,
                failed_login_attempts INTEGER DEFAULT 0,
                last_login DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tabla de tokens de refresh
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT UNIQUE NOT NULL,
                expires_at DATETIME NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Tabla de sesiones activas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS active_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_token TEXT UNIQUE NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                expires_at DATETIME NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Tabla de logs de seguridad
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS security_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                success INTEGER DEFAULT 1,
                details TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tabla de archivos de clientes (encriptados)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS client_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER,
                mime_type TEXT,
                is_encrypted INTEGER DEFAULT 1,
                encryption_key TEXT,
                uploaded_by INTEGER NOT NULL,
                access_level TEXT DEFAULT 'private',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (uploaded_by) REFERENCES users(id)
            )
        """)
        
        # Tabla de permisos de archivos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                permission_type TEXT DEFAULT 'read',
                granted_by INTEGER NOT NULL,
                expires_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (file_id) REFERENCES client_files(id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (granted_by) REFERENCES users(id)
            )
        """)
        
        conn.commit()
        conn.close()
        
        print("✅ Base de datos de seguridad inicializada")
    
    def hash_password(self, password, salt=None):
        """Hashea una contraseña con salt"""
        if salt is None:
            salt = secrets.token_hex(32)
        
        # Usar PBKDF2 con SHA256 (más seguro que SHA256 simple)
        pwd_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000  # 100,000 iteraciones
        )
        
        return pwd_hash.hex(), salt
    
    def verify_password(self, password, password_hash, salt):
        """Verifica una contraseña"""
        new_hash, _ = self.hash_password(password, salt)
        return new_hash == password_hash
    
    def create_user(self, username, email, password, role='viewer', company=None):
        """Crea un nuevo usuario"""
        try:
            # Validar contraseña fuerte
            if len(password) < 8:
                return {'success': False, 'error': 'La contraseña debe tener al menos 8 caracteres'}
            
            # Hashear contraseña
            pwd_hash, salt = self.hash_password(password)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, salt, role, company)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (username, email, pwd_hash, salt, role, company))
            
            user_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            # Log de seguridad
            self.log_security_event(user_id, 'user_created', success=True)
            
            return {'success': True, 'user_id': user_id}
            
        except sqlite3.IntegrityError as e:
            return {'success': False, 'error': 'Usuario o email ya existe'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def authenticate_user(self, username, password, ip_address=None, user_agent=None):
        """Autentica un usuario y genera tokens JWT"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Buscar usuario
        cursor.execute("""
            SELECT * FROM users 
            WHERE (username = ? OR email = ?) AND is_active = 1
        """, (username, username))
        
        user = cursor.fetchone()
        
        if not user:
            self.log_security_event(None, 'login_failed', ip_address, user_agent, False, 'User not found')
            conn.close()
            return {'success': False, 'error': 'Credenciales inválidas'}
        
        # Verificar intentos fallidos (bloqueo temporal)
        if user['failed_login_attempts'] >= 5:
            self.log_security_event(user['id'], 'login_blocked', ip_address, user_agent, False, 'Too many attempts')
            conn.close()
            return {'success': False, 'error': 'Cuenta bloqueada temporalmente. Contacte al administrador.'}
        
        # Verificar contraseña
        if not self.verify_password(password, user['password_hash'], user['salt']):
            # Incrementar intentos fallidos
            cursor.execute("""
                UPDATE users 
                SET failed_login_attempts = failed_login_attempts + 1
                WHERE id = ?
            """, (user['id'],))
            conn.commit()
            
            self.log_security_event(user['id'], 'login_failed', ip_address, user_agent, False, 'Invalid password')
            conn.close()
            return {'success': False, 'error': 'Credenciales inválidas'}
        
        # Login exitoso - resetear intentos fallidos
        cursor.execute("""
            UPDATE users 
            SET failed_login_attempts = 0, last_login = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (user['id'],))
        conn.commit()
        
        # Generar tokens
        access_token = self.generate_access_token(user)
        refresh_token = self.generate_refresh_token(user['id'])
        
        # Crear sesión activa
        session_token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=JWT_EXPIRATION_HOURS)
        
        cursor.execute("""
            INSERT INTO active_sessions (user_id, session_token, ip_address, user_agent, expires_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user['id'], session_token, ip_address, user_agent, expires_at))
        
        conn.commit()
        conn.close()
        
        self.log_security_event(user['id'], 'login_success', ip_address, user_agent, True)
        
        return {
            'success': True,
            'access_token': access_token,
            'refresh_token': refresh_token,
            'session_token': session_token,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'role': user['role'],
                'company': user['company']
            }
        }
    
    def generate_access_token(self, user):
        """Genera un token JWT de acceso"""
        payload = {
            'user_id': user['id'],
            'username': user['username'],
            'email': user['email'],
            'role': user['role'],
            'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
            'iat': datetime.utcnow()
        }
        
        return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    def generate_refresh_token(self, user_id):
        """Genera un token de refresh"""
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(days=REFRESH_TOKEN_DAYS)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO refresh_tokens (user_id, token, expires_at)
            VALUES (?, ?, ?)
        """, (user_id, token, expires_at))
        
        conn.commit()
        conn.close()
        
        return token
    
    def verify_token(self, token):
        """Verifica un token JWT"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
            return {'valid': True, 'payload': payload}
        except jwt.ExpiredSignatureError:
            return {'valid': False, 'error': 'Token expirado'}
        except jwt.InvalidTokenError:
            return {'valid': False, 'error': 'Token inválido'}
    
    def log_security_event(self, user_id, action, ip_address=None, user_agent=None, success=True, details=None):
        """Registra un evento de seguridad"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO security_logs (user_id, action, ip_address, user_agent, success, details)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, action, ip_address, user_agent, 1 if success else 0, details))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error logging security event: {e}")
    
    def encrypt_data(self, data):
        """Encripta datos sensibles"""
        if isinstance(data, str):
            data = data.encode('utf-8')
        return cipher_suite.encrypt(data).decode('utf-8')
    
    def decrypt_data(self, encrypted_data):
        """Desencripta datos"""
        if isinstance(encrypted_data, str):
            encrypted_data = encrypted_data.encode('utf-8')
        return cipher_suite.decrypt(encrypted_data).decode('utf-8')


# Decorador para proteger rutas
def require_auth(roles=None):
    """Decorador para requerir autenticación en rutas"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Obtener token del header
            auth_header = request.headers.get('Authorization')
            
            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({'error': 'Token no proporcionado'}), 401
            
            token = auth_header.split(' ')[1]
            
            # Verificar token
            auth_system = AuthSystem()
            result = auth_system.verify_token(token)
            
            if not result['valid']:
                return jsonify({'error': result['error']}), 401
            
            # Verificar rol si se especificó
            if roles and result['payload']['role'] not in roles:
                return jsonify({'error': 'Permisos insuficientes'}), 403
            
            # Agregar usuario al request
            request.current_user = result['payload']
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


# Instancia global
auth_system = AuthSystem()

if __name__ == '__main__':
    print("🔐 Sistema de Autenticación Integra Mind")
    print(f"✅ Base de datos: {auth_system.db_path}")
    print(f"🔑 Secret Key: {SECRET_KEY[:20]}...")
    print(f"🔒 Encryption Key: {ENCRYPTION_KEY[:20]}...")
