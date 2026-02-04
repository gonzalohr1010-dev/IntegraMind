"""wikipedia.py
Lightweight helpers to fetch summaries from Wikipedia in a given language.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Optional, Dict


def _http_get_json(url: str, headers: Optional[Dict[str, str]] = None) -> dict:
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "chat_ai/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:  # nosec - controlled URL
        data = resp.read().decode("utf-8", errors="ignore")
        return json.loads(data)


def search_title(query: str, lang: str = "es") -> Optional[str]:
    q = urllib.parse.quote(query)
    url = f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&format=json&srsearch={q}&srlimit=1"
    try:
        j = _http_get_json(url)
        hits = j.get("query", {}).get("search", [])
        if hits:
            return hits[0].get("title")
    except Exception:
        return None
    return None


def fetch_summary(title: str, lang: str = "es") -> Optional[dict]:
    t = urllib.parse.quote(title)
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{t}"
    try:
        j = _http_get_json(url, headers={"User-Agent": "chat_ai/1.0", "Accept": "application/json"})
        if j and j.get("extract"):
            return j
    except Exception:
        return None
    return None


def fetch_wikipedia_answer(query: str, lang: str = "es") -> Optional[dict]:
    """Return a dict with keys: title, url, extract; or None if not found."""
    title = search_title(query, lang=lang)
    if not title:
        return None
    summary = fetch_summary(title, lang=lang)
    if not summary:
        return None
    return {
        "title": summary.get("title", title),
        "url": summary.get("content_urls", {}).get("desktop", {}).get("page") or summary.get("urls", {}).get("desktop", {}).get("page") or f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(title)}",
        "extract": summary.get("extract", ""),
    }


