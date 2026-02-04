"""reasoning.py
Módulo para razonamiento avanzado (Chain-of-Thought) y verificación de consistencia.
"""
from __future__ import annotations
import logging
import re
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class ChainOfThoughtReasoner:
    """
    Implementa razonamiento paso a paso para resolver problemas complejos.
    """
    
    def __init__(self, llm_client):
        self.llm = llm_client
        
    def solve(self, problem: str, context: str = "") -> Dict[str, Any]:
        """
        Resuelve un problema usando Chain-of-Thought.
        
        Args:
            problem: El problema o pregunta a resolver
            context: Contexto adicional (opcional)
            
        Returns:
            Dict con la respuesta final y los pasos de razonamiento
        """
        logger.info(f"Iniciando razonamiento CoT para: {problem[:50]}...")
        
        # Paso 1: Análisis y Planificación
        plan_prompt = f"""
        Analiza el siguiente problema y crea un plan paso a paso para resolverlo.
        
        Problema: {problem}
        Contexto: {context}
        
        Tu respuesta debe tener este formato:
        ANÁLISIS: <breve análisis del problema>
        PLAN:
        1. <paso 1>
        2. <paso 2>
        ...
        """
        
        plan_response = self.llm.chat(
            prompt=plan_prompt,
            system="Eres un experto analista y planificador. Descompón problemas complejos en pasos lógicos."
        )
        
        # Paso 2: Ejecución (Simulada en un solo paso por ahora para eficiencia, 
        # pero estructurada para que el LLM piense paso a paso)
        execution_prompt = f"""
        Resuelve el problema siguiendo el plan.
        
        Problema: {problem}
        Contexto: {context}
        
        Plan propuesto:
        {plan_response}
        
        Instrucciones:
        - Ejecuta cada paso del plan explícitamente.
        - Muestra tu razonamiento para cada paso.
        - Al final, da la RESPUESTA FINAL clara y concisa.
        
        Formato de respuesta:
        PASO 1: <razonamiento y resultado>
        PASO 2: <razonamiento y resultado>
        ...
        CONCLUSIÓN: <síntesis>
        RESPUESTA FINAL: <respuesta final>
        """
        
        execution_response = self.llm.chat(
            prompt=execution_prompt,
            system="Eres un experto resolutor de problemas. Sigue el plan rigurosamente y muestra tu trabajo."
        )
        
        # Extraer respuesta final
        final_answer = self._extract_final_answer(execution_response)
        
        return {
            'answer': final_answer,
            'reasoning_steps': execution_response,
            'plan': plan_response
        }

    def _extract_final_answer(self, text: str) -> str:
        """Intenta extraer la respuesta final del texto generado"""
        # Buscar marcadores comunes
        markers = ["RESPUESTA FINAL:", "FINAL ANSWER:", "Respuesta:", "Conclusión:"]
        
        for marker in markers:
            if marker in text:
                parts = text.split(marker)
                if len(parts) > 1:
                    return parts[-1].strip()
        
        # Si no encuentra marcador, devolver el texto completo o los últimos párrafos
        return text

class ConsistencyChecker:
    """
    Verifica la consistencia de las respuestas generando múltiples intentos.
    """
    
    def __init__(self, llm_client):
        self.llm = llm_client
        
    def verify(self, question: str, initial_answer: str, num_samples: int = 2) -> Dict[str, Any]:
        """
        Verifica una respuesta generando alternativas y comparando.
        """
        logger.info(f"Verificando consistencia para: {question[:50]}...")
        
        alternatives = []
        for i in range(num_samples):
            resp = self.llm.chat(
                prompt=f"Responde a esta pregunta (intento independiente {i+1}): {question}",
                system="Eres un asistente experto. Responde de forma precisa."
            )
            alternatives.append(resp)
            
        # Comparar consistencia
        verification_prompt = f"""
        Pregunta: {question}
        
        Respuesta Original: {initial_answer}
        
        Alternativa 1: {alternatives[0]}
        {f'Alternativa 2: {alternatives[1]}' if len(alternatives) > 1 else ''}
        
        Tarea:
        1. Analiza si las respuestas son consistentes en cuanto a los hechos/conclusiones principales.
        2. Si hay contradicciones, determina cuál es la más probable de ser correcta.
        3. Genera una RESPUESTA MEJORADA que combine lo mejor de todas o corrija errores.
        
        Tu salida debe ser SOLO la RESPUESTA MEJORADA final.
        """
        
        improved_answer = self.llm.chat(
            prompt=verification_prompt,
            system="Eres un verificador de calidad y consistencia. Tu objetivo es la máxima precisión."
        )
        
        return {
            'verified_answer': improved_answer,
            'alternatives': alternatives,
            'was_consistent': True # Simplificación, idealmente el LLM nos diría
        }
