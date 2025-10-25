"""
Lightweight persistence layer for parsed document results.

This module provides an in-memory key/value store for extracted
document data with optional JSON file persistence. It is designed
to support concurrent FastAPI workloads using a re-entrant lock
for thread-safe mutations.

The persistence layer is intentionally minimal and format-agnostic.
Stored values must be JSON serializable.
"""

import json
import os
import threading
from typing import Dict, Optional, List

# Load persistence configuration from application settings if available
try:
    from app.config import Settings, get_settings
    SETTINGS = get_settings()
    PERSIST_PATH = getattr(SETTINGS, "PERSIST_PATH", None)
except Exception:
    PERSIST_PATH = None

# Primary in-memory backing store and synchronization primitive
_STORE: Dict[str, Dict] = {}
_STORE_LOCK = threading.RLock()

# Default persistence target if not configured
if PERSIST_PATH is None:
    PERSIST_PATH = os.environ.get("CLAIMS_STORE_PATH", "data/parsed_store.json")
    os.makedirs(os.path.dirname(PERSIST_PATH), exist_ok=True)


def _persist_to_disk():
    """
    Atomic write of the entire store to JSON on disk.

    A temporary file is written first, then moved into place
    to avoid corruption if interrupted during write.
    """
    tmp_path = PERSIST_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(_STORE, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, PERSIST_PATH)


def _load_from_disk():
    """
    Initialize in-memory state from persisted JSON at startup.

    Silently skips if the file is missing or corrupted to avoid
    preventing server startup.
    """
    if not os.path.exists(PERSIST_PATH):
        return
    try:
        with open(PERSIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        with _STORE_LOCK:
            _STORE.clear()
            for k, v in data.items():
                _STORE[k] = v
    except Exception:
        return


# Load persisted data opportunistically during module import
try:
    _load_from_disk()
except Exception:
    pass


def save_parsed(document_id: str, parsed_data: Dict, persist: bool = False) -> None:
    """
    Insert or update parsed document data.

    If persist=True, changes are synchronized to disk within the lock.
    Persistence failures are non-fatal for request handling.
    """
    with _STORE_LOCK:
        _STORE[document_id] = parsed_data
        if persist:
            try:
                _persist_to_disk()
            except Exception:
                pass


def get_parsed(document_id: str) -> Optional[Dict]:
    """
    Retrieve parsed data for a document_id if present.

    Returns None if not found.
    """
    with _STORE_LOCK:
        return _STORE.get(document_id)


def delete_parsed(document_id: str) -> bool:
    """
    Remove a parsed document entry.

    Returns True if the entry existed, otherwise False.
    Disk persistence is attempted on successful removal.
    """
    with _STORE_LOCK:
        if document_id in _STORE:
            del _STORE[document_id]
            try:
                _persist_to_disk()
            except Exception:
                pass
            return True
        return False


def list_all() -> List[str]:
    """
    List all stored document identifiers currently in memory.

    Does not reflect persisted state if disk writes failed.
    """
    with _STORE_LOCK:
        return list(_STORE.keys())
