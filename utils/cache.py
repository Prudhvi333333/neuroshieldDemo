# utils/cache.py
from functools import lru_cache
from datetime import datetime, timedelta

class ResponseCache:
    def __init__(self, ttl_minutes=5):
        self.cache = {}
        self.ttl = timedelta(minutes=ttl_minutes)

    @lru_cache(maxsize=1000)
    def get_cached_response(self, prompt: str, model: str) -> dict:
        key = f"{model}:{hash(prompt)}"
        if key in self.cache:
            cached = self.cache[key]
            if datetime.now() - cached['timestamp'] < self.ttl:
                return cached['response']
        return None

    def set_cached_response(self, prompt: str, model: str, response: dict):
        key = f"{model}:{hash(prompt)}"
        self.cache[key] = {
            'response': response,
            'timestamp': datetime.now()
        }