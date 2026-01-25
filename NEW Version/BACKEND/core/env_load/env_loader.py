# BACKEND/core/env_load/env_loader.py
import os
from dotenv import load_dotenv

_loaded = False


def _env_paths():
    here = os.path.dirname(os.path.abspath(__file__))
    backend_root = os.path.abspath(os.path.join(here, "..", ".."))
    project_root = os.path.abspath(os.path.join(backend_root, ".."))
    return [
        os.path.join(project_root, ".env"),
        os.path.join(backend_root, ".env"),
    ]


def load_env():
    global _loaded
    if _loaded:
        return
    for path in _env_paths():
        if os.path.exists(path):
            load_dotenv(path)
    _loaded = True


def get_env(key: str, default=None):
    load_env()
    return os.getenv(key, default)


def get_env_required(key: str):
    load_env()
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value
