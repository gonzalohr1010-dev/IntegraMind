"""data.py
Utilities to load plain text and CSV files into a list of documents (text chunks).
"""
from __future__ import annotations
import os
import csv
from typing import List, Dict


def load_text_file(path: str) -> List[Dict[str,str]]:
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    return [{'source': os.path.basename(path), 'text': text}]


def load_csv(path: str, text_col: str = None) -> List[Dict[str,str]]:
    docs = []
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if text_col is None:
            # try to find a text-y column
            for row in reader:
                combined = ' '.join([v for v in row.values() if v])
                docs.append({'source': os.path.basename(path), 'text': combined})
        else:
            for row in reader:
                docs.append({'source': os.path.basename(path), 'text': row.get(text_col, '')})
    return docs


def chunk_text(text: str, max_chars: int = 1000, overlap: int = 200) -> List[str]:
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end])
        start = max(start + max_chars - overlap, end)
        if start >= len(text):
            break
    return chunks


def load_directory(directory: str) -> List[Dict[str, str]]:
    """Load all .txt and .csv files in a directory into document dicts.

    For CSV files, this uses the auto-detect behavior from load_csv (concatenate all columns),
    which is a robust default when a text column name is unknown.
    """
    docs: List[Dict[str, str]] = []
    for filename in os.listdir(directory):
        path = os.path.join(directory, filename)
        if not os.path.isfile(path):
            continue
        lower = filename.lower()
        if lower.endswith('.txt'):
            docs.extend(load_text_file(path))
        elif lower.endswith('.csv'):
            docs.extend(load_csv(path))
    return docs


def prepare_documents(
    raw_docs: List[Dict[str, str]],
    max_chars: int = 1000,
    overlap: int = 200,
) -> List[Dict[str, str]]:
    """Split raw documents into chunks and attach metadata.

    Returns a list of dicts with keys: 'id', 'source', 'chunk_index', 'text', plus any extra metadata from original doc.
    """
    prepared: List[Dict[str, str]] = []
    for doc_idx, doc in enumerate(raw_docs):
        source = doc.get('source', f'doc_{doc_idx}')
        text = doc.get('text', '')
        
        # Extract extra metadata (everything except 'source' and 'text')
        extra_metadata = {k: v for k, v in doc.items() if k not in {'source', 'text'}}
        
        pieces = chunk_text(text, max_chars=max_chars, overlap=overlap)
        for i, piece in enumerate(pieces):
            chunk_data = {
                'id': f"{source}::chunk_{i}",
                'source': source,
                'chunk_index': str(i),
                'text': piece,
            }
            # Preserve all extra metadata in each chunk
            chunk_data.update(extra_metadata)
            prepared.append(chunk_data)
    return prepared