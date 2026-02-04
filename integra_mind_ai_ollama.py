"""
Integra Mind AI - Cerebro LLM (Ollama)
Usa Modelos de Lenguaje Locales para razonamiento avanzado
"""

import sqlite3
import json
import requests
from datetime import datetime

class IntegraMindOllama:
    def __init__(self, db_path='energy_demo.db', model_name=None):
        self.db_path = db_path
        self.api_url = "http://localhost:11434/api/generate"
        self.model = model_name or self._detect_model()
        print(f"🧠 Cerebro inicializado con modelo: {self.model}")

    def _detect_model(self):
        """Detecta el primer modelo disponible en Ollama"""
        try:
            resp = requests.get("http://localhost:11434/api/tags")
            if resp.status_code == 200:
                models = resp.json().get('models', [])
                if models:
                    return models[0]['name']
        except Exception as e:
            print(f"⚠️ Error detectando modelos: {e}")
        return "llama3" # Fallback por defecto

    def _get_system_context(self):
        """Recopila datos en tiempo real para darle contexto al LLM"""
        
        # 1. Demanda Actual
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT total_demand_mw, renewable_percentage, frequency_hz FROM realtime_demand ORDER BY timestamp DESC LIMIT 1")
        row = cursor.fetchone()
        
        if row:
            demand, renewable, freq = row
            status_text = f"Demanda: {demand:.0f} MW | Renovables: {renewable:.1f}% | Frecuencia: {freq:.2f} Hz"
        else:
            status_text = "Datos de demanda no disponibles."

        # 2. Alertas Críticas
        cursor.execute("SELECT title, description FROM alerts WHERE severity='critical' AND is_resolved=0")
        alerts = cursor.fetchall()
        alert_text = ""
        if alerts:
            alert_text = "🚨 ALERTAS CRÍTICAS ACTIVAS:\n" + "\n".join([f"- {a[0]}: {a[1]}" for a in alerts])
        else:
            alert_text = "✅ No hay alertas críticas activas."

        # 3. Predicción
        cursor.execute("SELECT target_timestamp, predicted_demand_mw FROM demand_forecasts ORDER BY forecast_timestamp DESC, target_timestamp ASC LIMIT 1")
        pred = cursor.fetchone()
        pred_text = ""
        if pred:
            ts = datetime.fromisoformat(pred[0]).strftime('%H:%M')
            pred_text = f"Predicción inminente: {pred[1]:.0f} MW a las {ts}"

        conn.close()

        # 4. CONOCIMIENTO UNIVERSAL (Recién Ingestado)
        kg_text = ""
        try:
            conn_kg = sqlite3.connect('knowledge_graph.db')
            cursor_kg = conn_kg.cursor()
            cursor_kg.execute("SELECT name, type, description FROM entities LIMIT 10")
            entities = cursor_kg.fetchall()
            conn_kg.close()
            
            if entities:
                kg_text = "🌍 INFRAESTRUCTURA UNIVERSAL DETECTADA:\n" + "\n".join([f"- {e[0]} ({e[1]})" for e in entities])
        except Exception as e:
            print(f"Nota: No se pudo leer Knowledge Graph: {e}")

        # Construir Prompt de Sistema
        system_prompt = f"""
Eres Integra Mind AI, el asistente experto y cerebro central de una plataforma de infraestructura crítica.
Tu objetivo es ayudar a los operadores a tomar decisiones, analizar datos y resolver problemas.

ESTADO ACTUAL DEL SISTEMA (ENERGÍA):
{status_text}
{pred_text}

{alert_text}

{kg_text}

INSTRUCCIONES:
1. Responde como un experto técnico pero accesible.
2. Usa los datos proporcionados arriba para fundamentar tus respuestas.
3. Si hay alertas críticas, prioriza mencionarlas si son relevantes.
4. Sé conciso, directo y útil.
5. Usa formato Markdown (negritas, listas) para claridad.
6. NO inventes datos numéricos que no estén en el contexto.

Responde a la siguiente consulta del operador:
"""
        return system_prompt

    def chat(self, user_message):
        """Genera respuesta usando el LLM local"""
        context = self._get_system_context()
        full_prompt = f"{context}\n\nOperador: {user_message}\nIntegra Mind AI:"
        
        print("🤔 Pensando...")
        
        try:
            # Llamada a Ollama (Stream desactivado para simplicidad en la API)
            response = requests.post(self.api_url, json={
                "model": self.model,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3, # Baja temperatura para respuestas más precisas/técnicas
                    "num_ctx": 4096
                }
            })
            
            if response.status_code == 200:
                return response.json().get('response', '')
            else:
                return f"Error del modelo (Status {response.status_code})"
                
        except Exception as e:
            return f"Error conectando con el cerebro LLM: {str(e)}"

# Prueba rápida si se ejecuta directo
if __name__ == "__main__":
    ai = IntegraMindOllama()
    print(ai.chat("Dame un resumen del estado actual"))
