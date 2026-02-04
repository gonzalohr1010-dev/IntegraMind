"""embeddings.py
Pluggable embedding backend with graceful fallback:
- Prefer SentenceTransformers if installed
- Fallback to TF-IDF from scikit-learn
"""
from __future__ import annotations

from typing import List, Optional


class EmbeddingBackend:
    """Unified interface for text embeddings with optional training/fit."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._backend: str
        self._model = None
        self._vectorizer = None
        self._model_name = model_name

        # Try SentenceTransformers first
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            self._model = SentenceTransformer(model_name)
            self._backend = "sentence_transformers"
        except Exception:
            # Fallback to TF-IDF
            try:
                from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore

                self._vectorizer = TfidfVectorizer(
                    max_features=4096,
                    ngram_range=(1, 2),
                    stop_words="english",
                )
                # Fit on dummy data to prevent NotFittedError if used before ingestion
                self._vectorizer.fit(["initialization dummy text"])
                self._backend = "tfidf"
            except Exception as e:  # pragma: no cover
                raise RuntimeError(
                    "No embedding backend available. Please install 'sentence-transformers' or 'scikit-learn'."
                ) from e

    @property
    def backend_name(self) -> str:
        return self._backend

    def fit_corpus(self, texts: List[str]) -> None:
        """Optional fit; only needed for TF-IDF backend."""
        if self._backend == "tfidf" and self._vectorizer is not None:
            # Fit on corpus to build vocabulary
            self._vectorizer.fit(texts)

    def encode_texts(self, texts: List[str]):
        """Return a 2D array-like of embeddings for texts."""
        if self._backend == "sentence_transformers" and self._model is not None:
            return self._model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        elif self._backend == "tfidf" and self._vectorizer is not None:
            # For TF-IDF we L2-normalize to make cosine similarity simple dot product
            import numpy as np  # type: ignore
            from sklearn.preprocessing import normalize  # type: ignore

            X = self._vectorizer.transform(texts)
            X = normalize(X, norm="l2")
            return X.toarray() if hasattr(X, "toarray") else np.asarray(X)
        else:  # pragma: no cover
            raise RuntimeError("Embedding backend is not properly initialized")

    def encode_query(self, query: str):
        return self.encode_texts([query])[0]


# Helper functions to keep backward compatibility with older modules
def get_model(model_name: str = "all-MiniLM-L6-v2") -> EmbeddingBackend:
    """Return a singleton EmbeddingBackend instance.

    The original codebase expected a ``get_model`` function that returned an
    object exposing ``encode`` and ``encode_query``.  The new
    :class:`EmbeddingBackend` already provides those methods, so this helper
    simply creates and caches a single instance.
    """
    if not hasattr(get_model, "_instance"):
        get_model._instance = EmbeddingBackend(model_name=model_name)
    return get_model._instance


def embed_texts(texts: List[str], model_name: str = "all-MiniLM-L6-v2"):
    """Convenience wrapper that returns embeddings for a list of texts.

    Parameters
    ----------
    texts:
        List of strings to embed.
    model_name:
        Name of the model to use.  It is passed to :func:`get_model`.
    """
    model = get_model(model_name)
    return model.encode_texts(texts)
