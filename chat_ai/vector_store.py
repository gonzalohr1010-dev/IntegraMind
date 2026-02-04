"""vector_store.py
Vector stores:
- InMemoryVectorStore: memoria, coseno
- FaissVectorStore: persistente si faiss está disponible
"""
from __future__ import annotations

from typing import List, Dict, Tuple
import numpy as np  # type: ignore
import json
import os


def _cosine_sim_matrix(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    # Assumes rows are already L2-normalized. If not, normalize here.
    return A @ B.T


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._embeddings: np.ndarray | None = None
        self._metas: List[Dict[str, str]] = []

    @property
    def size(self) -> int:
        return 0 if self._embeddings is None else self._embeddings.shape[0]

    def add(self, embeddings: np.ndarray, metas: List[Dict[str, str]]) -> None:
        if embeddings.shape[0] != len(metas):
            raise ValueError("Embeddings and metas size mismatch")
        if self._embeddings is None:
            self._embeddings = embeddings
        else:
            self._embeddings = np.vstack([self._embeddings, embeddings])
        self._metas.extend(metas)

    def search(self, query_vec: np.ndarray, top_k: int = 5) -> List[Tuple[Dict[str, str], float]]:
        if self._embeddings is None or self._embeddings.shape[0] == 0:
            return []
        # Ensure query is 2D
        q = query_vec.reshape(1, -1)
        sims = _cosine_sim_matrix(q, self._embeddings)[0]
        idxs = np.argsort(-sims)[:top_k]
        results: List[Tuple[Dict[str, str], float]] = []
        for idx in idxs:
            results.append((self._metas[int(idx)], float(sims[int(idx)])))
        return results


class FaissVectorStore:
    """FAISS index with cosine similarity (inner product on normalized vectors).

    Persists index and metadata to a directory.
    """

    def __init__(self) -> None:
        self._index = None
        self._metas: List[Dict[str, str]] = []

    @property
    def size(self) -> int:
        if self._index is None:
            return 0
        try:
            return int(self._index.ntotal)  # type: ignore[attr-defined]
        except Exception:
            return 0

    def _ensure_index(self, dim: int):
        if self._index is None:
            try:
                import faiss  # type: ignore
            except Exception as e:
                raise RuntimeError("FAISS no está instalado. Instala faiss-cpu.") from e
            # Inner product because embeddings están L2-normalizados
            self._index = faiss.IndexFlatIP(dim)

    def add(self, embeddings: np.ndarray, metas: List[Dict[str, str]]) -> None:
        if embeddings.shape[0] != len(metas):
            raise ValueError("Embeddings and metas size mismatch")
        self._ensure_index(embeddings.shape[1])
        try:
            import faiss  # type: ignore
        except Exception as e:
            raise RuntimeError("FAISS no está instalado. Instala faiss-cpu.") from e
        self._index.add(embeddings.astype('float32'))
        self._metas.extend(metas)

    def search(self, query_vec: np.ndarray, top_k: int = 5) -> List[Tuple[Dict[str, str], float]]:
        if self._index is None or self.size == 0:
            return []
        if not isinstance(query_vec, np.ndarray):
            query_vec = np.array(query_vec)
        q = query_vec.astype('float32').reshape(1, -1)
        D, I = self._index.search(q, top_k)
        results: List[Tuple[Dict[str, str], float]] = []
        for idx, score in zip(I[0], D[0]):
            if int(idx) < 0 or int(idx) >= len(self._metas):
                continue
            results.append((self._metas[int(idx)], float(score)))
        return results

    def save(self, directory: str) -> None:
        os.makedirs(directory, exist_ok=True)
        metas_path = os.path.join(directory, 'metas.json')
        index_path = os.path.join(directory, 'index.faiss')
        with open(metas_path, 'w', encoding='utf-8') as f:
            json.dump(self._metas, f, ensure_ascii=False)
        if self._index is not None:
            try:
                import faiss  # type: ignore
                faiss.write_index(self._index, index_path)
            except Exception as e:
                raise RuntimeError("Error al guardar índice FAISS") from e

    def load(self, directory: str) -> None:
        metas_path = os.path.join(directory, 'metas.json')
        index_path = os.path.join(directory, 'index.faiss')
        if not (os.path.isfile(metas_path) and os.path.isfile(index_path)):
            return
        with open(metas_path, 'r', encoding='utf-8') as f:
            self._metas = json.load(f)
        try:
            import faiss  # type: ignore
            self._index = faiss.read_index(index_path)
        except Exception as e:
            raise RuntimeError("Error al cargar índice FAISS") from e


