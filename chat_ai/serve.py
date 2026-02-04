"""serve.py
Lightweight FastAPI server exposing /chat and /profile endpoints.
"""
from __future__ import annotations
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
from dotenv import load_dotenv
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

from .personalization import load_profile, save_profile, classify_user_type
from .embeddings import get_model
from .index import FaissIndex, init_meta_db
from .rag import answer_question

app = FastAPI()

# Load environment variables from .env if present
load_dotenv()

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger(__name__)

# Enable CORS for all origins (adjust as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CORS_ORIGINS", "*")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# mount static web UI
app.mount('/static', StaticFiles(directory='web'), name='static')


@app.get('/admin', response_class=HTMLResponse)
async def admin_page():
    return FileResponse('web/admin.html')


@app.on_event("startup")
async def startup_event():
    logger.info("startup: loading embedding model and index")
    # Load embeddings model (cached by get_model)
    try:
        model = get_model()
        app.state.model = model
    except Exception:
        logger.exception("failed to load embeddings model")
        app.state.model = None

    # Initialize metadata DB early
    try:
        init_meta_db()
    except Exception:
        logger.exception("init_meta_db failed during startup")

    # Prepare FaissIndex: try to open existing index, otherwise infer dim from model
    idx = None
    try:
        idx = FaissIndex()
        logger.info("FaissIndex loaded from disk or created (existing)")
    except Exception as e:
        logger.info("FaissIndex() without dim failed: %s", e)
        # Try to infer dim from model by encoding a sample
        dim = None
        try:
            if hasattr(app.state, 'model') and app.state.model is not None:
                sample = app.state.model.encode_texts(["hola mundo"])
                if hasattr(sample, 'shape'):
                    dim = int(sample.shape[1])
                else:
                    try:
                        import numpy as _np
                        arr = _np.asarray(sample)
                        dim = int(arr.shape[1])
                    except Exception:
                        dim = None
        except Exception:
            logger.exception("failed to infer embedding dim from model")
        if dim is None:
            try:
                dim = int(os.getenv("EMBED_DIM", 384))
            except Exception:
                dim = 384
        try:
            idx = FaissIndex(dim=dim)
            logger.info("FaissIndex created with dim=%s", dim)
        except Exception:
            logger.exception("failed to create FaissIndex during startup")
            idx = None

    app.state.idx = idx



@app.get('/admin/feedback')
async def admin_feedback():
    # Return feedback rows from meta sqlite
    import sqlite3
    init_meta_db()
    conn = sqlite3.connect('chat_index/meta.sqlite')
    c = conn.cursor()
    try:
        c.execute('SELECT id, doc_id, user_id, helpful, ts FROM feedback ORDER BY ts DESC')
        rows = c.fetchall()
    except Exception:
        rows = []
    conn.close()
    return {'feedback': [{'id': r[0], 'doc_id': r[1], 'user_id': r[2], 'helpful': bool(r[3]), 'ts': r[4]} for r in rows]}


@app.get('/admin/feedback/export')
async def admin_feedback_export():
    import sqlite3, csv, io
    init_meta_db()
    conn = sqlite3.connect('chat_index/meta.sqlite')
    c = conn.cursor()
    try:
        c.execute('SELECT id, doc_id, user_id, helpful, ts FROM feedback ORDER BY ts DESC')
        rows = c.fetchall()
    except Exception:
        rows = []
    conn.close()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['id', 'doc_id', 'user_id', 'helpful', 'ts'])
    for r in rows:
        writer.writerow(r)
    return HTMLResponse(content=buf.getvalue(), media_type='text/csv')


@app.get('/admin/users')
async def admin_users():
    import sqlite3
    conn = sqlite3.connect('users.sqlite')
    c = conn.cursor()
    try:
        c.execute('SELECT id, created_at, profile_json FROM users ORDER BY created_at DESC')
        rows = c.fetchall()
    except Exception:
        rows = []
    conn.close()
    return {'users': [{'id': r[0], 'created_at': r[1], 'profile_json': r[2]} for r in rows]}


class ChatRequest(BaseModel):
    user_id: Optional[str] = 'anonymous'
    question: str


class ProfileRequest(BaseModel):
    user_id: str
    profile_json: str


@app.post('/chat')
async def chat(req: ChatRequest):
    model = getattr(app.state, 'model', None) or get_model()
    if model is None:
        raise HTTPException(status_code=500, detail='Embeddings model no disponible')
    init_meta_db()
    # reuse index created at startup when possible
    idx = getattr(app.state, 'idx', None)
    if idx is None:
        try:
            idx = FaissIndex()
        except Exception:
            # fallback to creating with a default dim
            idx = FaissIndex(dim=int(os.getenv('EMBED_DIM', 384)))
    # also return contexts used
    from .rag import retrieve_contexts
    contexts = []
    try:
        contexts = retrieve_contexts(req.question, idx, top_k=5)
    except Exception:
        contexts = []
    try:
        resp = answer_question(req.question, idx)
    except Exception as e:
        logger.exception("Error answering question")
        raise HTTPException(status_code=500, detail='Error processing question')
    # Return only the assistant answer (single response). Contexts are intentionally omitted.
    return {'answer': resp}


@app.post('/chat_stream')
async def chat_stream(req: ChatRequest):
    # Return a streaming response (text/event-stream not necessary; we'll stream raw chunks)
    from fastapi.responses import StreamingResponse
    init_meta_db()
    idx = getattr(app.state, 'idx', None)
    if idx is None:
        try:
            idx = FaissIndex()
        except Exception:
            idx = FaissIndex(dim=int(os.getenv('EMBED_DIM', 384)))
    async def iter_chunks():
        for chunk in __import__('chat_ai.rag', fromlist=['stream_answer']).stream_answer(req.question, idx, top_k=5):
            yield chunk
    return StreamingResponse(iter_chunks(), media_type='text/plain; charset=utf-8')


@app.get('/', response_class=HTMLResponse)
async def homepage(request: Request):
    # serve the main web UI
    return FileResponse('web/index.html')


@app.get('/docs_list')
async def docs_list():
    # return a simple list of docs from metadata DB
    init_meta_db()
    import sqlite3
    conn = sqlite3.connect('chat_index/meta.sqlite')
    c = conn.cursor()
    c.execute('SELECT id, source, text FROM docs ORDER BY id LIMIT 100')
    rows = c.fetchall()
    conn.close()
    return {'docs': [{'id': r[0], 'source': r[1], 'text': (r[2][:200] + '...') if r[2] else ''} for r in rows]}


@app.post('/ingest')
async def ingest_endpoint(payload: dict):
    # simple ingest endpoint accepting {source, text}
    src = payload.get('source', 'web_upload')
    txt = payload.get('text', '')
    if not txt:
        raise HTTPException(status_code=400, detail='text required')
    from .ingest import ingest_texts
    idx = ingest_texts([{'source': src, 'text': txt}])
    return {'status': 'ingested'}


@app.post('/feedback')
async def feedback(payload: dict):
    """Accept feedback from UI: {doc_id, helpful:bool, user_id} - store in a simple sqlite table."""
    init_meta_db()
    doc_id = payload.get('doc_id')
    helpful = bool(payload.get('helpful', False))
    user_id = payload.get('user_id', 'anonymous')
    # store feedback in a table
    import sqlite3
    conn = sqlite3.connect('chat_index/meta.sqlite')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS feedback (id INTEGER PRIMARY KEY AUTOINCREMENT, doc_id INTEGER, user_id TEXT, helpful INTEGER, ts DATETIME DEFAULT CURRENT_TIMESTAMP)')
    c.execute('INSERT INTO feedback (doc_id, user_id, helpful) VALUES (?, ?, ?)', (doc_id, user_id, 1 if helpful else 0))
    conn.commit()
    conn.close()
    return {'status': 'ok'}


@app.post('/profile')
async def profile(req: ProfileRequest):
    save_profile(req.user_id, req.profile_json)
    return {'status': 'ok'}


@app.get('/profile/{user_id}')
async def get_profile(user_id: str):
    return {'profile': load_profile(user_id)}


def run(host='127.0.0.1', port=8000):
    uvicorn.run('chat_ai.serve:app', host=host, port=port, reload=False)


if __name__ == '__main__':
    run()
