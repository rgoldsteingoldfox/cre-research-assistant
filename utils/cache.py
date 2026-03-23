"""Simple JSON file cache to avoid redundant API calls."""

import json
import os

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".cache")


def _cache_path(name):
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"{name}.json")


def load_cache(name):
    path = _cache_path(name)
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}


def save_cache(name, data):
    path = _cache_path(name)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def get_cached(name, key):
    cache = load_cache(name)
    return cache.get(key)


def set_cached(name, key, value):
    cache = load_cache(name)
    cache[key] = value
    save_cache(name, cache)
