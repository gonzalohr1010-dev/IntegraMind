"""ingest.py
Script to ingest a list of documents, compute embeddings and store them in FAISS + SQLite metadata.
"""
from __future__ import annotations
import os
import numpy as np
from typing import List, Dict

from .data import chunk_text
from .embeddings import get_model, embed_texts
from .index import FaissIndex, save_metadata, init_meta_db


def ingest_texts(texts: List[Dict[str,str]], model_name: str = 'sentence-transformers/all-MiniLM-L6-v2'):
    model = get_model(model_name)
    if model is None:
        raise RuntimeError('Embeddings model no disponible. Instala sentence-transformers.')
    # chunk
    docs = []
    for i, d in enumerate(texts):
        chunks = chunk_text(d.get('text', ''))
        for j, c in enumerate(chunks):
            docs.append({'id': i*1000 + j, 'source': d.get('source'), 'text': c})

    texts_only = [d['text'] for d in docs]
    vectors = embed_texts(texts_only, model_name=model_name)
    vectors = np.asarray(vectors).astype('float32')
    dim = vectors.shape[1]

    idx = FaissIndex(dim=dim)
    ids = np.array([d['id'] for d in docs], dtype='int64')
    idx.add(vectors, ids)
    save_metadata(docs)
    return idx


if __name__ == '__main__':
    sample = [
        {'source': 'doc1', 'text': 'Python es un lenguaje de programación interpretado, utilizado ampliamente para desarrollo web y ciencia de datos.'},
        {'source': 'doc2', 'text': 'La inteligencia artificial incluye aprendizaje automático, redes neuronales y procesamiento del lenguaje natural.'},
        {'source': 'doc3', 'text': 'SQLite es una base de datos ligera que se guarda en un archivo y es adecuada para prototipos y apps pequeñas.'}
    ]
    ingest_texts(sample)
    print('Ingest completed')
