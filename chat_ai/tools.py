"""tools.py
Sistema de herramientas para la IA: Calculadora, Ejecución de Código, Búsqueda Web, etc.
"""
from __future__ import annotations
import logging
import math
import datetime
import sys
import io
import contextlib
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class ToolSystem:
    """
    Gestor de herramientas disponibles para la IA.
    """
    
    def __init__(self):
        self.tools = {
            'calculator': self.calculator,
            'datetime': self.get_datetime,
            'python_repl': self.python_repl,
            'web_search': self.web_search,
            'system_info': self.get_system_info,
            'visualizer': self.visualize_concept,
            'finance_tool': self.finance_tool
        }
        
        # Import finance manager
        try:
            from .finance import finance_manager
            self.finance_manager = finance_manager
        except ImportError:
            self.finance_manager = None
            logger.warning("Finance module not available")
        
        # Intentar importar librerías opcionales
        try:
            from duckduckgo_search import DDGS
            self.ddgs = DDGS()
            self.has_search = True
        except ImportError:
            self.has_search = False
            logger.warning("duckduckgo-search no instalado. La búsqueda web estará limitada.")

    def detect_tool(self, query: str, llm_client) -> Optional[str]:
        """
        Detecta si se necesita una herramienta usando heurísticas rápidas primero,
        y fallback al LLM solo si es necesario.
        """
        q = query.lower()
        
        # 1. Heurísticas Rápidas (Zero Latency)
        
        # Visualizer
        if any(x in q for x in ['ver', 'mostrar', 'visualizar', 'show', 'display', 'diagrama', 'imagen', 'foto', 'esquema']):
            return 'visualizer'
            
        # Calculator
        if any(x in q for x in ['calcula', 'cuánto es', 'calculate', 'solve', '+', '*', '/']) and any(c.isdigit() for c in q):
            return 'calculator'
            
        # Datetime
        if any(x in q for x in ['hora', 'fecha', 'time', 'date', 'hoy', 'today']):
            return 'datetime'
            
        # Python REPL (Code)
        if any(x in q for x in ['python', 'código', 'code', 'script', 'función', 'algoritmo']):
            return 'python_repl'
            
        # Web Search (Explicit)
        if any(x in q for x in ['busca', 'search', 'google', 'internet', 'noticias', 'clima', 'weather', 'news']):
            return 'web_search'

        # Finance Tool (Heuristics)
        if any(x in q for x in ['saldo', 'balance', 'cuenta', 'dinero', 'banco', 'transacción', 'asiento', 'contabilidad', 'finance', 'money', 'budget', 'presupuesto']):
            return 'finance_tool'

        # 2. Si no es obvio, asumimos que NO es herramienta (para ser rápidos)
        # O podríamos llamar al LLM aquí si queremos ser muy precisos, pero 
        # para velocidad es mejor pecar de "no usar herramienta" en casos ambiguos
        # a menos que sea una pregunta muy compleja.
        
        return None

    def use_tool(self, tool_name: str, query: str, llm_client) -> Any:
        """Ejecuta una herramienta específica"""
        if tool_name not in self.tools:
            return f"Error: Herramienta {tool_name} no encontrada."
            
        try:
            if tool_name == 'calculator':
                # ... (código existente) ...
                expression = llm_client.chat(
                    prompt=f"Extrae solo la expresión matemática a calcular de: {query}. Responde SOLO con la expresión.",
                    system="Eres una calculadora."
                ).strip()
                return self.calculator(expression)
            
            elif tool_name == 'visualizer':
                # Optimización: Extracción rápida sin LLM
                concept = query
                # Eliminar prefijos comunes
                prefixes = ['show me a ', 'show me ', 'visualize ', 'diagram of ', 'image of ', 
                           'muéstrame un ', 'muéstrame ', 'ver ', 'diagrama de ', 'imagen de ']
                lower_q = query.lower()
                for p in prefixes:
                    if lower_q.startswith(p):
                        concept = query[len(p):].strip()
                        break
                
                # Detectar dominio simple
                domain = "general"
                if any(x in lower_q for x in ['medical', 'heart', 'brain', 'surgery', 'médico', 'corazón']):
                    domain = "medical"
                elif any(x in lower_q for x in ['building', 'structure', 'foundation', 'edificio', 'arquitectura']):
                    domain = "architecture"
                elif any(x in lower_q for x in ['engine', 'motor', 'gear', 'ingeniería']):
                    domain = "engineering"
                
                return self.visualize_concept(concept, domain)

            elif tool_name == 'datetime':
                return self.get_datetime()
                
            elif tool_name == 'python_repl':
                # ... (código existente) ...
                code = llm_client.chat(
                    prompt=f"Escribe código Python para resolver: {query}. Responde SOLO con el código, sin bloques markdown ni explicaciones.",
                    system="Eres un experto programador Python."
                ).strip()
                code = code.replace('```python', '').replace('```', '').strip()
                return self.python_repl(code)
                
            elif tool_name == 'web_search':
                # ... (código existente) ...
                search_query = llm_client.chat(
                    prompt=f"Genera una consulta de búsqueda web óptima para: {query}. Responde SOLO con la consulta.",
                    system="Eres un experto en búsquedas web."
                ).strip()
                return self.web_search(search_query)
                
            elif tool_name == 'system_info':
                return self.get_system_info()

            elif tool_name == 'finance_tool':
                # Extraer intención con LLM si es complejo, o keyword simple
                if 'saldo' in query.lower() or 'balance' in query.lower():
                    return self.finance_tool("balances")
                elif 'transac' in query.lower() or 'movimiento' in query.lower():
                    return self.finance_tool("transactions")
                else:
                    return self.finance_tool("summary")
                
            return "Herramienta no implementada correctamente."
        except Exception as e:
            logger.error(f"Error usando herramienta {tool_name}: {e}")
            return f"Error al usar la herramienta: {str(e)}"

    def visualize_concept(self, concept: str, domain: str = "general") -> Dict[str, Any]:
        """Genera una visualización conceptual."""
        # Normalizar dominio
        domain = domain.lower()
        if domain not in ['medical', 'architecture', 'engineering', 'legal', 'government']:
            domain = 'general'
            
        return {
            "type": "generated_content",
            "title": f"Visualización: {concept}",
            "domain": domain,
            "media_assets": [{
                "type": "image",
                "url": f"/static/assets/placeholder_{domain}.png",
                "caption": f"Visualización de {concept}"
            }]
        }

    def calculator(self, expression: str) -> str:
        """Calculadora segura"""
        allowed_names = {
            k: v for k, v in math.__dict__.items() if not k.startswith("__")
        }
        allowed_names.update({
            "abs": abs, "round": round, "min": min, "max": max, "sum": sum, "pow": pow
        })
        clean_expr = expression.replace('^', '**').replace('=', '')
        try:
            result = eval(clean_expr, {"__builtins__": {}}, allowed_names)
            return f"Resultado: {result}"
        except Exception as e:
            return f"Error de cálculo: {str(e)}"

    def get_datetime(self, *args) -> str:
        now = datetime.datetime.now()
        return f"Fecha y hora actual: {now.strftime('%Y-%m-%d %H:%M:%S')}"

    def python_repl(self, code: str) -> str:
        """Ejecuta código Python y captura la salida"""
        buffer = io.StringIO()
        try:
            # Contexto seguro limitado
            safe_globals = {
                "math": math,
                "datetime": datetime,
                "print": print,
                "range": range,
                "len": len,
                "float": float,
                "int": int,
                "str": str,
                "list": list,
                "dict": dict,
                "set": set,
                "min": min,
                "max": max,
                "sum": sum,
                "sorted": sorted,
            }
            
            # Intentar agregar pandas si está disponible
            try:
                import pandas as pd
                safe_globals['pd'] = pd
                import numpy as np
                safe_globals['np'] = np
            except ImportError:
                pass

            with contextlib.redirect_stdout(buffer):
                exec(code, safe_globals)
            
            output = buffer.getvalue()
            return f"Salida del código:\n{output}" if output else "Código ejecutado sin salida."
        except Exception as e:
            return f"Error de ejecución Python: {str(e)}"

    def web_search(self, query: str) -> str:
        """Busca en la web usando DuckDuckGo"""
        if not self.has_search:
            return "Error: Búsqueda web no disponible (falta librería duckduckgo-search)."
        
        try:
            results = self.ddgs.text(query, max_results=3)
            if not results:
                return "No se encontraron resultados."
            
            formatted = []
            for r in results:
                formatted.append(f"- {r.get('title')}: {r.get('body')} ({r.get('href')})")
            
            return "Resultados de búsqueda:\n" + "\n".join(formatted)
        except Exception as e:
            return f"Error en búsqueda web: {str(e)}"

    def get_system_info(self, *args) -> str:
        import platform
        return f"Sistema: {platform.system()} {platform.release()}, Python {platform.python_version()}"

    def finance_tool(self, action: str) -> str:
        """Herramienta para consultar datos financieros del ERP"""
        if not self.finance_manager:
            return "Error: Módulo financiero no disponible."

        try:
            if action == 'balances':
                accounts = self.finance_manager.get_accounts()
                report = "📊 Saldos de Cuentas:\n"
                for acc in accounts:
                    # Formato: [11100] Banco Principal: $1,500.00
                    balance = float(acc.get('balance', 0))
                    report += f"- [{acc['code']}] {acc['name']}: ${balance:,.2f}\n"
                return report

            elif action == 'transactions':
                txs = self.finance_manager.get_transactions(limit=5)
                report = "📜 Últimas 5 Transacciones:\n"
                if not txs:
                    return "No hay transacciones registradas."
                for tx in txs:
                    report += f"- {tx['transaction_date']} | {tx['transaction_number']}: {tx['description']} (${float(tx['total_amount']):,.2f})\n"
                return report

            else:
                # Resumen general
                accounts = self.finance_manager.get_accounts()
                total_assets = sum(float(a['balance']) for a in accounts if a['type'] == 'asset')
                total_revenue = sum(float(a['balance']) for a in accounts if a['type'] == 'revenue')
                return f"📈 Resumen Financiero:\n- Total Activos: ${total_assets:,.2f}\n- Total Ingresos: ${total_revenue:,.2f}\nUse 'ver saldos' o 'ver transacciones' para más detalle."

        except Exception as e:
            return f"Error consultando finanzas: {str(e)}"

