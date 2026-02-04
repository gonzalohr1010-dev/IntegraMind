"""index.py
FAISS-based vector index with SQLite metadata for documents.
"""
from __future__ import annotations
import os
import sqlite3
import logging
from typing import List, Dict, Any, Optional

_has_faiss = True
try:
    import faiss
except Exception:
    _has_faiss = False

INDEX_DIR = 'chat_index'
INDEX_FILE = os.path.join(INDEX_DIR, 'index.faiss')
META_DB = os.path.join(INDEX_DIR, 'meta.sqlite')
VECTORS_FILE = os.path.join(INDEX_DIR, 'vectors.npz')


def ensure_index_dir():
    os.makedirs(INDEX_DIR, exist_ok=True)


def init_meta_db():
    ensure_index_dir()
    conn = sqlite3.connect(META_DB)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS docs (
            id INTEGER PRIMARY KEY,
            source TEXT,
            text TEXT
        )
    ''')
    conn.commit()
    conn.close()


def save_metadata(items: List[Dict[str, Any]]):
    init_meta_db()
    conn = sqlite3.connect(META_DB)
    c = conn.cursor()
    for i, it in enumerate(items):
        # Use INSERT OR REPLACE to avoid UNIQUE constraint failures when re-ingesting
        c.execute('INSERT OR REPLACE INTO docs (id, source, text) VALUES (?, ?, ?)', (it['id'], it.get('source'), it.get('text')))
    conn.commit()
    conn.close()


class FaissIndex:
    def __init__(self, dim: Optional[int] = None):
        ensure_index_dir()
        self.dim = dim
        self.index = None
        self._use_faiss = _has_faiss
        if self._use_faiss:
            if os.path.exists(INDEX_FILE):
                self.index = faiss.read_index(INDEX_FILE)
                try:
                    self.dim = self.index.d
                except Exception:
                    pass
            else:
                if self.dim is None:
                    raise ValueError('dim is required to create a new FAISS index')
                self.index = faiss.IndexFlatL2(self.dim)
            # no in-memory store when using faiss
            self._vectors = None
            self._ids = None
        else:
            # fallback: keep vectors and ids in memory and do brute-force search
            import numpy as _np
            # attempt to load persisted vectors if present
            if os.path.exists(VECTORS_FILE):
                try:
                    data = _np.load(VECTORS_FILE)
                    self._vectors = data['vectors'].astype('float32')
                    self._ids = data['ids'].astype('int64')
                    if self.dim is None and self._vectors is not None and self._vectors.shape[1]:
                        self.dim = int(self._vectors.shape[1])
                except Exception:
                    # fallback to empty
                    self._vectors = _np.zeros((0, dim if dim is not None else 0), dtype='float32')
                    self._ids = _np.array([], dtype='int64')
            else:
                self._vectors = _np.zeros((0, dim if dim is not None else 0), dtype='float32')
                self._ids = _np.array([], dtype='int64')

    def add(self, vectors, ids):
        import numpy as np
        if self._use_faiss:
            try:
                # try to add with ids (if using an Index that supports ids)
                self.index.add_with_ids(vectors.astype('float32'), ids.astype('int64'))
            except Exception:
                # some FAISS indexes don't support add_with_ids; fall back to add()
                try:
                    self.index.add(vectors.astype('float32'))
                except Exception as e:
                    logging.warning(f"faiss add failed: {e}")
            try:
                faiss.write_index(self.index, INDEX_FILE)
            except Exception:
                # best-effort persist
                pass
        else:
            # append to in-memory arrays
            if self._vectors is None or self._ids is None:
                self._vectors = vectors.astype('float32')
                self._ids = ids.astype('int64')
            else:
                # Remove any existing vectors that have ids overlapping with incoming ids
                incoming_ids = ids.astype('int64')
                if self._ids.size > 0:
                    try:
                        overlap_mask = np.isin(self._ids, incoming_ids)
                        if overlap_mask.any():
                            keep_mask = ~overlap_mask
                            self._vectors = self._vectors[keep_mask]
                            self._ids = self._ids[keep_mask]
                    except Exception:
                        # if any issue computing overlaps, fall back to naive append
                        pass
                # append incoming (this will replace any removed overlapping ids)
                self._vectors = np.vstack([self._vectors, vectors.astype('float32')])
                self._ids = np.concatenate([self._ids, ids.astype('int64')])
            # optional: persist numpy arrays for later reuse
            try:
                np.savez_compressed(VECTORS_FILE, vectors=self._vectors, ids=self._ids)
            except Exception:
                pass

    def load_vectors(self):
        """Force-load persisted vectors (if present) into memory."""
        if self._use_faiss:
            return
        try:
            import numpy as _np
            if os.path.exists(VECTORS_FILE):
                data = _np.load(VECTORS_FILE)
                self._vectors = data['vectors'].astype('float32')
                self._ids = data['ids'].astype('int64')
                return True
        except Exception:
            return False
        return False

    def search(self, vector, k=5):
        import numpy as np
        if self._use_faiss:
            D, I = self.index.search(vector.astype('float32'), k)
            return D, I
        # brute-force search over in-memory vectors
        if self._vectors is None or self._vectors.shape[0] == 0:
            return np.array([[]]), np.array([[]], dtype='int64')
        v = vector.astype('float32')
        # vector: (1, dim), _vectors: (n, dim)
        # handle dimension mismatch gracefully
        stored_dim = self._vectors.shape[1]
        q_dim = v.shape[1]
        if stored_dim == 0:
            return np.array([[]]), np.array([[]], dtype='int64')
        if q_dim != stored_dim:
            try:
                # truncate or pad query to match stored dimension
                if q_dim > stored_dim:
                    v = v[:, :stored_dim]
                else:
                    # pad query with zeros
                    pad_width = stored_dim - q_dim
                    v = np.hstack([v, np.zeros((v.shape[0], pad_width), dtype='float32')])
            except Exception:
                # fallback: no results
                return np.array([[]]), np.array([[]], dtype='int64')
        # compute squared L2 distances
        dif = self._vectors - v
        dists = np.sum(dif * dif, axis=1)
        idxs = np.argsort(dists)[:k]
        D = dists[idxs][None, :]
        I = self._ids[idxs][None, :].astype('int64')
        return D, I


def simple_retrieve(query_vec, top_k=5):
    # Fallback simple SQLite scan (naive) if FAISS not available
    if _has_faiss:
        raise RuntimeError('simple_retrieve should be used only when FAISS no disponible')
    conn = sqlite3.connect(META_DB)
    c = conn.cursor()
    c.execute('SELECT id, text FROM docs')
    rows = c.fetchall()
    # naive similarity: length of common substring (placeholder)
    results = []
    for r in rows:
        score = 0
        results.append((score, r[0]))
    results.sort(reverse=True)
    return results[:top_k]
