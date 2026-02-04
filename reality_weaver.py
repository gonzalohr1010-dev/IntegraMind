import pandas as pd
import json
import sqlite3
import re

class RealityWeaver:
    """
    Componente que ingiere datos crudos y 'teje' una estructura de conocimiento
    comprensible para la IA, sin esquemas predefinidos.
    """
    
    def __init__(self, db_path='knowledge_graph.db'):
        self.db_path = db_path
        self._init_meta_store()

    def _init_meta_store(self):
        """Inicializa el almacén de metadatos (el 'mapa' del conocimiento)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabla de Entidades (Nodos del árbol)
        # Registra qué 'COSAS' existen en la empresa (ej: "Bomba-01", "Sector-A")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY,
                name TEXT,
                type TEXT,
                description TEXT,
                raw_table_ref TEXT
            )
        ''')
        
        # Tabla de Relaciones (Ramas del árbol)
        # Registra cómo se conectan (ej: "Bomba-01" -> ALIMENTA -> "Sector-A")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS relationships (
                source_id INTEGER,
                target_id INTEGER,
                relation_type TEXT,
                weight REAL DEFAULT 1.0,
                FOREIGN KEY(source_id) REFERENCES entities(id),
                FOREIGN KEY(target_id) REFERENCES entities(id)
            )
        ''')
        
        conn.commit()
        conn.close()

    def ingest_csv(self, file_path, data_type_hint=None):
        """
        Ingiere un CSV desconocido y trata de entender qué es.
        """
        print(f"🕸️ Reality Weaver: Analizando {file_path}...")
        
        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            return f"Error leyendo archivo: {e}"

        # 1. Análisis de Estructura (Profiling)
        columns = df.columns.tolist()
        potential_ids = [c for c in columns if 'id' in c.lower() or 'code' in c.lower() or 'name' in c.lower()]
        potential_metrics = [c for c in columns if df[c].dtype in ['float64', 'int64'] and c not in potential_ids]
        potential_time = [c for c in columns if 'date' in c.lower() or 'time' in c.lower()]

        print(f"   🔍 Estructura Detectada:")
        print(f"      - Posibles Identificadores: {potential_ids}")
        print(f"      - Posibles Métricas: {potential_metrics}")
        print(f"      - Columnas de Tiempo: {potential_time}")

        # 2. Tejido de Nodos (Crear Entidades en el Gráfico)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        entity_count = 0
        
        # Si detectamos una columna que parece un nombre/ID, creamos nodos para cada fila única
        primary_id_col = potential_ids[0] if potential_ids else None
        
        if primary_id_col:
            unique_entities = df[primary_id_col].unique()
            for entity_name in unique_entities:
                # Insertar nodo en el gráfico
                cursor.execute("INSERT INTO entities (name, type, description, raw_table_ref) VALUES (?, ?, ?, ?)",
                               (str(entity_name), data_type_hint or 'unknown_asset', f"Ingested from {file_path}", file_path))
                entity_count += 1
        
        conn.commit()
        conn.close()
        
        return {
            "status": "success",
            "entities_created": entity_count,
            "structure_guess": {
                "type": data_type_hint or "generic_data",
                "metrics_found": len(potential_metrics)
            }
        }

    def process_live_packet(self, packet):
        """
        Procesa un paquete de datos en tiempo real (JSON).
        Packet format expected: { "asset_id": "...", "metric": "...", "value": ..., "timestamp": "..." }
        """
        asset_id = packet.get('asset_id')
        metric = packet.get('metric')
        value = packet.get('value')
        
        if not asset_id:
            return {"status": "error", "message": "Missing asset_id"}

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 1. Verificar si el nodo existe, si no, crearlo (Ghost Node)
        cursor.execute("SELECT id, type FROM entities WHERE name = ?", (asset_id,))
        row = cursor.fetchone()
        
        if not row:
            # Ghost Node Creation
            cursor.execute("INSERT INTO entities (name, type, description, raw_table_ref) VALUES (?, ?, ?, ?)",
                           (asset_id, 'ghost_asset', f"Auto-detected from live stream (metric: {metric})", 'live_stream'))
            node_id = cursor.lastrowid
            status = "created_ghost_node"
        else:
            node_id = row[0]
            status = "updated_existing"

        # 2. Registrar la métrica (Por ahora, usamos una tabla simple de 'live_values' o actualizamos atributos)
        # Para esta versión, guardaremos el último valor conocido en una tabla 'live_state'
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS live_state (
                entity_id INTEGER,
                metric_name TEXT,
                value REAL,
                last_updated TIMESTAMP,
                PRIMARY KEY (entity_id, metric_name),
                FOREIGN KEY(entity_id) REFERENCES entities(id)
            )
        ''')
        
        cursor.execute('''
            INSERT INTO live_state (entity_id, metric_name, value, last_updated)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(entity_id, metric_name) DO UPDATE SET
            value = excluded.value,
            last_updated = excluded.last_updated
        ''', (node_id, metric, value))
        
        conn.commit()
        conn.close()
        
        return {"status": "success", "action": status, "id": node_id}

if __name__ == "__main__":
    # Prueba rápida
    rw = RealityWeaver()
    print("✨ Reality Weaver Inicializado.")
