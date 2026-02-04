"""memory.py
Minimal conversational memory with a rolling window by char budget.
"""
from __future__ import annotations

from typing import List, Dict


class ChatMemory:
    def __init__(self, max_chars: int = 4000) -> None:
        self._messages: List[Dict[str, str]] = []
        self._max_chars = max_chars

    def add(self, role: str, content: str) -> None:
        self._messages.append({"role": role, "content": content})
        self._trim()

    def _trim(self) -> None:
        # Keep most recent messages under the char budget
        total = 0
        kept: List[Dict[str, str]] = []
        for msg in reversed(self._messages):
            total += len(msg.get("content", ""))
            kept.append(msg)
            if total >= self._max_chars:
                break
        self._messages = list(reversed(kept))

    def get(self) -> List[Dict[str, str]]:
        return list(self._messages)


