"""relation_extractor.py
Extractor de relaciones para identificar problemas, herramientas, acciones y resultados en documentos.
Inspirado en "The Reality Weaver" - extrae contexto, acción y resultado.
"""
from __future__ import annotations

from typing import List, Dict, Optional, Any
import json
import re
import logging
from .knowledge_graph import KnowledgeGraph, KnowledgeNode, KnowledgeEdge

logger = logging.getLogger(__name__)


class RelationExtractor:
    """
    Extrae relaciones causales de documentos de texto:
    - Problemas (síntomas, errores, necesidades)
    - Herramientas (equipos, software, recursos)
    - Acciones (pasos, procedimientos, operaciones)
    - Resultados (soluciones, efectos, consecuencias)
    """
    
    def __init__(self, knowledge_graph: KnowledgeGraph, llm_client=None):
        self.kg = knowledge_graph
        self.llm = llm_client
    
    def extract_from_text(self, text: str, source: str = "unknown", 
                          doc_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Extraer relaciones de un texto.
        
        Returns:
            Dict con 'nodes' (lista de nodos encontrados) y 'edges' (lista de relaciones)
        """
        if not text or len(text.strip()) < 50:
            return {"nodes": [], "edges": []}
        
        # Si tenemos LLM, usarlo para extracción inteligente
        if self.llm and hasattr(self.llm, 'chat'):
            return self._extract_with_llm(text, source, doc_id)
        else:
            # Fallback: extracción basada en patrones
            return self._extract_with_patterns(text, source, doc_id)
    
    def _extract_with_llm(self, text: str, source: str, doc_id: Optional[str]) -> Dict[str, Any]:
        """Extraer relaciones usando LLM"""
        prompt = f"""Analiza el siguiente texto y extrae información estructurada sobre problemas, herramientas, acciones y resultados.

Texto:
{text[:2000]}

Extrae la información en formato JSON con esta estructura:
{{
  "problems": [
    {{"label": "nombre del problema", "description": "descripción detallada"}}
  ],
  "tools": [
    {{"label": "nombre de la herramienta", "description": "para qué se usa"}}
  ],
  "actions": [
    {{"label": "nombre de la acción", "description": "qué se hace", "requires_tool": "herramienta necesaria (opcional)"}}
  ],
  "results": [
    {{"label": "nombre del resultado", "description": "qué se logra"}}
  ],
  "relations": [
    {{"source": "problema o acción", "target": "herramienta o resultado", "type": "requires|uses|produces|solves"}}
  ]
}}

Responde SOLO con el JSON, sin texto adicional."""

        try:
            response = self.llm.chat(prompt=prompt, system="Eres un extractor de conocimiento estructurado. Responde solo con JSON válido.")
            
            # Limpiar respuesta (puede tener markdown o texto extra)
            response_clean = response.strip()
            if response_clean.startswith("```json"):
                response_clean = response_clean[7:]
            if response_clean.startswith("```"):
                response_clean = response_clean[3:]
            if response_clean.endswith("```"):
                response_clean = response_clean[:-3]
            response_clean = response_clean.strip()
            
            data = json.loads(response_clean)
            return self._process_extracted_data(data, source, doc_id)
        except Exception as e:
            logger.warning(f"Error extracting with LLM: {e}, falling back to patterns")
            return self._extract_with_patterns(text, source, doc_id)
    
    def _extract_with_patterns(self, text: str, source: str, doc_id: Optional[str]) -> Dict[str, Any]:
        """Extraer relaciones usando patrones de texto (fallback)"""
        nodes = []
        edges = []
        
        # Patrones simples para identificar problemas
        problem_patterns = [
            r'(?:error|problema|fallo|falla|bug|issue|síntoma|necesita|requiere)\s+[a-záéíóúñ]+[^\n\.]{10,}',
            r'(?:no\s+funciona|no\s+se\s+puede|no\s+es\s+posible)[^\n\.]{10,}',
        ]
        
        # Patrones para herramientas
        tool_patterns = [
            r'(?:usar|utilizar|emplear|con|mediante)\s+([A-Z][a-záéíóúñ]+(?:\s+[A-Z][a-záéíóúñ]+)*)',
            r'(?:herramienta|equipo|software|aplicación|programa)\s+([A-Z][a-záéíóúñ]+(?:\s+[a-záéíóúñ]+)*)',
        ]
        
        # Patrones para acciones
        action_patterns = [
            r'(?:hacer|realizar|ejecutar|aplicar|girar|presionar|instalar|configurar)\s+[a-záéíóúñ]+[^\n\.]{10,}',
            r'(?:paso\s+\d+|primero|segundo|luego|después)\s+[^\n\.]{10,}',
        ]
        
        # Patrones para resultados
        result_patterns = [
            r'(?:resultado|solución|efecto|consecuencia|se\s+logra|se\s+obtiene)\s+[a-záéíóúñ]+[^\n\.]{10,}',
            r'(?:funciona|correcto|exitoso|resuelto|completado)[^\n\.]{10,}',
        ]
        
        # Extraer problemas
        for pattern in problem_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                label = match.group(0)[:50]
                node_id = f"problem_{hash(label) % 1000000}"
                nodes.append({
                    "id": node_id,
                    "type": "problem",
                    "label": label,
                    "description": match.group(0)[:200]
                })
        
        # Extraer herramientas
        for pattern in tool_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                label = match.group(1) if match.lastindex else match.group(0)[:50]
                node_id = f"tool_{hash(label) % 1000000}"
                nodes.append({
                    "id": node_id,
                    "type": "tool",
                    "label": label,
                    "description": match.group(0)[:200]
                })
        
        # Extraer acciones
        for pattern in action_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                label = match.group(0)[:50]
                node_id = f"action_{hash(label) % 1000000}"
                nodes.append({
                    "id": node_id,
                    "type": "action",
                    "label": label,
                    "description": match.group(0)[:200]
                })
        
        # Extraer resultados
        for pattern in result_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                label = match.group(0)[:50]
                node_id = f"result_{hash(label) % 1000000}"
                nodes.append({
                    "id": node_id,
                    "type": "result",
                    "label": label,
                    "description": match.group(0)[:200]
                })
        
        # Crear relaciones simples basadas en proximidad
        # (si un problema y una herramienta aparecen cerca, crear relación)
        for i, node1 in enumerate(nodes):
            for node2 in nodes[i+1:]:
                if node1["type"] == "problem" and node2["type"] == "tool":
                    edges.append({
                        "source": node1["id"],
                        "target": node2["id"],
                        "type": "requires",
                        "weight": 0.5
                    })
                elif node1["type"] == "tool" and node2["type"] == "action":
                    edges.append({
                        "source": node1["id"],
                        "target": node2["id"],
                        "type": "uses",
                        "weight": 0.5
                    })
                elif node1["type"] == "action" and node2["type"] == "result":
                    edges.append({
                        "source": node1["id"],
                        "target": node2["id"],
                        "type": "produces",
                        "weight": 0.5
                    })
        
        return {
            "nodes": nodes,
            "edges": edges,
            "source": source,
            "doc_id": doc_id
        }
    
    def _process_extracted_data(self, data: Dict[str, Any], source: str, 
                               doc_id: Optional[str]) -> Dict[str, Any]:
        """Procesar datos extraídos y crear nodos y aristas en el grafo"""
        nodes_created = []
        edges_created = []
        
        doc_id_str = doc_id or source
        
        # Crear nodos de problemas
        for prob in data.get("problems", []):
            node_id = f"problem_{hash(prob.get('label', '')) % 1000000}"
            node = KnowledgeNode(
                id=node_id,
                type="problem",
                label=prob.get("label", "Problema desconocido"),
                description=prob.get("description", ""),
                metadata={"source": source, "doc_id": doc_id_str}
            )
            self.kg.add_node(node)
            nodes_created.append(node_id)
        
        # Crear nodos de herramientas
        for tool in data.get("tools", []):
            node_id = f"tool_{hash(tool.get('label', '')) % 1000000}"
            node = KnowledgeNode(
                id=node_id,
                type="tool",
                label=tool.get("label", "Herramienta desconocida"),
                description=tool.get("description", ""),
                metadata={"source": source, "doc_id": doc_id_str}
            )
            self.kg.add_node(node)
            nodes_created.append(node_id)
        
        # Crear nodos de acciones
        for action in data.get("actions", []):
            node_id = f"action_{hash(action.get('label', '')) % 1000000}"
            node = KnowledgeNode(
                id=node_id,
                type="action",
                label=action.get("label", "Acción desconocida"),
                description=action.get("description", ""),
                metadata={"source": source, "doc_id": doc_id_str, 
                         "requires_tool": action.get("requires_tool")}
            )
            self.kg.add_node(node)
            nodes_created.append(node_id)
        
        # Crear nodos de resultados
        for result in data.get("results", []):
            node_id = f"result_{hash(result.get('label', '')) % 1000000}"
            node = KnowledgeNode(
                id=node_id,
                type="result",
                label=result.get("label", "Resultado desconocido"),
                description=result.get("description", ""),
                metadata={"source": source, "doc_id": doc_id_str}
            )
            self.kg.add_node(node)
            nodes_created.append(node_id)
        
        # Crear aristas (relaciones)
        for rel in data.get("relations", []):
            source_label = rel.get("source", "")
            target_label = rel.get("target", "")
            rel_type = rel.get("type", "uses")
            
            # Buscar IDs de nodos por label
            source_id = None
            target_id = None
            
            for node in self.kg.nodes.values():
                if source_label.lower() in node.label.lower():
                    source_id = node.id
                if target_label.lower() in node.label.lower():
                    target_id = node.id
            
            if source_id and target_id:
                edge = KnowledgeEdge(
                    source=source_id,
                    target=target_id,
                    relation_type=rel_type,
                    weight=0.8,  # Confianza media-alta para extracciones con LLM
                    evidence=[doc_id_str] if doc_id_str else []
                )
                self.kg.add_edge(edge)
                edges_created.append(edge)
        
        return {
            "nodes": nodes_created,
            "edges": len(edges_created),
            "source": source,
            "doc_id": doc_id_str
        }
    
    def extract_from_experience_object(self, exp_obj: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extraer relaciones de un Experience Object (estructura rica con contexto, acciones, resultados).
        """
        title = exp_obj.get("title", "")
        context = exp_obj.get("context", "")
        actions = exp_obj.get("action_plan", [])
        results = exp_obj.get("result", "") or exp_obj.get("outcome", "")
        source = exp_obj.get("source", "experience")
        
        # Crear nodo de problema desde el contexto
        problem_id = f"problem_exp_{hash(context) % 1000000}"
        if context:
            problem_node = KnowledgeNode(
                id=problem_id,
                type="problem",
                label=title or "Problema de experiencia",
                description=context,
                metadata={"source": source, "is_experience": True}
            )
            self.kg.add_node(problem_node)
        
        # Crear nodos de acciones con mejor extracción de información
        action_ids = []
        tool_ids = []  # Track herramientas para crear relaciones
        
        for i, action in enumerate(actions):
            if isinstance(action, dict):
                # Extraer label de acción (prioridad: action > step > descripción corta)
                action_label = action.get("action") or action.get("step") or action.get("description", "")
                if not action_label or action_label.isdigit():
                    # Si es solo un número, usar la descripción
                    action_label = action.get("description", f"Acción {i+1}")
                    if len(action_label) > 50:
                        action_label = action_label[:47] + "..."
                
                action_desc = action.get("description", str(action))
                tool_name = action.get("tool") or action.get("tool_name")
            else:
                # Si es string, intentar extraer información
                action_str = str(action)
                action_label = action_str[:50] + "..." if len(action_str) > 50 else action_str
                action_desc = action_str
                tool_name = None
            
            # Crear nodo de acción con ID único basado en contenido
            action_hash = hash(f"{source}_{i}_{action_label}") % 1000000
            action_id = f"action_exp_{action_hash}"
            
            action_node = KnowledgeNode(
                id=action_id,
                type="action",
                label=action_label if action_label else f"Paso {i+1}",
                description=action_desc,
                metadata={
                    "source": source, 
                    "is_experience": True, 
                    "step_order": i,
                    "tool": tool_name
                }
            )
            self.kg.add_node(action_node)
            action_ids.append(action_id)
            
            # Si hay herramienta mencionada, crear nodo de herramienta y relación
            if tool_name:
                tool_hash = hash(f"{source}_tool_{tool_name}") % 1000000
                tool_id = f"tool_exp_{tool_hash}"
                
                # Verificar si la herramienta ya existe
                if tool_id not in self.kg.nodes:
                    tool_node = KnowledgeNode(
                        id=tool_id,
                        type="tool",
                        label=tool_name,
                        description=f"Herramienta usada en: {title or 'experiencia'}",
                        metadata={"source": source, "is_experience": True}
                    )
                    self.kg.add_node(tool_node)
                    tool_ids.append(tool_id)
                
                # Crear relación: herramienta -> usa -> acción
                tool_edge = KnowledgeEdge(
                    source=tool_id,
                    target=action_id,
                    relation_type="uses",
                    weight=0.85,
                    evidence=[source]
                )
                self.kg.add_edge(tool_edge)
        
        # Crear nodo de resultado con mejor label
        result_id = None
        if results:
            # Extraer un label más descriptivo del resultado
            result_str = str(results)
            if len(result_str) > 60:
                result_label = result_str[:57] + "..."
            else:
                result_label = result_str
            
            # Si el resultado es muy genérico, usar el título de la experiencia
            if result_label.lower() in ["resultado exitoso", "éxito", "completado", "resuelto"]:
                result_label = f"Resultado: {title}" if title else "Resultado exitoso"
            
            result_hash = hash(f"{source}_result_{results}") % 1000000
            result_id = f"result_exp_{result_hash}"
            
            result_node = KnowledgeNode(
                id=result_id,
                type="result",
                label=result_label,
                description=result_str,
                metadata={"source": source, "is_experience": True, "experience_title": title}
            )
            self.kg.add_node(result_node)
        
        # Crear relaciones
        edges_created = []
        if context and action_ids:
            # Problema -> requiere -> Acción
            for action_id in action_ids:
                edge = KnowledgeEdge(
                    source=problem_id,
                    target=action_id,
                    relation_type="requires",
                    weight=0.9,
                    evidence=[source]
                )
                self.kg.add_edge(edge)
                edges_created.append(edge)
        
        if action_ids and result_id:
            # Acción -> produce -> Resultado
            for action_id in action_ids:
                edge = KnowledgeEdge(
                    source=action_id,
                    target=result_id,
                    relation_type="produces",
                    weight=0.9,
                    evidence=[source]
                )
                self.kg.add_edge(edge)
                edges_created.append(edge)
        
        return {
            "nodes": [problem_id] + action_ids + ([result_id] if result_id else []),
            "edges": len(edges_created),
            "source": source
        }

