"""
API Backend para Integra Mind Energy
Endpoints para dashboard de control operacional
"""

from flask import Flask, jsonify, request, Blueprint
from flask_cors import CORS
import sqlite3
from datetime import datetime, timedelta
import json
# Inicialización Robusta de Módulos (Evita crash si faltan dep or memoria)
DB_PATH = 'energy_demo.db'
ai_brain = None
weaver = None
predictive_engine = None

try:
    from integra_mind_ai_ollama import IntegraMindOllama
    from reality_weaver import RealityWeaver
    # pdf_report_generator se importa localmente
    from plc_bridge import plc_bridge 
    from predictive_engine import engine as predictive_engine_mod
    
    predictive_engine = predictive_engine_mod
    ai_brain = IntegraMindOllama(DB_PATH)
    weaver = RealityWeaver()
    print("✅ Modulos AI cargados correctamente")
except Exception as e:
    print(f"⚠️ Alerta: Ejecutando en modo limitado (AI no disponible): {e}")
    # plc_bridge puede ser None
    plc_bridge = None

# Transformar en Blueprint para integración con server.py
energy_bp = Blueprint('energy_api', __name__)
app = energy_bp  # Alias para mantener compatibilidad con decoradores @app.route

# --- GOD MODE SIMULATION STATE ---
# Estado global para coordinar simulaciones
SIMULATION_STATE = {
    "is_crisis_active": False,
    "crisis_type": None,  # 'overheat_reactor', 'pressure_leak'
    "target_asset": None
}

@app.route('/api/simulation/trigger-crisis', methods=['POST'])
def trigger_crisis():
    """GOD MODE: Iniciar una falla catastrófica simulada"""
    data = request.json
    SIMULATION_STATE["is_crisis_active"] = True
    SIMULATION_STATE["crisis_type"] = data.get('type', 'overheat_reactor')
    SIMULATION_STATE["target_asset"] = data.get('asset_id', 'Reactor-RX01')
    
    print(f"🔥 GOD MODE ACTIVATED: {SIMULATION_STATE['crisis_type']} on {SIMULATION_STATE['target_asset']}")
    return jsonify({"status": "CRITICAL_FAILURE_INITIATED", "state": SIMULATION_STATE})

@app.route('/api/simulation/resolve-crisis', methods=['POST'])
def resolve_crisis():
    """GOD MODE: La IA 'resuelve' la crisis"""
    SIMULATION_STATE["is_crisis_active"] = False
    SIMULATION_STATE["crisis_type"] = None
    
    print(f"✅ GOD MODE: Crisis Resolved")
    return jsonify({"status": "SYSTEM_STABILIZED", "state": SIMULATION_STATE})

@app.route('/api/simulation/status', methods=['GET'])
def get_simulation_status():
    """Obtener estado actual de la simulación"""
    return jsonify(SIMULATION_STATE)

@app.route('/api/ingest/stream', methods=['POST'])
def ingest_stream():
    """Endpoint para recibir datos en tiempo real de cualquier sensor"""
    data = request.json
    # data format: { "asset_id": "P-101", "metric": "pressure", "value": 150.5 }
    
    if not data:
        return jsonify({'error': 'No json data'}), 400

    result = weaver.process_live_packet(data)
    return jsonify(result)

@app.route('/api/plc/live-data', methods=['GET'])
def get_plc_live_data():
    """
    🏭 NUEVO: Obtiene datos en tiempo real del PLC Virtual vía Modbus.
    Este endpoint lee directamente de la 'máquina' industrial.
    """
    data = plc_bridge.read_reactor_data()
    
    if not data:
        return jsonify({
            'status': 'error',
            'message': 'No se puede conectar al PLC. ¿Está corriendo plc_simulator.py?',
            'connected': False
        }), 503
    
    # Retornar datos en formato compatible con el dashboard
    return jsonify({
        'status': 'ok',
        'connected': True,
        'timestamp': datetime.now().isoformat(),
        'plc_data': {
            'temperatura_reactor': data['temperatura_reactor_c'],
            'temperatura_unit': '°C',
            'presion_valvula': data['presion_valvula_psi'],
            'presion_unit': 'PSI',
            'turbina_estado': 'ON' if data['turbina_estado'] == 1 else 'OFF',
            'turbina_rpm': data['turbina_estado'] * 3600  # Simulado
        },
        'alerts': generate_plc_alerts(data)
    })

def generate_plc_alerts(plc_data):
    """Genera alertas basadas en los datos del PLC"""
    alerts = []
    
    temp = plc_data['temperatura_reactor_c']
    presion = plc_data['presion_valvula_psi']
    
    if temp > 400:
        alerts.append({
            'level': 'critical' if temp > 800 else 'warning',
            'message': f'🔥 Temperatura del reactor elevada: {temp}°C',
            'asset': 'Reactor-RX01'
        })
    
    if presion > 800:
        alerts.append({
            'level': 'critical',
            'message': f'💥 Presión peligrosa: {presion} PSI',
            'asset': 'Valve-Main'
        })
    
    if plc_data['turbina_estado'] == 0:
        alerts.append({
            'level': 'info',
            'message': '⚠️ Turbina detenida',
            'asset': 'Turbine-T01'
        })
    
    return alerts

@app.route('/api/predictive/analyze', methods=['GET'])
def get_predictive_analysis():
    """
    🤖 Motor Predictivo: Analiza datos del PLC y predice fallas
    """
    plc_data = plc_bridge.read_reactor_data()
    
    if not plc_data:
        return jsonify({'error': 'PLC no disponible'}), 503
    
    # Obtener predicción del motor ML
    prediction = predictive_engine.predict_anomaly(
        temperatura=plc_data['temperatura_reactor_c'],
        presion=plc_data['presion_valvula_psi'],
        rpm=plc_data['turbina_estado'] * 3600  # Simulado
    )
    
    # Obtener recomendación
    recommendation = predictive_engine.get_recommendation(prediction)
    
    return jsonify({
        'status': 'ok',
        'prediction': prediction,
        'recommendation': recommendation,
        'current_values': {
            'temperatura': plc_data['temperatura_reactor_c'],
            'presion': plc_data['presion_valvula_psi'],
            'turbina_rpm': plc_data['turbina_estado'] * 3600
        }
    })

def get_db():
    """Obtiene conexión a la base de datos"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/api/energy/current-status', methods=['GET'])
def get_current_status():
    """Obtiene estado actual del sistema"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Última lectura de demanda
    cursor.execute("""
        SELECT * FROM realtime_demand
        ORDER BY timestamp DESC
        LIMIT 1
    """)
    current = dict(cursor.fetchone())
    
    # Capacidad instalada
    cursor.execute("SELECT installed_capacity_mw FROM company_profile LIMIT 1")
    capacity = cursor.fetchone()[0]
    
    # Utilización
    utilization = (current['total_demand_mw'] / capacity) * 100
    
    conn.close()
    
    return jsonify({
        'current_demand_mw': round(current['total_demand_mw'], 2),
        'capacity_mw': capacity,
        'utilization_percent': round(utilization, 1),
        'frequency_hz': round(current['frequency_hz'], 2),
        'renewable_percent': round(current['renewable_percentage'], 1),
        'grid_losses_mw': round(current['grid_losses_mw'], 2),
        'status': 'normal' if utilization < 90 else 'high',
        'timestamp': current['timestamp']
    })

@app.route('/api/energy/demand-history', methods=['GET'])
def get_demand_history():
    """Obtiene histórico de demanda (últimas 24 horas)"""
    hours = request.args.get('hours', 24, type=int)
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT timestamp, total_demand_mw, renewable_generation_mw
        FROM realtime_demand
        ORDER BY timestamp DESC
        LIMIT ?
    """, (hours,))
    
    data = []
    for row in cursor.fetchall():
        data.append({
            'timestamp': row['timestamp'],
            'demand_mw': round(row['total_demand_mw'], 2),
            'renewable_mw': round(row['renewable_generation_mw'], 2)
        })
    
    conn.close()
    
    # Invertir para que esté en orden cronológico
    data.reverse()
    
    return jsonify(data)

@app.route('/api/energy/forecast', methods=['GET'])
def get_forecast():
    """Obtiene predicciones de demanda"""
    hours = request.args.get('hours', 6, type=int)
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Obtener predicciones más recientes
    cursor.execute("""
        SELECT 
            target_timestamp,
            predicted_demand_mw,
            confidence_lower_mw,
            confidence_upper_mw,
            confidence_score
        FROM demand_forecasts
        WHERE forecast_timestamp = (
            SELECT MAX(forecast_timestamp) FROM demand_forecasts
        )
        ORDER BY target_timestamp
        LIMIT ?
    """, (hours,))
    
    forecasts = []
    for row in cursor.fetchall():
        forecasts.append({
            'timestamp': row['target_timestamp'],
            'predicted_mw': round(row['predicted_demand_mw'], 2),
            'confidence_lower': round(row['confidence_lower_mw'], 2),
            'confidence_upper': round(row['confidence_upper_mw'], 2),
            'confidence': round(row['confidence_score'] * 100, 0)
        })
    
    conn.close()
    
    return jsonify(forecasts)

@app.route('/api/energy/alerts', methods=['GET'])
def get_alerts():
    """Obtiene alertas activas"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM alerts
        WHERE is_resolved = 0
        ORDER BY 
            CASE severity
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                ELSE 4
            END,
            created_at DESC
    """)
    
    alerts = []
    for row in cursor.fetchall():
        alerts.append({
            'id': row['id'],
            'type': row['alert_type'],
            'severity': row['severity'],
            'title': row['title'],
            'description': row['description'],
            'equipment_type': row['equipment_type'],
            'equipment_id': row['equipment_id'],
            'created_at': row['created_at'],
            'is_acknowledged': bool(row['is_acknowledged'])
        })
    
    conn.close()
    
    return jsonify(alerts)

@app.route('/api/energy/transformers', methods=['GET'])
def get_transformers():
    """Obtiene estado de transformadores"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            t.id,
            t.transformer_code,
            t.capacity_mva,
            t.health_score,
            t.status,
            s.name as substation_name,
            tm.oil_temperature_c,
            tm.load_percentage,
            tm.is_critical
        FROM transformers t
        LEFT JOIN substations s ON t.substation_id = s.id
        LEFT JOIN (
            SELECT transformer_id, oil_temperature_c, load_percentage, is_critical
            FROM transformer_metrics
            WHERE (transformer_id, timestamp) IN (
                SELECT transformer_id, MAX(timestamp)
                FROM transformer_metrics
                GROUP BY transformer_id
            )
        ) tm ON t.id = tm.transformer_id
    """)
    
    transformers = []
    for row in cursor.fetchall():
        transformers.append({
            'id': row['id'],
            'code': row['transformer_code'],
            'substation': row['substation_name'],
            'capacity_mva': row['capacity_mva'],
            'health_score': round(row['health_score'] * 100, 0) if row['health_score'] else 0,
            'status': row['status'],
            'temperature': round(row['oil_temperature_c'], 1) if row['oil_temperature_c'] else 0,
            'load_percent': round(row['load_percentage'], 1) if row['load_percentage'] else 0,
            'is_critical': bool(row['is_critical']) if row['is_critical'] is not None else False
        })
    
    conn.close()
    
    return jsonify(transformers)

@app.route('/api/energy/statistics', methods=['GET'])
def get_statistics():
    """Obtiene estadísticas del día"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Estadísticas de hoy
    today = datetime.now().date()
    cursor.execute("""
        SELECT * FROM daily_statistics
        WHERE stat_date = ?
    """, (today,))
    
    row = cursor.fetchone()
    
    if row:
        stats = {
            'date': row['stat_date'],
            'total_energy_mwh': round(row['total_energy_generated_mwh'], 2),
            'peak_demand_mw': round(row['peak_demand_mw'], 2),
            'average_demand_mw': round(row['average_demand_mw'], 2),
            'renewable_percent': round(row['renewable_percentage'], 1),
            'grid_losses_percent': round(row['grid_losses_percentage'], 1),
            'incidents_count': row['incidents_count']
        }
    else:
        # Si no hay datos de hoy, calcular en tiempo real
        cursor.execute("""
            SELECT 
                AVG(total_demand_mw) as avg_demand,
                MAX(total_demand_mw) as peak_demand,
                AVG(renewable_percentage) as renewable_pct,
                AVG(grid_losses_mw / total_demand_mw * 100) as losses_pct
            FROM realtime_demand
            WHERE DATE(timestamp) = ?
        """, (today,))
        
        row = cursor.fetchone()
        stats = {
            'date': str(today),
            'average_demand_mw': round(row['avg_demand'], 2) if row['avg_demand'] else 0,
            'peak_demand_mw': round(row['peak_demand'], 2) if row['peak_demand'] else 0,
            'renewable_percent': round(row['renewable_pct'], 1) if row['renewable_pct'] else 0,
            'grid_losses_percent': round(row['losses_pct'], 1) if row['losses_pct'] else 0,
            'incidents_count': 0
        }
    
    conn.close()
    
    return jsonify(stats)

@app.route('/api/energy/fraud-detections', methods=['GET'])
def get_fraud_detections():
    """Obtiene casos de fraude detectados"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            fd.id,
            c.customer_code,
            c.customer_type,
            fd.fraud_type,
            fd.confidence_score,
            fd.evidence,
            fd.estimated_loss_usd,
            fd.status,
            fd.detection_timestamp
        FROM fraud_detections fd
        LEFT JOIN customers c ON fd.customer_id = c.id
        ORDER BY fd.confidence_score DESC, fd.estimated_loss_usd DESC
        LIMIT 20
    """)
    
    detections = []
    for row in cursor.fetchall():
        detections.append({
            'id': row['id'],
            'customer_code': row['customer_code'],
            'customer_type': row['customer_type'],
            'fraud_type': row['fraud_type'],
            'confidence': round(row['confidence_score'] * 100, 0) if row['confidence_score'] else 0,
            'evidence': row['evidence'],
            'loss_usd': round(row['estimated_loss_usd'], 2) if row['estimated_loss_usd'] else 0,
            'status': row['status'],
            'detected_at': row['detection_timestamp']
        })
    
    conn.close()
    
    return jsonify(detections)

@app.route('/api/energy/ai-summary', methods=['GET'])
def get_ai_summary():
    """Obtiene resumen de módulos de IA"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Contar fraudes detectados
    cursor.execute("SELECT COUNT(*), SUM(estimated_loss_usd) FROM fraud_detections WHERE status = 'detected'")
    fraud_count, fraud_loss = cursor.fetchone()
    
    # Contar predicciones
    cursor.execute("SELECT COUNT(*) FROM demand_forecasts")
    forecast_count = cursor.fetchone()[0]
    
    # Contar alertas críticas
    cursor.execute("SELECT COUNT(*) FROM alerts WHERE severity = 'critical' AND is_resolved = 0")
    critical_alerts = cursor.fetchone()[0]
    
    conn.close()
    
    summary = {
        'demand_forecasting': {
            'status': 'operational',
            'accuracy': 98,
            'predictions_generated': forecast_count or 0,
            'daily_savings_usd': 45000
        },
        'fraud_detection': {
            'status': 'operational',
            'cases_detected': fraud_count or 0,
            'annual_loss_detected_usd': (fraud_loss * 12) if fraud_loss else 0,
            'confidence_avg': 92
        },
        'predictive_maintenance': {
            'status': 'operational',
            'critical_equipment': critical_alerts or 0,
            'potential_savings_usd': critical_alerts * 1300000 if critical_alerts else 0,
            'accuracy': 90
        },
        'total_annual_savings_usd': 19393946
    }
    
    return jsonify(summary)

@app.route('/api/chat', methods=['POST'])
def chat_endpoint():
    """Endpoint para conversar con la IA"""
    data = request.json
    message = data.get('message', '')
    
    if not message:
        return jsonify({'error': 'Message is required'}), 400
    
    try:
        # Consultar al cerebro
        response = ai_brain.chat(message)
        
        # Convertir saltos de línea y markdown básico a HTML simple para el frontend si fuera necesario,
        # pero el frontend manejará el markdown o texto plano mejor.
        # Por ahora enviamos texto plano enriquecido.
        
        return jsonify({
            'response': response,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"Error en chat: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/register-lead', methods=['POST'])
def register_lead():
    """Registra un nuevo interesado (Lead) desde la web"""
    data = request.json
    
    # Validaciones básicas
    if not data or not data.get('email'):
        return jsonify({'error': 'El email es obligatorio'}), 400
    
    try:
        # USAR POSTGRESQL
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from database_configuration import get_db_connection
        
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        
        print(f"🔵 Registrando lead en PostgreSQL: {data.get('email')}")
        
        cursor.execute("""
            INSERT INTO leads (name, email, company, role, interest)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (data.get('name'), data.get('email'), data.get('company'), data.get('role'), data.get('interest')))
        lead_id = cursor.fetchone()['id']
        
        conn.commit()
        conn.close()
        
        print(f"✅ Lead guardado con ID: {lead_id}")
        
        return jsonify({
            'success': True, 
            'message': 'Registro exitoso. ¡Gracias por tu interés!',
            'lead_id': lead_id
        })
        
    except Exception as e:
        try:
            with open('error_log.txt', 'a', encoding='utf-8') as f:
                f.write(f"ERROR REGISTRANDO LEAD: {str(e)}\n")
                import traceback
                traceback.print_exc(file=f)
        except:
            pass
        print(f"Error registrando lead: {e}")
        return jsonify({'error': 'Error interno al guardar datos'}), 500


# NOTA: Esta ruta está duplicada en server.py y causa conflictos
# Se comenta para usar la versión de server.py que tiene soporte para report_generated
"""
@app.route('/api/admin/leads', methods=['GET'])
def get_leads():
    \"\"\"Endpoint protegido para ver lista de leads\"\"\"
    # Simple Auth: Verificar Header 'X-Admin-Token'
    token = request.headers.get('X-Admin-Token')
    
    if token != 'INTEGRA2026': # Contraseña Maestra
        return jsonify({'error': 'Acceso Denegado: Contraseña Incorrecta'}), 401
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM leads ORDER BY created_at DESC")
        
        leads = []
        for row in cursor.fetchall():
            leads.append({
                'id': row['id'],
                'name': row['name'],
                'email': row['email'],
                'company': row['company'],
                'role': row['role'],
                'interest': row['interested_in'],
                'created_at': row['created_at']
            })
        
        conn.close()
        return jsonify(leads), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
"""


@app.route('/api/knowledge-graph', methods=['GET'])
def get_knowledge_graph():
    """Endpoint para visualizar el árbol de conocimiento universal"""
    try:
        conn = sqlite3.connect('knowledge_graph.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Obtener Nodos
        cursor.execute("SELECT id, name, type, description FROM entities")
        nodes = []
        for row in cursor.fetchall():
            # Asignar grupos/colores según tipo
            group = 'default'
            if 'pump' in row['name'].lower() or 'bomba' in row['type'].lower(): group = 'pump'
            if 'tank' in row['name'].lower() or 'tanque' in row['type'].lower(): group = 'tank'
            if 'sensor' in row['name'].lower(): group = 'sensor'
            if 'valve' in row['name'].lower(): group = 'valve'

            nodes.append({
                'id': row['id'], 
                'label': row['name'], 
                'title': row['description'], # Tooltip
                'group': group,
                'type': row['type']
            })
            
        # Obtener Relaciones (Si las hay - RealityWeaver v1 aún no infería relaciones complejas, 
        # pero podemos simular una estructura básica si está vacía o mostrar nodos sueltos)
        cursor.execute("SELECT source_id, target_id, relation_type FROM relationships")
        edges = []
        for row in cursor.fetchall():
            edges.append({
                'from': row['source_id'], 
                'to': row['target_id'],
                'label': row['relation_type']
            })
            
        conn.close()

        # === SIMULACIÓN OMNI-DATA PARA DEMO ===
        # Inyectamos nodos de diferentes fuentes para mostrar capacidad universal
        extra_nodes = [
            # Finanzas & ERP
            {'id': 'ERP-SAP', 'label': 'SAP Core', 'group': 'FINANCE', 'type': 'ERP'},
            {'id': 'Oracle-DB', 'label': 'Oracle HR', 'group': 'FINANCE', 'type': 'DB'},
            
            # Datos Externos & Mercado
            {'id': 'Weather-API', 'label': 'NOAA Sat', 'group': 'EXTERNAL', 'type': 'API'},
            {'id': 'Market-Spot', 'label': 'Energy Price', 'group': 'EXTERNAL', 'type': 'MARKET'},
            {'id': 'Forex-Feed', 'label': 'USD/EUR', 'group': 'EXTERNAL', 'type': 'FOREX'},
            
            # Documentos
            {'id': 'Doc-Manuals', 'label': 'Tech PDFs', 'group': 'DOCUMENT', 'type': 'DOCS'},
            {'id': 'Legal-Contracts', 'label': 'Contracts', 'group': 'DOCUMENT', 'type': 'PDF'},
            
            # Social & Colaboración
            {'id': 'Slack-Bot', 'label': 'Dev Ops Chat', 'group': 'SOCIAL', 'type': 'CHAT'},
            {'id': 'Email-Server', 'label': 'Corp Mail', 'group': 'SOCIAL', 'type': 'MAIL'},
            
            # Seguridad Física
            {'id': 'CCTV-Main', 'label': 'Main Gate Cam', 'group': 'PRODUCER', 'type': 'CAM'},
            {'id': 'Access-Control', 'label': 'Biometrics', 'group': 'PRODUCER', 'type': 'SEC'},
            
            # Logística
            {'id': 'Fleet-GPS', 'label': 'Truck #402', 'group': 'CONSUMER', 'type': 'GPS'},
            {'id': 'Warehouse-IoT', 'label': 'Stock Sensor', 'group': 'CONSUMER', 'type': 'IOT'},

            # El Cerebro
            {'id': 'Grid-Controller', 'label': 'NEURAL CORE', 'group': 'CORE', 'type': 'AI'}
        ]
        
        for node in extra_nodes:
            nodes.append(node)
            # Conectamos todo al "Cerebro Central" simulado
            edges.append({'source': node['id'], 'target': 'Grid-Controller', 'label': 'INGEST'})
            
            # Conexiones aleatorias a nodos existentes para simular fusión de datos
            import random
            if len(nodes) > 5:
                random_target = nodes[random.randint(0, len(nodes)-6)]['id']
                edges.append({'source': node['id'], 'target': random_target, 'label': 'CORRELATE'})

        return jsonify({'nodes': nodes, 'edges': edges})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

from email_sender import send_report_to_client

@app.route('/api/admin/generate-report', methods=['POST'])
def generate_executive_report():
    """Generar reporte ejecutivo PDF para un lead/cliente"""
    # Verificar autenticación
    token = request.headers.get('X-Admin-Token')
    if token != 'INTEGRA2026':
        return jsonify({'error': 'Acceso Denegado'}), 401
    
    data = request.json
    client_name = data.get('client_name', 'Cliente Prospecto')
    industry = data.get('industry', 'Energy')
    lead_id = data.get('lead_id')
    should_send_email = data.get('send_email', False)
    
    try:
        # Generar reporte
        from pdf_report_generator import generate_client_report
        report_path = generate_client_report(client_name, industry, lead_id)
        
        email_status = "No solicitado"
        
        # Enviar email si se solicita y hay lead_id
        if should_send_email and lead_id:
            try:
                # Usar PostgreSQL/SQLite vía db_config
                import sys
                import os
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                from database_configuration import get_db_connection
                
                conn, db_type = get_db_connection()
                cursor = conn.cursor()
                
                try:
                    lead_id = int(lead_id) # Forzar conversión a int
                except:
                    print(f"⚠️ Error convirtiendo lead_id '{lead_id}' a int")

                print(f"🔍 Buscando email para Lead ID: {lead_id} (Tipo: {type(lead_id)}) en DB: {db_type}")
                
                # Debug: Listar TODOS los IDs y emails para ver si el 9 existe
                cursor.execute("SELECT id, email FROM leads")
                all_leads = cursor.fetchall()
                print(f"📊 Leads disponibles en DB ({len(all_leads)}): {all_leads}")

                cursor.execute("SELECT email FROM leads WHERE id = %s", (lead_id,))
                row = cursor.fetchone()
                
                print(f"📝 Resultado consulta específica para ID {lead_id}: {row}")
                
                client_email = row['email'] if row else None
                
                conn.close()
                
                if client_email:
                    print(f"📧 Enviando reporte a: {client_email}")
                    from email_sender import send_report_to_client
                    email_result = send_report_to_client(
                        client_email, 
                        client_name, 
                        industry, 
                        report_path
                    )
                    
                    if email_result:
                        email_status = "Enviado con éxito"
                        
                        # Actualizar estado en DB
                        try:
                            conn, db_type = get_db_connection()
                            cursor = conn.cursor()
                            now = datetime.now()
                            
                            cursor.execute("""
                                UPDATE leads 
                                SET report_generated = 1, 
                                    report_sent_at = %s,
                                    report_file_path = %s
                                WHERE id = %s
                            """, (now, report_path, lead_id))
                            
                            conn.commit()
                            conn.close()
                        except Exception as e:
                            print(f"⚠️ Error actualizando estado en DB: {e}")
                            
                    else:
                        email_status = "Fallo envío SMTP"
                else:
                    email_status = f"Email no encontrado en DB (lead_id={lead_id})"
                    print(f"⚠️ No se encontró email para lead_id={lead_id}")
                    
            except Exception as email_err:
                print(f"❌ Error proceso email: {email_err}")
                import traceback
                traceback.print_exc()
                email_status = f"Error: {str(email_err)}"
        
        return jsonify({
            'success': True,
            'message': 'Reporte generado exitosamente',
            'file_path': report_path,
            'download_url': f'/reports/{os.path.basename(report_path)}',
            'email_status': email_status
        })
    except Exception as e:
        print(f"❌ Error generando reporte: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/lead/<int:lead_id>', methods=['DELETE'])
def delete_lead(lead_id):
    """Eliminar un lead por ID"""
    token = request.headers.get('X-Admin-Token')
    if token != 'INTEGRA2026':
        return jsonify({'error': 'Acceso Denegado'}), 401
        
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from db_config import get_db_connection
        
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        
        if db_type == 'postgresql':
            cursor.execute("DELETE FROM leads WHERE id = %s", (lead_id,))
        else:
            cursor.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
            
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': f'Lead {lead_id} eliminado'})
    except Exception as e:
        print(f"Error eliminando lead: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/list-reports', methods=['GET'])
def list_reports():
    """Listar todos los reportes generados"""
    token = request.headers.get('X-Admin-Token')
    if token != 'INTEGRA2026':
        return jsonify({'error': 'Acceso Denegado'}), 401
    
    try:
        import os
        reports_dir = 'reports'
        
        if not os.path.exists(reports_dir):
            return jsonify({'reports': []})
        
        reports = []
        for filename in os.listdir(reports_dir):
            if filename.endswith('.pdf'):
                filepath = os.path.join(reports_dir, filename)
                stat = os.stat(filepath)
                reports.append({
                    'filename': filename,
                    'name': filename.replace('Executive_Report_', '').replace('.pdf', '').replace('_', ' '),
                    'size': stat.st_size,
                    'created': stat.st_mtime
                })
        
        # Ordenar por fecha de creación (más reciente primero)
        reports.sort(key=lambda x: x['created'], reverse=True)
        
        return jsonify({'reports': reports})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/reports/<filename>')
def serve_report(filename):
    """Servir archivos PDF generados"""
    from flask import send_from_directory
    import os
    return send_from_directory(os.path.join(os.getcwd(), 'reports'), filename)

if __name__ == '__main__':
    # Modo Standalone para pruebas
    test_app = Flask(__name__, static_folder='web', static_url_path='')
    CORS(test_app)
    test_app.register_blueprint(energy_bp)
    
    print("⚡ Iniciando API de Integra Mind Energy (Modo Test)...")
    print("📡 Servidor corriendo en http://localhost:5001")
    test_app.run(host='0.0.0.0', port=5001, debug=True)
