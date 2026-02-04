"""enhanced_memory.py
Sistema de memoria mejorado con persistencia, búsqueda semántica y compresión automática.
"""
from __future__ import annotations
import sqlite3
import json
import pickle
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class EnhancedMemory:
    """
    Memoria mejorada con:
    - Persistencia en base de datos
    - Búsqueda semántica usando embeddings
    - Memoria a corto y largo plazo
    - Compresión automática de contexto antiguo
    - Puntuación de importancia
    """
    
    def __init__(self, db_path: str, embedder, user_id: str = "anonymous", 
                 max_short_term: int = 20, llm_client=None):
        """
        Args:
            db_path: Ruta a la base de datos SQLite
            embedder: Objeto embedder para generar embeddings
            user_id: ID del usuario
            max_short_term: Número máximo de mensajes en memoria corto plazo
            llm_client: Cliente LLM para resúmenes (opcional)
        """
        self.db_path = db_path
        self.embedder = embedder
        self.user_id = user_id
        self.max_short_term = max_short_term
        self.llm_client = llm_client
        
        # Memoria de corto plazo (en RAM)
        self.short_term: List[Dict[str, Any]] = []
        
        # Inicializar base de datos
        self._init_db()
        
        # Cargar memoria reciente
        self._load_recent_memory()
    
    def _init_db(self):
        """Inicializar tabla de memoria si no existe"""
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS long_term_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    conversation_id INTEGER,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    embedding BLOB,
                    metadata TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    importance_score REAL DEFAULT 0.5,
                    is_summarized INTEGER DEFAULT 0
                )
            """)
            
            # Índices para búsqueda rápida
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_user 
                ON long_term_memory(user_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_timestamp 
                ON long_term_memory(timestamp DESC)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_importance 
                ON long_term_memory(importance_score DESC)
            """)
            
            conn.commit()
        finally:
            conn.close()
    
    def _load_recent_memory(self):
        """Cargar mensajes recientes en memoria de corto plazo"""
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT role, content, metadata, timestamp, importance_score
                FROM long_term_memory
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (self.user_id, self.max_short_term))
            
            rows = cur.fetchall()
            self.short_term = []
            
            for row in reversed(rows):  # Invertir para orden cronológico
                role, content, metadata_json, timestamp, importance = row
                metadata = json.loads(metadata_json) if metadata_json else {}
                
                self.short_term.append({
                    'role': role,
                    'content': content,
                    'metadata': metadata,
                    'timestamp': timestamp,
                    'importance': importance
                })
        finally:
            conn.close()
    
    def add(self, role: str, content: str, metadata: Optional[Dict] = None, 
            conversation_id: Optional[int] = None, importance: float = 0.5):
        """
        Agregar mensaje a memoria corto y largo plazo
        
        Args:
            role: 'user' o 'assistant'
            content: Contenido del mensaje
            metadata: Metadata adicional (opcional)
            conversation_id: ID de conversación (opcional)
            importance: Puntuación de importancia 0-1 (opcional)
        """
        if not content or not content.strip():
            return
        
        # Calcular importancia automáticamente si no se proporciona
        if importance == 0.5:
            importance = self._calculate_importance(role, content, metadata)
        
        # Generar embedding para búsqueda semántica
        try:
            embedding = self.embedder.encode_query(content)
            embedding_blob = pickle.dumps(embedding)
        except Exception as e:
            logger.warning(f"Error generando embedding: {e}")
            embedding_blob = None
        
        # Guardar en base de datos
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            metadata_json = json.dumps(metadata) if metadata else None
            
            cur.execute("""
                INSERT INTO long_term_memory 
                (user_id, conversation_id, role, content, embedding, metadata, importance_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (self.user_id, conversation_id, role, content, 
                  embedding_blob, metadata_json, importance))
            
            conn.commit()
        finally:
            conn.close()
        
        # Agregar a memoria de corto plazo
        self.short_term.append({
            'role': role,
            'content': content,
            'metadata': metadata or {},
            'timestamp': datetime.now().isoformat(),
            'importance': importance
        })
        
        # Mantener límite de memoria corto plazo
        if len(self.short_term) > self.max_short_term:
            self.short_term.pop(0)
        
        # Comprimir memoria antigua si es necesario
        self._compress_old_memory_if_needed()
    
    def _calculate_importance(self, role: str, content: str, metadata: Optional[Dict]) -> float:
        """
        Calcular puntuación de importancia automáticamente
        
        Factores:
        - Longitud del mensaje
        - Presencia de palabras clave importantes
        - Metadata especial
        """
        importance = 0.5  # Base
        
        # Mensajes del usuario son más importantes
        if role == 'user':
            importance += 0.1
        
        # Mensajes largos tienden a ser más importantes
        if len(content) > 200:
            importance += 0.1
        if len(content) > 500:
            importance += 0.1
        
        # Palabras clave importantes
        important_keywords = [
            'importante', 'recordar', 'siempre', 'nunca', 'preferencia',
            'me gusta', 'no me gusta', 'quiero', 'necesito'
        ]
        content_lower = content.lower()
        for keyword in important_keywords:
            if keyword in content_lower:
                importance += 0.15
                break
        
        # Metadata especial
        if metadata:
            if metadata.get('tool_used'):
                importance += 0.1
            if metadata.get('reasoning'):
                importance += 0.1
        
        return min(importance, 1.0)  # Máximo 1.0
    
    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtener mensajes recientes de memoria corto plazo
        
        Args:
            limit: Número máximo de mensajes
            
        Returns:
            Lista de mensajes recientes
        """
        return self.short_term[-limit:] if self.short_term else []
    
    def get_relevant(self, query: str, limit: int = 5, 
                     min_importance: float = 0.3) -> List[Dict[str, Any]]:
        """
        Recuperar mensajes relevantes usando búsqueda semántica
        
        Args:
            query: Consulta para buscar mensajes relevantes
            limit: Número máximo de resultados
            min_importance: Importancia mínima para considerar
            
        Returns:
            Lista de mensajes relevantes ordenados por relevancia
        """
        # Generar embedding de la consulta
        try:
            query_embedding = self.embedder.encode_query(query)
        except Exception as e:
            logger.warning(f"Error generando embedding de consulta: {e}")
            return []
        
        # Buscar en base de datos
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, role, content, metadata, timestamp, importance_score, embedding
                FROM long_term_memory
                WHERE user_id = ? AND importance_score >= ? AND embedding IS NOT NULL
                ORDER BY timestamp DESC
                LIMIT 100
            """, (self.user_id, min_importance))
            
            rows = cur.fetchall()
            
            # Calcular similitud con cada mensaje
            results = []
            for row in rows:
                msg_id, role, content, metadata_json, timestamp, importance, embedding_blob = row
                
                try:
                    msg_embedding = pickle.loads(embedding_blob)
                    similarity = self._cosine_similarity(query_embedding, msg_embedding)
                    
                    # Combinar similitud con importancia
                    score = (similarity * 0.7) + (importance * 0.3)
                    
                    metadata = json.loads(metadata_json) if metadata_json else {}
                    
                    results.append({
                        'id': msg_id,
                        'role': role,
                        'content': content,
                        'metadata': metadata,
                        'timestamp': timestamp,
                        'importance': importance,
                        'relevance_score': score
                    })
                except Exception as e:
                    logger.warning(f"Error procesando mensaje {msg_id}: {e}")
                    continue
            
            # Ordenar por score y retornar top-k
            results.sort(key=lambda x: x['relevance_score'], reverse=True)
            return results[:limit]
            
        finally:
            conn.close()
    
    def _cosine_similarity(self, vec1, vec2) -> float:
        """Calcular similitud coseno entre dos vectores"""
        try:
            import numpy as np
            v1 = np.array(vec1, dtype=np.float32)
            v2 = np.array(vec2, dtype=np.float32)
            
            dot_product = np.dot(v1, v2)
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            return float(dot_product / (norm1 * norm2))
        except Exception:
            # Fallback sin numpy
            dot = sum(a * b for a, b in zip(vec1, vec2))
            import math
            norm1 = math.sqrt(sum(a * a for a in vec1))
            norm2 = math.sqrt(sum(b * b for b in vec2))
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            return dot / (norm1 * norm2)
    
    def _compress_old_memory_if_needed(self):
        """
        Comprimir memoria antigua si hay demasiados mensajes
        
        Estrategia:
        - Resumir conversaciones antiguas (>7 días)
        - Mantener solo mensajes importantes
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            
            # Contar mensajes no resumidos antiguos
            seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
            cur.execute("""
                SELECT COUNT(*) FROM long_term_memory
                WHERE user_id = ? AND timestamp < ? AND is_summarized = 0
            """, (self.user_id, seven_days_ago))
            
            old_count = cur.fetchone()[0]
            
            # Si hay más de 100 mensajes antiguos, comprimir
            if old_count > 100:
                logger.info(f"Comprimiendo {old_count} mensajes antiguos...")
                self._compress_old_conversations(seven_days_ago, conn)
        finally:
            conn.close()
    
    def _compress_old_conversations(self, cutoff_date: str, conn: sqlite3.Connection):
        """Comprimir conversaciones antiguas usando resúmenes"""
        if not self.llm_client:
            logger.warning("No hay LLM client para resumir, saltando compresión")
            return
        
        cur = conn.cursor()
        
        # Obtener mensajes antiguos agrupados por día
        cur.execute("""
            SELECT DATE(timestamp) as day, GROUP_CONCAT(content, '\n---\n') as combined
            FROM long_term_memory
            WHERE user_id = ? AND timestamp < ? AND is_summarized = 0
            GROUP BY DATE(timestamp)
            ORDER BY day
        """, (self.user_id, cutoff_date))
        
        rows = cur.fetchall()
        
        for day, combined_content in rows:
            if not combined_content:
                continue
            
            try:
                # Generar resumen del día
                summary = self.llm_client.summarize(combined_content, max_chars=500)
                
                # Guardar resumen
                summary_embedding = pickle.dumps(self.embedder.encode_query(summary))
                
                cur.execute("""
                    INSERT INTO long_term_memory 
                    (user_id, role, content, embedding, importance_score, is_summarized, timestamp)
                    VALUES (?, 'system', ?, ?, 0.7, 1, ?)
                """, (self.user_id, f"Resumen del {day}: {summary}", 
                      summary_embedding, f"{day} 23:59:59"))
                
                # Marcar mensajes originales como resumidos
                cur.execute("""
                    UPDATE long_term_memory
                    SET is_summarized = 1
                    WHERE user_id = ? AND DATE(timestamp) = ? AND is_summarized = 0
                """, (self.user_id, day))
                
                conn.commit()
                logger.info(f"Resumido día {day}")
                
            except Exception as e:
                logger.error(f"Error resumiendo día {day}: {e}")
                continue
    
    def get_summary(self, days: int = 7) -> str:
        """
        Obtener resumen de memoria de los últimos N días
        
        Args:
            days: Número de días a resumir
            
        Returns:
            Resumen de la memoria
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT content FROM long_term_memory
                WHERE user_id = ? AND timestamp >= ? AND is_summarized = 1
                ORDER BY timestamp DESC
            """, (self.user_id, cutoff))
            
            summaries = [row[0] for row in cur.fetchall()]
            
            if summaries:
                return "\n\n".join(summaries)
            else:
                return "No hay resúmenes disponibles para este período."
        finally:
            conn.close()
    
    def clear(self):
        """Limpiar toda la memoria del usuario"""
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM long_term_memory WHERE user_id = ?", (self.user_id,))
            conn.commit()
            self.short_term = []
        finally:
            conn.close()
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de memoria"""
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            
            # Total de mensajes
            cur.execute("SELECT COUNT(*) FROM long_term_memory WHERE user_id = ?", (self.user_id,))
            total = cur.fetchone()[0]
            
            # Mensajes resumidos
            cur.execute("SELECT COUNT(*) FROM long_term_memory WHERE user_id = ? AND is_summarized = 1", 
                       (self.user_id,))
            summarized = cur.fetchone()[0]
            
            # Importancia promedio
            cur.execute("SELECT AVG(importance_score) FROM long_term_memory WHERE user_id = ?", 
                       (self.user_id,))
            avg_importance = cur.fetchone()[0] or 0.0
            
            # Mensaje más antiguo
            cur.execute("SELECT MIN(timestamp) FROM long_term_memory WHERE user_id = ?", 
                       (self.user_id,))
            oldest = cur.fetchone()[0]
            
            return {
                'total_messages': total,
                'summarized_messages': summarized,
                'active_messages': total - summarized,
                'average_importance': round(avg_importance, 2),
                'oldest_message': oldest,
                'short_term_size': len(self.short_term)
            }
        finally:
            conn.close()
