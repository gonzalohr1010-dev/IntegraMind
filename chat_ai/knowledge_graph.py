"""knowledge_graph.py
Sistema de Knowledge Graph para capturar relaciones causales entre problemas, herramientas, acciones y resultados.
Inspirado en "The Reality Weaver" - Fase 2: Grafos de Conocimiento Físico.
"""
from __future__ import annotations

from typing import List, Dict, Optional, Set, Tuple, Any
import json
import sqlite3
import logging
from collections import defaultdict
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeNode:
    """Nodo en el grafo de conocimiento"""
    id: str
    type: str  # 'problem', 'tool', 'action', 'result', 'concept'
    label: str
    description: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class KnowledgeEdge:
    """Arista en el grafo de conocimiento que representa una relación causal"""
    source: str  # ID del nodo origen
    target: str  # ID del nodo destino
    relation_type: str  # 'requires', 'produces', 'uses', 'solves', 'enables'
    weight: float  # Confianza en la relación (0.0 a 1.0)
    evidence: List[str]  # IDs de documentos que respaldan esta relación
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class KnowledgeGraph:
    """
    Grafo de conocimiento que almacena relaciones causales:
    Problema -> requiere -> Herramienta -> usa -> Acción -> produce -> Resultado
    """
    
    def __init__(self, db_path: str = "knowledge_graph.db"):
        self.db_path = db_path
        self.nodes: Dict[str, KnowledgeNode] = {}
        self.edges: List[KnowledgeEdge] = []
        self._init_db()
        self._load_from_db()
    
    def _init_db(self):
        """Inicializar tablas de base de datos"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        # Tabla de nodos
        cur.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                label TEXT NOT NULL,
                description TEXT,
                metadata TEXT
            )
        """)
        
        # Tabla de aristas
        cur.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                evidence TEXT,
                FOREIGN KEY (source) REFERENCES nodes(id),
                FOREIGN KEY (target) REFERENCES nodes(id)
            )
        """)
        
        # Índices para búsquedas rápidas
        cur.execute("CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(relation_type)")
        
        conn.commit()
        conn.close()
    
    def _load_from_db(self):
        """Cargar grafo desde base de datos"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        # Cargar nodos
        cur.execute("SELECT id, type, label, description, metadata FROM nodes")
        for row in cur.fetchall():
            node_id, node_type, label, description, metadata_json = row
            metadata = json.loads(metadata_json) if metadata_json else {}
            self.nodes[node_id] = KnowledgeNode(
                id=node_id,
                type=node_type,
                label=label,
                description=description or "",
                metadata=metadata
            )
        
        # Cargar aristas
        cur.execute("SELECT source, target, relation_type, weight, evidence FROM edges")
        for row in cur.fetchall():
            source, target, relation_type, weight, evidence_json = row
            evidence = json.loads(evidence_json) if evidence_json else []
            self.edges.append(KnowledgeEdge(
                source=source,
                target=target,
                relation_type=relation_type,
                weight=float(weight),
                evidence=evidence
            ))
        
        conn.close()
        logger.info(f"Loaded {len(self.nodes)} nodes and {len(self.edges)} edges from database")
    
    def add_node(self, node: KnowledgeNode) -> None:
        """Agregar o actualizar un nodo"""
        self.nodes[node.id] = node
        self._save_node_to_db(node)
    
    def _save_node_to_db(self, node: KnowledgeNode):
        """Guardar nodo en base de datos"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO nodes (id, type, label, description, metadata)
            VALUES (?, ?, ?, ?, ?)
        """, (
            node.id,
            node.type,
            node.label,
            node.description,
            json.dumps(node.metadata, ensure_ascii=False)
        ))
        conn.commit()
        conn.close()
    
    def add_edge(self, edge: KnowledgeEdge) -> None:
        """Agregar una arista (relación)"""
        # Verificar que ambos nodos existan
        if edge.source not in self.nodes:
            logger.warning(f"Source node {edge.source} not found, skipping edge")
            return
        if edge.target not in self.nodes:
            logger.warning(f"Target node {edge.target} not found, skipping edge")
            return
        
        # Evitar duplicados (misma relación)
        existing = next(
            (e for e in self.edges 
             if e.source == edge.source and e.target == edge.target and e.relation_type == edge.relation_type),
            None
        )
        if existing:
            # Actualizar peso y evidencia si la nueva relación es más fuerte
            if edge.weight > existing.weight:
                existing.weight = edge.weight
                existing.evidence.extend(edge.evidence)
                existing.evidence = list(set(existing.evidence))  # Eliminar duplicados
                self._update_edge_in_db(existing)
        else:
            self.edges.append(edge)
            self._save_edge_to_db(edge)
    
    def _save_edge_to_db(self, edge: KnowledgeEdge):
        """Guardar arista en base de datos"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO edges (source, target, relation_type, weight, evidence)
            VALUES (?, ?, ?, ?, ?)
        """, (
            edge.source,
            edge.target,
            edge.relation_type,
            edge.weight,
            json.dumps(edge.evidence, ensure_ascii=False)
        ))
        conn.commit()
        conn.close()
    
    def _update_edge_in_db(self, edge: KnowledgeEdge):
        """Actualizar arista existente en base de datos"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            UPDATE edges SET weight=?, evidence=?
            WHERE source=? AND target=? AND relation_type=?
        """, (
            edge.weight,
            json.dumps(edge.evidence, ensure_ascii=False),
            edge.source,
            edge.target,
            edge.relation_type
        ))
        conn.commit()
        conn.close()
    
    def find_nodes(self, query: str, node_type: Optional[str] = None, limit: int = 10) -> List[KnowledgeNode]:
        """Buscar nodos por texto (búsqueda simple en label y description)"""
        results = []
        query_lower = query.lower()
        
        for node in self.nodes.values():
            if node_type and node.type != node_type:
                continue
            if query_lower in node.label.lower() or query_lower in node.description.lower():
                results.append(node)
        
        return results[:limit]
    
    def get_related_nodes(self, node_id: str, relation_type: Optional[str] = None, 
                          direction: str = "both") -> List[Tuple[KnowledgeNode, KnowledgeEdge]]:
        """
        Obtener nodos relacionados con un nodo dado.
        
        Args:
            node_id: ID del nodo
            relation_type: Filtrar por tipo de relación (opcional)
            direction: 'out' (salientes), 'in' (entrantes), 'both' (ambas)
        """
        if node_id not in self.nodes:
            return []
        
        results = []
        for edge in self.edges:
            if relation_type and edge.relation_type != relation_type:
                continue
            
            if direction in ("out", "both") and edge.source == node_id:
                target_node = self.nodes.get(edge.target)
                if target_node:
                    results.append((target_node, edge))
            
            if direction in ("in", "both") and edge.target == node_id:
                source_node = self.nodes.get(edge.source)
                if source_node:
                    results.append((source_node, edge))
        
        return results
    
    def find_solution_path(self, problem: str, max_depth: int = 4) -> List[Dict[str, Any]]:
        """
        Encontrar un camino de solución desde un problema hasta un resultado.
        Retorna una lista de pasos: [problema -> herramienta -> acción -> resultado]
        Mejorado para encontrar caminos más completos y relevantes.
        """
        # Buscar nodos de problema que coincidan (búsqueda más flexible)
        problem_nodes = self.find_nodes(problem, node_type="problem")
        
        # Si no encuentra problemas exactos, buscar por similitud en descripción
        if not problem_nodes:
            # Buscar en todos los nodos de problema
            all_problems = self.find_nodes("", node_type="problem")
            problem_lower = problem.lower()
            for prob in all_problems:
                if problem_lower in prob.label.lower() or problem_lower in prob.description.lower():
                    problem_nodes.append(prob)
        
        if not problem_nodes:
            return []
        
        paths = []
        visited_edges = set()  # Evitar ciclos en aristas
        
        def dfs(node_id: str, path: List[Tuple[str, str, str]], depth: int, current_sequence: List[str]):
            """Búsqueda en profundidad mejorada para encontrar caminos"""
            if depth > max_depth:
                return
            
            node = self.nodes.get(node_id)
            if not node:
                return
            
            # Si llegamos a un resultado, guardamos el camino
            if node.type == "result":
                # Solo guardar si el camino tiene al menos 2 pasos (problema -> algo -> resultado)
                if len(path) >= 2:
                    paths.append({
                        "path": path.copy(),
                        "sequence": current_sequence.copy(),
                        "score": self._calculate_path_score(path)
                    })
                return
            
            # Explorar relaciones salientes con priorización
            related = self.get_related_nodes(node_id, direction="out")
            
            # Priorizar relaciones que llevan a resultados
            prioritized = []
            regular = []
            
            for target_node, edge in related:
                edge_key = (node_id, target_node.id, edge.relation_type)
                if edge_key in visited_edges:
                    continue
                
                # Priorizar acciones y herramientas (más cercanos a resultados)
                if target_node.type in ("action", "tool"):
                    prioritized.append((target_node, edge, edge_key))
                else:
                    regular.append((target_node, edge, edge_key))
            
            # Procesar primero los prioritarios
            for target_node, edge, edge_key in prioritized + regular:
                visited_edges.add(edge_key)
                new_path = path + [(edge.relation_type, target_node.id, target_node.type)]
                new_sequence = current_sequence + [target_node.label]
                dfs(target_node.id, new_path, depth + 1, new_sequence)
                visited_edges.remove(edge_key)
        
        # Iniciar búsqueda desde cada nodo de problema
        for problem_node in problem_nodes:
            dfs(problem_node.id, [("start", problem_node.id, "problem")], 0, [problem_node.label])
        
        # Ordenar caminos por score (mejores primero) y limitar
        paths.sort(key=lambda x: x["score"], reverse=True)
        
        # Formatear resultados
        formatted_paths = []
        for path_data in paths[:5]:  # Top 5 caminos
            path = path_data["path"]
            steps = []
            for i, (relation, node_id, node_type) in enumerate(path):
                node = self.nodes.get(node_id)
                if node:
                    steps.append({
                        "step": i + 1,
                        "node": node.to_dict(),
                        "relation": relation if i > 0 else "start",
                        "type": node_type
                    })
            if steps:
                formatted_paths.append({
                    "path": steps, 
                    "length": len(steps),
                    "score": path_data["score"],
                    "sequence": path_data["sequence"]
                })
        
        return formatted_paths
    
    def _calculate_path_score(self, path: List[Tuple[str, str, str]]) -> float:
        """Calcular score de un camino basado en su calidad"""
        if not path:
            return 0.0
        
        score = 1.0
        
        # Bonus por tener tipos variados (problema -> acción -> resultado es mejor)
        types_seen = set()
        for _, _, node_type in path:
            types_seen.add(node_type)
        
        # Más tipos = mejor camino
        score += len(types_seen) * 0.2
        
        # Penalizar caminos muy largos
        if len(path) > 5:
            score -= (len(path) - 5) * 0.1
        
        # Bonus por tener resultado al final
        if path and path[-1][2] == "result":
            score += 0.5
        
        return max(0.0, score)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Obtener estadísticas del grafo"""
        node_types = defaultdict(int)
        relation_types = defaultdict(int)
        
        for node in self.nodes.values():
            node_types[node.type] += 1
        
        for edge in self.edges:
            relation_types[edge.relation_type] += 1
        
        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "nodes_by_type": dict(node_types),
            "relations_by_type": dict(relation_types)
        }
    
    def export_json(self) -> Dict[str, Any]:
        """Exportar grafo completo como JSON"""
        return {
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges]
        }

