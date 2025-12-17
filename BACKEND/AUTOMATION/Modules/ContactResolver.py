import json
import os
from CORE.Utils.DataPath import get_data_file_path

CONTACT_FILE = get_data_file_path("USER", "contacts.json")
_cache = {}
_mtime = 0


def _load():
    global _cache, _mtime
    if not os.path.exists(CONTACT_FILE):
        return

    mtime = os.path.getmtime(CONTACT_FILE)
    if mtime != _mtime:
        with open(CONTACT_FILE, "r", encoding="utf-8") as f:
            _cache = json.load(f)
        _mtime = mtime


def find_matching_contacts(query_name):
    """
    Returns list of (name, number) that partially match query
    """
    _load()
    query = query_name.lower()

    matches = []
    for name, number in _cache.items():
        if query in name:
            matches.append((name, number))

    return matches
