from __future__ import annotations

import os
import json
import sqlite3
from typing import List, Dict
from flask import Flask, request, jsonify, Response, send_from_directory, stream_with_context
from pydantic import ValidationError
import logging

# Finance Module
from chat_ai.finance import finance_manager, AccountCreate, TransactionCreate

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, 'web')
DB_PATH = os.path.join(BASE_DIR, 'users.sqlite')
INDEX_DIR = os.path.join(BASE_DIR, 'index_store')



def ensure_db():
    from db_config import ensure_tables
    ensure_tables()



app = Flask(__name__, static_folder=None)

# Registrar Blueprint del Módulo de Energía
try:
    from energy_api import energy_bp
    app.register_blueprint(energy_bp)
    print("✅ Módulo de Energía integrado correctamente")
except Exception as e:
    print(f"⚠️ Advertencia: No se pudo cargar el módulo de energía: {e}")

# ============================================
# CORS CONFIGURATION
# ============================================
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-Admin-Token')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# ============================================
# SECURITY SYSTEM INTEGRATION
# ============================================
try:
    from security_api import security_bp
    app.register_blueprint(security_bp)
    logger.info("✅ Security system integrated successfully")
except ImportError as e:
    logger.warning(f"⚠️  Security system not available: {e}")
except Exception as e:
    logger.error(f"❌ Error integrating security system: {e}")
# ============================================

# Brain instances cache by user_id
brain_instances = {}
ensure_db()

def get_brain(user_id: str = "anonymous") -> 'chat_ai.brain.Brain':
    """Return a Brain instance for the given user, creating it lazily on first use.
    
    Each user gets their own Brain instance with separate enhanced memory.
    """
    global brain_instances
    
    if user_id not in brain_instances:
        # Lazily import to avoid heavy imports during module import
        from chat_ai.brain import Brain
        brain_instances[user_id] = Brain(
            storage_dir=INDEX_DIR, 
            prefer_faiss=True,
            user_id=user_id,
            db_path=DB_PATH  # Use same DB for all users
        )
        logger.info(f"Created Brain instance for user: {user_id}")
    
    return brain_instances[user_id]



def load_profile(user_id: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT profile_json FROM profiles WHERE user_id=?", (user_id,))
        row = cur.fetchone()
        if not row:
            return {}
        try:
            return json.loads(row[0]) if row[0] else {}
        except Exception:
            return {}
    finally:
        conn.close()


@app.route('/')
def index():
    return send_from_directory(WEB_DIR, 'index.html')

# Catch-all for other static files (html, js, css, png, etc.)
# This ensures that admin.html, admin_simple.html, styles.css, etc. are all served correctly
@app.route('/<path:filename>')
def serve_web_files(filename):
    return send_from_directory(WEB_DIR, filename)

@app.route('/static/<path:filename>')
def static_files_legacy(filename):
    return send_from_directory(WEB_DIR, filename)

@app.route('/reports/<path:filename>')
def serve_report(filename):
    """Serve generated PDF reports"""
    reports_dir = os.path.join(BASE_DIR, 'reports')
    return send_from_directory(reports_dir, filename)

# ============================================
# LEGACY ADMIN ROUTES (Compatibility)
# ============================================
ADMIN_TOKEN = "INTEGRA2026"

@app.route('/api/admin/leads', methods=['GET'])
def get_leads_legacy():
    token = request.headers.get('X-Admin-Token')
    if token != ADMIN_TOKEN:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Get real leads from database
    try:
        from db_config import get_db_connection
        conn, db_type = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, name, email, company, role, interest, created_at,
                   report_generated, report_sent_at, report_file_path
            FROM leads
            ORDER BY created_at DESC
        """)
        
        leads = []
        for row in cur.fetchall():
            if db_type == 'postgresql':
                # PostgreSQL returns dict-like rows
                lead_dict = dict(row)
            else:
                # SQLite Row object
                lead_dict = {
                    'id': row['id'],
                    'name': row['name'],
                    'email': row['email'],
                    'company': row['company'],
                    'role': row['role'],
                    'interest': row['interest'],
                    'created_at': row['created_at'],
                    'report_generated': row['report_generated'] or 0,
                    'report_sent_at': row['report_sent_at'],
                    'report_file_path': row['report_file_path']
                }
            
            leads.append(lead_dict)
        
        conn.close()
        return jsonify(leads)
        
    except Exception as e:
        logger.error(f"Error fetching leads: {str(e)}")
        # Return empty list if table doesn't exist yet
        return jsonify([])

@app.route('/api/admin/generate-report', methods=['POST'])
def generate_report_legacy():
    token = request.headers.get('X-Admin-Token')
    if token != ADMIN_TOKEN:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        from pdf_report_generator import generate_client_report
        from email_sender import send_report_to_client
        
        data = request.json
        client_name = data.get('client_name', 'Cliente')
        industry = data.get('industry', 'Energy & Utilities')
        lead_id = data.get('lead_id')
        send_email = data.get('send_email', False)
        
        # Generate PDF using existing generator
        pdf_path = generate_client_report(client_name, industry, lead_id)
        pdf_filename = os.path.basename(pdf_path)
        
        logger.info(f"Report generated: {pdf_path}")
        
        # Send email if requested
        email_status = "No solicitado"
        report_sent = False
        
        if send_email and lead_id:
            try:
                # Get lead email from database
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute("SELECT email, name FROM leads WHERE id = ?", (lead_id,))
                lead = cur.fetchone()
                conn.close()
                
                if lead:
                    recipient_email = lead[0]
                    recipient_name = lead[1]
                    
                    # Send email using existing email_sender module
                    success = send_report_to_client(
                        recipient_email, 
                        recipient_name, 
                        client_name, 
                        pdf_path
                    )
                    
                    if success:
                        email_status = f"✅ Enviado a {recipient_email}"
                        report_sent = True
                        logger.info(f"Email sent to {recipient_email}")
                    else:
                        email_status = "⚠️ Error al enviar email (ver logs)"
                else:
                    email_status = "❌ Lead no encontrado"
            except Exception as e:
                email_status = f"❌ Error: {str(e)}"
                logger.error(f"Error sending email: {str(e)}")
        
        # Update lead record with report status
        if lead_id:
            try:
                from datetime import datetime
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                
                if report_sent:
                    # Mark as generated and sent
                    cur.execute("""
                        UPDATE leads 
                        SET report_generated = 1, 
                            report_sent_at = ?, 
                            report_file_path = ?
                        WHERE id = ?
                    """, (datetime.now().isoformat(), pdf_path, lead_id))
                else:
                    # Mark as generated only (not sent)
                    cur.execute("""
                        UPDATE leads 
                        SET report_generated = 1, 
                            report_file_path = ?
                        WHERE id = ?
                    """, (pdf_path, lead_id))
                
                conn.commit()
                conn.close()
                logger.info(f"Lead {lead_id} updated with report status")
            except Exception as e:
                logger.error(f"Error updating lead status: {str(e)}")
        
        return jsonify({
            'message': '✅ Reporte generado correctamente',
            'file_path': pdf_path,
            'email_status': email_status,
            'download_url': f'/reports/{pdf_filename}'
        })
        
    except Exception as e:
        logger.error(f"Error generating report: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============================================
# BULK REPORT SENDING
# ============================================
@app.route('/api/admin/send-all-reports', methods=['POST'])
def send_all_reports():
    """Generate and send reports to all leads that haven't received them"""
    token = request.headers.get('X-Admin-Token')
    if token != ADMIN_TOKEN:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        from pdf_report_generator import generate_client_report
        from email_sender import send_report_to_client
        from datetime import datetime
        
        # Get all leads that haven't received reports
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, name, email, company, role, interest
            FROM leads
            WHERE report_generated = 0 OR report_sent_at IS NULL
            ORDER BY created_at ASC
        """)
        
        pending_leads = cur.fetchall()
        conn.close()
        
        if not pending_leads:
            return jsonify({
                'message': 'No hay leads pendientes de envío',
                'total': 0,
                'sent': 0,
                'skipped': 0,
                'errors': 0
            })
        
        sent_count = 0
        error_count = 0
        
        logger.info(f"Starting bulk report sending for {len(pending_leads)} leads")
        
        for lead in pending_leads:
            try:
                lead_id = lead['id']
                client_name = lead['name']
                company = lead['company'] or 'Empresa'
                email = lead['email']
                
                # Generate PDF
                pdf_path = generate_client_report(client_name, 'Energy & Utilities', lead_id)
                logger.info(f"Generated report for {client_name}: {pdf_path}")
                
                # Send email
                success = send_report_to_client(email, client_name, company, pdf_path)
                
                # Update database
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                
                if success:
                    cur.execute("""
                        UPDATE leads 
                        SET report_generated = 1, 
                            report_sent_at = ?, 
                            report_file_path = ?
                        WHERE id = ?
                    """, (datetime.now().isoformat(), pdf_path, lead_id))
                    sent_count += 1
                    logger.info(f"✅ Report sent to {email}")
                else:
                    # Mark as generated but not sent
                    cur.execute("""
                        UPDATE leads 
                        SET report_generated = 1, 
                            report_file_path = ?
                        WHERE id = ?
                    """, (pdf_path, lead_id))
                    error_count += 1
                    logger.warning(f"⚠️ Report generated but not sent to {email}")
                
                conn.commit()
                conn.close()
                
            except Exception as e:
                error_count += 1
                logger.error(f"❌ Error processing lead {lead['name']}: {str(e)}")
                continue
        
        return jsonify({
            'message': 'Proceso de envío masivo completado',
            'total': len(pending_leads),
            'sent': sent_count,
            'skipped': 0,
            'errors': error_count
        })
        
    except Exception as e:
        logger.error(f"Error in bulk sending: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============================================
# LEAD REGISTRATION (Contact Form)
# ============================================
@app.route('/api/register-lead', methods=['POST'])
def register_lead():
    """Register a new lead from the contact form"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['name', 'email', 'company', 'role', 'interest']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Store in database
        from db_config import get_db_connection
        conn, db_type = get_db_connection()
        cur = conn.cursor()
        
        # Insert lead (PostgreSQL and SQLite compatible)
        if db_type == 'postgresql':
            cur.execute("""
                INSERT INTO leads (name, email, company, role, interest)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (data['name'], data['email'], data['company'], data['role'], data['interest']))
            lead_id = cur.fetchone()[0]
        else:
            cur.execute("""
                INSERT INTO leads (name, email, company, role, interest)
                VALUES (?, ?, ?, ?, ?)
            """, (data['name'], data['email'], data['company'], data['role'], data['interest']))
            lead_id = cur.lastrowid
        
        conn.commit()
        conn.close()
        
        logger.info(f"New lead registered: {data['name']} ({data['email']})")
        
        return jsonify({
            'success': True,
            'message': 'Lead registered successfully',
            'lead_id': lead_id
        }), 201
        
    except Exception as e:
        logger.error(f"Error registering lead: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# ============================================

@app.route('/docs_list', methods=['GET'])
def docs_list():
    docs = []
    # Show up to 50 snippet docs
    b = get_brain()
    for meta, text in zip(b._corpus_metas[:50], b._corpus_texts[:50]):
        docs.append({
            'id': meta.get('id', ''),
            'source': meta.get('source', ''),
            'text': text[:200] + ('...' if len(text) > 200 else ''),
        })
    return jsonify({'docs': docs})


@app.route('/ingest', methods=['POST'])
def ingest():
    data = request.get_json(force=True, silent=True) or {}
    
    # Handle raw_docs (Experience Objects or batch ingest)
    if 'raw_docs' in data and isinstance(data['raw_docs'], list):
        n = get_brain().ingest_raw(data['raw_docs'], chunk_chars=800, overlap=150)
        return jsonify({'status': 'ok', 'chunks': n})
        
    # Handle simple text ingest
    source = data.get('source', 'web_input')
    text = data.get('text', '')
    if not text:
        return jsonify({'status': 'no_text'}), 400
    n = get_brain().ingest_raw([{'source': source, 'text': text}], chunk_chars=800, overlap=150)
    return jsonify({'status': 'ok', 'chunks': n})


@app.route('/chat_stream', methods=['POST'])
def chat_stream():
    data = request.get_json(force=True, silent=True) or {}
    question = data.get('question', '')
    topk = int(data.get('topk', 5))
    user_id = data.get('user_id', 'anonymous')
    conversation_id = data.get('conversation_id')  # Optional conversation ID
    
    if not question:
        return jsonify({'error': 'no_question'}), 400
    
    profile = load_profile(user_id)
    tone = (profile.get('tone') if isinstance(profile, dict) else None) or 'neutral'
    prefs = profile.get('prefs') if isinstance(profile, dict) else None
    
    # Get Brain instance for this user
    brain = get_brain(user_id)
    
    # Produce answer once, then stream by chunks
    # True streaming
    try:
        gen, refs = brain.ask(
            question, 
            top_k=topk, 
            tone=tone, 
            prefs=prefs if isinstance(prefs, dict) else None, 
            stream=True,
            conversation_id=conversation_id
        )
    except Exception:
        # Fallback to non-streaming if error
        result = brain.ask(
            question, 
            top_k=topk, 
            tone=tone, 
            prefs=prefs if isinstance(prefs, dict) else None, 
            stream=False,
            conversation_id=conversation_id
        )
        gen = iter([result.get('answer', '')])
        refs = result.get('references', [])

    def generate():
        full_answer = []
        try:
            for chunk in gen:
                if chunk:
                    full_answer.append(chunk)
                    yield chunk
        except Exception:
            pass
        finally:
            # Persist Q/A log (best-effort) after stream ends
            try:
                ans_str = "".join(full_answer)
                src = ''
                url = ''
                learned = 0
                for r in refs:
                    if isinstance(r.get('id'), str) and r.get('id','').startswith('wikipedia::'):
                        src = r.get('source','')
                        url = r.get('url','')
                        learned = 1
                        break
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO qa_log(user_id, question, answer, source, url, learned) VALUES(?,?,?,?,?,?)",
                    (user_id, question, ans_str[:4000], src, url, learned),
                )
                conn.commit(); conn.close()
            except Exception:
                pass

    resp = Response(stream_with_context(generate()), mimetype='text/plain')
    # Encourage proxies/browsers to deliver chunks immediately
    resp.headers['Cache-Control'] = 'no-cache'
    resp.headers['X-Accel-Buffering'] = 'no'
    return resp


@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json(force=True, silent=True) or {}
    question = data.get('question', '')
    topk = int(data.get('topk', 5))
    user_id = data.get('user_id', 'anonymous')
    conversation_id = data.get('conversation_id')  # Optional conversation ID
    
    if not question:
        return jsonify({'error': 'no_question'}), 400
    
    profile = load_profile(user_id)
    tone = (profile.get('tone') if isinstance(profile, dict) else None) or 'neutral'
    prefs = profile.get('prefs') if isinstance(profile, dict) else None
    
    # Get Brain instance for this user
    brain = get_brain(user_id)
    
    result = brain.ask(
        question, 
        top_k=topk, 
        tone=tone, 
        prefs=prefs if isinstance(prefs, dict) else None,
        conversation_id=conversation_id
    )
    
    refs = result.get('references', [])
    contexts: List[Dict[str, str]] = []
    for r in refs:
        # Preserve ALL fields from the reference to include custom metadata
        contexts.append(r)
    # Persist Q/A log (best-effort)
    try:
        src = ''
        url = ''
        learned = 0
        for r in refs or []:
            if isinstance(r.get('id'), str) and r.get('id','').startswith('wikipedia::'):
                src = r.get('source','')
                url = r.get('url','')
                learned = 1
                break
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO qa_log(user_id, question, answer, source, url, learned) VALUES(?,?,?,?,?,?)",
            (user_id, question, (result.get('answer','') or '')[:4000], src, url, learned),
        )
        conn.commit(); conn.close()
    except Exception:
        pass
    
    # Include projection if present
    response_data = {
        'answer': result.get('answer', ''), 
        'contexts': contexts
    }
    if result.get('projection'):
        response_data['projection'] = result.get('projection')
    
    # Include Knowledge Graph information if available (mejorado)
    if hasattr(brain, 'knowledge_graph') and brain.knowledge_graph:
        try:
            kg_info = {}
            
            # Get solution paths for the question (mejorado con más profundidad)
            kg_paths = brain.knowledge_graph.find_solution_path(question, max_depth=4)
            if kg_paths:
                # Formatear caminos de forma más legible
                formatted_paths = []
                for path_data in kg_paths[:2]:  # Top 2 paths
                    path = path_data.get('path', [])
                    sequence = path_data.get('sequence', [])
                    formatted_path = {
                        'steps': [
                            {
                                'step': step.get('step', i+1),
                                'type': step.get('node', {}).get('type', ''),
                                'label': step.get('node', {}).get('label', ''),
                                'description': step.get('node', {}).get('description', '')[:150],
                                'relation': step.get('relation', '')
                            }
                            for i, step in enumerate(path)
                        ],
                        'length': path_data.get('length', len(path)),
                        'score': path_data.get('score', 0.0),
                        'summary': ' → '.join(sequence[:5])  # Resumen legible
                    }
                    formatted_paths.append(formatted_path)
                
                kg_info['solution_paths'] = formatted_paths
                kg_info['has_paths'] = True
            
            # Get related problems, tools, and actions
            problem_nodes = brain.knowledge_graph.find_nodes(question, node_type="problem", limit=3)
            tool_nodes = brain.knowledge_graph.find_nodes(question, node_type="tool", limit=3)
            action_nodes = brain.knowledge_graph.find_nodes(question, node_type="action", limit=3)
            
            if problem_nodes or tool_nodes or action_nodes:
                if problem_nodes:
                    kg_info['related_problems'] = [
                        {
                            'label': node.label,
                            'description': node.description[:200] if node.description else '',
                            'id': node.id
                        }
                        for node in problem_nodes
                    ]
                if tool_nodes:
                    kg_info['related_tools'] = [
                        {
                            'label': node.label,
                            'description': node.description[:150] if node.description else '',
                            'id': node.id
                        }
                        for node in tool_nodes
                    ]
                if action_nodes:
                    kg_info['related_actions'] = [
                        {
                            'label': node.label,
                            'description': node.description[:150] if node.description else '',
                            'id': node.id
                        }
                        for node in action_nodes
                    ]
            
            # Estadísticas del grafo
            stats = brain.knowledge_graph.get_statistics()
            kg_info['graph_stats'] = {
                'total_nodes': stats['total_nodes'],
                'total_edges': stats['total_edges']
            }
            
            if kg_info:
                response_data['knowledge_graph'] = kg_info
                
        except Exception as e:
            logger.warning(f"Error getting Knowledge Graph info: {e}")
        
    return jsonify(response_data)



@app.route('/feedback', methods=['POST'])
def feedback():
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get('user_id', 'anonymous')
    doc_id = data.get('doc_id', '')
    helpful = 1 if data.get('helpful', False) else 0
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO feedback(user_id, doc_id, helpful) VALUES(?,?,?)",
            (user_id, doc_id, helpful),
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({'status': 'ok'})


@app.route('/purge_sources', methods=['POST'])
def purge_sources():
    data = request.get_json(force=True, silent=True) or {}
    patterns = data.get('patterns') or []
    if not isinstance(patterns, list) or not patterns:
        return jsonify({'error': 'patterns required (e.g., ["wikipedia:*"] )'}), 400
    removed = get_brain().remove_sources([str(p) for p in patterns])
    return jsonify({'status': 'ok', 'removed': removed})


@app.route('/profile', methods=['POST'])
def save_profile():
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get('user_id', 'anonymous')
    profile_json = data.get('profile_json', '{}')
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO profiles(user_id, profile_json) VALUES(?, ?) ON CONFLICT(user_id) DO UPDATE SET profile_json=excluded.profile_json",
            (user_id, profile_json),
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({'status': 'ok'})


@app.route('/profile/<user_id>', methods=['GET'])
def get_profile(user_id: str):
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT profile_json FROM profiles WHERE user_id=?", (user_id,))
        row = cur.fetchone()
    finally:
        conn.close()
    return jsonify({'user_id': user_id, 'profile': row[0] if row else '{}'})


@app.route('/conversations', methods=['GET'])
def get_conversations():
    user_id = request.args.get('user_id', 'anonymous')
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, title, created_at, updated_at 
               FROM conversations 
               WHERE user_id=? 
               ORDER BY updated_at DESC 
               LIMIT ? OFFSET ?""",
            (user_id, limit, offset)
        )
        rows = cur.fetchall()
        conversations = []
        for row in rows:
            conversations.append({
                'id': row[0],
                'title': row[1],
                'created_at': row[2],
                'updated_at': row[3]
            })
    finally:
        conn.close()
    return jsonify({'conversations': conversations})


@app.route('/conversation/<int:conv_id>', methods=['GET'])
def get_conversation(conv_id: int):
    user_id = request.args.get('user_id', 'anonymous')
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, user_id, title, created_at FROM conversations WHERE id=?", (conv_id,))
        conv_row = cur.fetchone()
        if not conv_row:
            return jsonify({'error': 'not_found'}), 404
        
        # Check ownership
        if conv_row[1] != user_id:
            return jsonify({'error': 'forbidden'}), 403
        
        cur.execute(
            "SELECT id, role, content, timestamp FROM messages WHERE conversation_id=? ORDER BY timestamp ASC",
            (conv_id,)
        )
        msg_rows = cur.fetchall()
        messages = []
        for row in msg_rows:
            messages.append({
                'id': row[0],
                'role': row[1],
                'content': row[2],
                'timestamp': row[3]
            })
    finally:
        conn.close()
    
    return jsonify({
        'id': conv_row[0],
        'user_id': conv_row[1],
        'title': conv_row[2],
        'created_at': conv_row[3],
        'messages': messages
    })


@app.route('/conversation', methods=['POST'])
def create_conversation():
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get('user_id', 'anonymous')
    title = data.get('title', 'Nueva conversación')
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO conversations(user_id, title) VALUES(?, ?)",
            (user_id, title)
        )
        conv_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    
    return jsonify({'status': 'ok', 'conversation_id': conv_id})


@app.route('/conversation/<int:conv_id>/message', methods=['POST'])
def add_message(conv_id: int):
    data = request.get_json(force=True, silent=True) or {}
    role = data.get('role', 'user')
    content = data.get('content', '')
    user_id = data.get('user_id', 'anonymous')
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        # Verify conversation ownership
        cur.execute("SELECT user_id FROM conversations WHERE id=?", (conv_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'not_found'}), 404
        if row[0] != user_id:
            return jsonify({'error': 'forbidden'}), 403
            
        cur.execute(
            "INSERT INTO messages(conversation_id, role, content) VALUES(?, ?, ?)",
            (conv_id, role, content)
        )
        msg_id = cur.lastrowid
        # Update conversation timestamp
        cur.execute(
            "UPDATE conversations SET updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (conv_id,)
        )
        conn.commit()
    finally:
        conn.close()
    
    return jsonify({'status': 'ok', 'message_id': msg_id})


@app.route('/conversation/<int:conv_id>', methods=['DELETE'])
def delete_conversation(conv_id: int):
    user_id = request.args.get('user_id', 'anonymous')
    # Also check JSON body just in case, though DELETE usually doesn't have body
    if not user_id or user_id == 'anonymous':
        data = request.get_json(force=True, silent=True) or {}
        if data.get('user_id'):
            user_id = data.get('user_id')

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        # Verify ownership
        cur.execute("SELECT user_id FROM conversations WHERE id=?", (conv_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'not_found'}), 404
        if row[0] != user_id:
            return jsonify({'error': 'forbidden'}), 403

        cur.execute("DELETE FROM messages WHERE conversation_id=?", (conv_id,))
        cur.execute("DELETE FROM conversations WHERE id=?", (conv_id,))
        conn.commit()
    finally:
        conn.close()
    
    return jsonify({'status': 'ok'})


@app.route('/export_conversation/<int:conv_id>', methods=['GET'])
def export_conversation(conv_id: int):
    format_type = request.args.get('format', 'json')
    user_id = request.args.get('user_id', 'anonymous')
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT title, created_at, user_id FROM conversations WHERE id=?", (conv_id,))
        conv_row = cur.fetchone()
        if not conv_row:
            return jsonify({'error': 'not_found'}), 404
        
        # Check ownership
        if conv_row[2] != user_id:
            return jsonify({'error': 'forbidden'}), 403
        
        cur.execute(
            "SELECT role, content, timestamp FROM messages WHERE conversation_id=? ORDER BY timestamp ASC",
            (conv_id,)
        )
        msg_rows = cur.fetchall()
    finally:
        conn.close()
    
    if format_type == 'json':
        messages = [{'role': r[0], 'content': r[1], 'timestamp': r[2]} for r in msg_rows]
        return jsonify({
            'title': conv_row[0],
            'created_at': conv_row[1],
            'messages': messages
        })
    elif format_type == 'txt':
        lines = [f"Conversación: {conv_row[0]}", f"Fecha: {conv_row[1]}", "=" * 60, ""]
        for r in msg_rows:
            lines.append(f"[{r[2]}] {r[0].upper()}: {r[1]}")
            lines.append("")
        return Response('\n'.join(lines), mimetype='text/plain')
    else:
        return jsonify({'error': 'invalid_format'}), 400


@app.route('/search_history', methods=['POST'])
def search_history():
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get('user_id', 'anonymous')
    query = data.get('query', '')
    
    if not query:
        return jsonify({'results': []})
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        # Simple text search - could be enhanced with embeddings
        cur.execute(
            """SELECT DISTINCT c.id, c.title, c.updated_at
               FROM conversations c
               JOIN messages m ON c.id = m.conversation_id
               WHERE c.user_id=? AND (m.content LIKE ? OR c.title LIKE ?)
               ORDER BY c.updated_at DESC
               LIMIT 20""",
            (user_id, f'%{query}%', f'%{query}%')
        )
        rows = cur.fetchall()
        results = []
        for row in rows:
            results.append({
                'id': row[0],
                'title': row[1],
                'updated_at': row[2]
            })
    finally:
        conn.close()
    
    return jsonify({'results': results})


@app.route('/suggest_questions', methods=['POST'])
def suggest_questions():
    data = request.get_json(force=True, silent=True) or {}
    context = data.get('context', '')
    
    # Generate suggestions based on context
    suggestions = [
        "¿Puedes explicar más sobre esto?",
        "¿Cuáles son las ventajas y desventajas?",
        "Dame un ejemplo práctico",
        "¿Cómo puedo aplicar esto?"
    ]
    
    # Could use the brain to generate smarter suggestions
    # For now, return generic helpful questions
    return jsonify({'suggestions': suggestions})


@app.route('/user_stats', methods=['GET'])
def user_stats():
    user_id = request.args.get('user_id', 'anonymous')
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        
        # Total conversations
        cur.execute("SELECT COUNT(*) FROM conversations WHERE user_id=?", (user_id,))
        total_convs = cur.fetchone()[0]
        
        # Total messages
        cur.execute(
            """SELECT COUNT(*) FROM messages m
               JOIN conversations c ON m.conversation_id = c.id
               WHERE c.user_id=? AND m.role='user'""",
            (user_id,)
        )
        total_questions = cur.fetchone()[0]
        
        # Recent activity (last 7 days)
        cur.execute(
            """SELECT COUNT(*) FROM conversations 
               WHERE user_id=? AND created_at >= datetime('now', '-7 days')""",
            (user_id,)
        )
        recent_convs = cur.fetchone()[0]
        
    finally:
        conn.close()
    
    return jsonify({
        'total_conversations': total_convs,
        'total_questions': total_questions,
        'recent_conversations': recent_convs
    })


@app.route('/favorites', methods=['GET'])
def get_favorites():
    user_id = request.args.get('user_id', 'anonymous')
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT f.id, f.message_id, f.category, f.notes, m.content, f.created_at
               FROM favorites f
               JOIN messages m ON f.message_id = m.id
               WHERE f.user_id=?
               ORDER BY f.created_at DESC""",
            (user_id,)
        )
        rows = cur.fetchall()
        favorites = []
        for row in rows:
            favorites.append({
                'id': row[0],
                'message_id': row[1],
                'category': row[2],
                'notes': row[3],
                'content': row[4],
                'created_at': row[5]
            })
    finally:
        conn.close()
    
    return jsonify({'favorites': favorites})


@app.route('/favorites', methods=['POST'])
def add_favorite():
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get('user_id', 'anonymous')
    message_id = data.get('message_id')
    category = data.get('category', 'general')
    notes = data.get('notes', '')
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        
        # Verify message ownership
        cur.execute("""
            SELECT c.user_id 
            FROM messages m 
            JOIN conversations c ON m.conversation_id = c.id 
            WHERE m.id = ?
        """, (message_id,))
        row = cur.fetchone()
        if not row:
             return jsonify({'error': 'message_not_found'}), 404
        if row[0] != user_id:
             return jsonify({'error': 'forbidden'}), 403
             
        cur.execute(
            "INSERT INTO favorites(user_id, message_id, category, notes) VALUES(?, ?, ?, ?)",
            (user_id, message_id, category, notes)
        )
        fav_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    
    return jsonify({'status': 'ok', 'favorite_id': fav_id})


@app.route('/favorites/<int:fav_id>', methods=['DELETE'])
def delete_favorite(fav_id: int):
    user_id = request.args.get('user_id', 'anonymous')
    if not user_id or user_id == 'anonymous':
        data = request.get_json(force=True, silent=True) or {}
        if data.get('user_id'):
            user_id = data.get('user_id')

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        # Verify ownership
        cur.execute("SELECT user_id FROM favorites WHERE id=?", (fav_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'not_found'}), 404
        if row[0] != user_id:
            return jsonify({'error': 'forbidden'}), 403
            
        cur.execute("DELETE FROM favorites WHERE id=?", (fav_id,))
        conn.commit()
    finally:
        conn.close()
    
    return jsonify({'status': 'ok'})



@app.route('/memory_stats', methods=['GET'])
def memory_stats():
    """Get memory statistics for a user"""
    user_id = request.args.get('user_id', 'anonymous')
    
    try:
        brain = get_brain(user_id)
        if hasattr(brain.enhanced_memory, 'get_stats'):
            stats = brain.enhanced_memory.get_stats()
            return jsonify({'status': 'ok', 'stats': stats})
        else:
            return jsonify({'status': 'ok', 'stats': {'message': 'Enhanced memory not available'}})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/knowledge_graph/stats', methods=['GET'])
def kg_stats():
    """Get Knowledge Graph statistics"""
    user_id = request.args.get('user_id', 'anonymous')
    
    try:
        brain = get_brain(user_id)
        if hasattr(brain, 'knowledge_graph') and brain.knowledge_graph:
            stats = brain.knowledge_graph.get_statistics()
            return jsonify({'status': 'ok', 'stats': stats})
        else:
            return jsonify({'status': 'error', 'message': 'Knowledge Graph not available'}), 404
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/knowledge_graph/search', methods=['POST'])
def kg_search():
    """Search nodes in the Knowledge Graph"""
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get('user_id', 'anonymous')
    query = data.get('query', '')
    node_type = data.get('node_type')  # Optional filter
    
    if not query:
        return jsonify({'error': 'query required'}), 400
    
    try:
        brain = get_brain(user_id)
        if not hasattr(brain, 'knowledge_graph') or not brain.knowledge_graph:
            return jsonify({'status': 'error', 'message': 'Knowledge Graph not available'}), 404
        
        nodes = brain.knowledge_graph.find_nodes(query, node_type=node_type, limit=10)
        results = [
            {
                'id': node.id,
                'label': node.label,
                'type': node.type,
                'description': node.description,
                'metadata': node.metadata
            }
            for node in nodes
        ]
        
        return jsonify({'status': 'ok', 'results': results, 'count': len(results)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/knowledge_graph/paths', methods=['POST'])
def kg_paths():
    """Find solution paths in the Knowledge Graph"""
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get('user_id', 'anonymous')
    problem = data.get('problem', '')
    max_depth = int(data.get('max_depth', 3))
    
    if not problem:
        return jsonify({'error': 'problem query required'}), 400
    
    try:
        brain = get_brain(user_id)
        if not hasattr(brain, 'knowledge_graph') or not brain.knowledge_graph:
            return jsonify({'status': 'error', 'message': 'Knowledge Graph not available'}), 404
        
        paths = brain.knowledge_graph.find_solution_path(problem, max_depth=max_depth)
        
        return jsonify({
            'status': 'ok',
            'paths': paths,
            'count': len(paths)
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/kg_export', methods=['GET'])
def kg_export():
    """Export the Knowledge Graph as JSON"""
    try:
        from chat_ai.knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph(db_path=os.getenv('SQLITE_KG_DB', 'knowledge_graph.db'))
        data = kg.export_json()
        return jsonify(data)
    except Exception as e:
        logger.exception("Error exporting KG")
        return jsonify({'error': str(e)}), 500

# --- Finance Module Endpoints ---

@app.route('/finance/accounts', methods=['GET', 'POST'])
def manage_accounts():
    """Manage chart of accounts"""
    if request.method == 'GET':
        try:
            accounts = finance_manager.get_accounts()
            return jsonify(accounts)
        except Exception as e:
            logger.exception("Error listing accounts")
            return jsonify({'error': str(e)}), 500
            
    elif request.method == 'POST':
        try:
            data = request.json
            account = AccountCreate(**data)
            result = finance_manager.create_account(account)
            return jsonify(result), 201
        except ValidationError as e:
            return jsonify({'error': e.errors()}), 400
        except Exception as e:
            logger.exception("Error creating account")
            return jsonify({'error': str(e)}), 500

@app.route('/finance/transactions', methods=['GET', 'POST'])
def manage_transactions():
    """Manage financial transactions (Journal Entries)"""
    if request.method == 'GET':
        try:
            limit = int(request.args.get('limit', 50))
            txs = finance_manager.get_transactions(limit=limit)
            return jsonify(txs)
        except Exception as e:
            logger.exception("Error listing transactions")
            return jsonify({'error': str(e)}), 500
            
    elif request.method == 'POST':
        try:
            data = request.json
            # Convert date string to date object if needed, Pydantic handles ISO strings well
            tx = TransactionCreate(**data)
            result = finance_manager.create_transaction(tx, created_by=request.headers.get('X-User-ID', 'system'))
            return jsonify(result), 201
        except ValidationError as e:
            return jsonify({'error': e.errors()}), 400
        except ValueError as e:
             return jsonify({'error': str(e)}), 400
        except Exception as e:
            logger.exception("Error creating transaction")
            return jsonify({'error': str(e)}), 500



@app.route('/finance/forecast', methods=['GET'])
def forecast_cashflow():
    """Predict future cashflow using Neural Network"""
    try:
        days = int(request.args.get('days', 7))
        prediction = finance_manager.predict_cashflow(days=days)
        return jsonify(prediction)
    except Exception as e:
        logger.exception("Error forecasting")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', '8000'))
    app.run(host='0.0.0.0', port=port, debug=True)


