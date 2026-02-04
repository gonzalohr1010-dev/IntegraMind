"""smoke_test.py
Run a small ingest and perform a demo query through the RAG pipeline.
"""
from __future__ import annotations
from .ingest import ingest_texts
from .rag import answer_question


def run():
    texts = [
        {'source': 'doc1', 'text': 'Python es un lenguaje de programación interpretado, utilizado ampliamente para desarrollo web y ciencia de datos.'},
        {'source': 'doc2', 'text': 'La inteligencia artificial incluye aprendizaje automático, redes neuronales y procesamiento del lenguaje natural.'},
        {'source': 'doc3', 'text': 'SQLite es una base de datos ligera que se guarda en un archivo y es adecuada para prototipos y apps pequeñas.'}
    ]
    print('Ingestando textos...')
    idx = ingest_texts(texts)
    print('Ingest completado. Realizando consulta RAG...')
    q = '¿Qué es SQLite y para qué sirve?'
    resp = answer_question(q, idx)
    print('Pregunta:', q)
    print('Respuesta:', resp)


if __name__ == '__main__':
    run()
