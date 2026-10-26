# api/services/cache.py
"""Cache mémoire à durée de vie limitée, partagé par les services externes."""
from __future__ import annotations

import json
import time


class TTLCache:
    def __init__(self, ttl_s: float, max_items: int = 500) -> None:
        self.ttl = ttl_s
        self.max = max_items
        self.data: dict[str, tuple[float, object]] = {}

    @staticmethod
    def key(*parts) -> str:
        return json.dumps(parts, sort_keys=True, default=str)

    def get(self, key: str):
        hit = self.data.get(key)
        if hit and time.monotonic() - hit[0] < self.ttl:
            return hit[1]
        return None

    def set(self, key: str, value) -> None:
        if len(self.data) >= self.max:
            # supprime la plus ancienne entrée
            self.data.pop(min(self.data, key=lambda k: self.data[k][0]))
        self.data[key] = (time.monotonic(), value)
