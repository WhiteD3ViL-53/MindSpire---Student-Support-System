# data_store_utils.py
import json
import os
from threading import Lock
from typing import Dict, Any

# ---------- File-based defaults ----------
DATA_FILE = os.path.join(os.path.dirname(__file__), "data_store.json")

DEFAULT_STORE = {
    "availability": {},   # "d_s" (e.g. "0_3") -> bool
    "bookings": [],       # {"day":int,"slot":int,"token":str,"time":str}
    "counsellors": [],    # {"id":int,"name":str,"specialty":str}
    "chat_logs": [],      # optional
}

_lock = Lock()

# ---------- Firestore setup ----------
USE_FIRESTORE = os.environ.get("USE_FIRESTORE", "").lower() in ("1", "true", "yes")
FIRESTORE_COLLECTION = os.environ.get("FIRESTORE_COLLECTION", "healnest_store")
FIRESTORE_DOC_ID = os.environ.get("FIRESTORE_DOC_ID", "default")

_firestore_client = None
_firestore_available = False

if USE_FIRESTORE:
    try:
        from google.cloud import firestore  # type: ignore
        _firestore_client = firestore.Client()
        _firestore_available = True
        print("[data_store_utils] Using Firestore backend")
    except Exception as e:
        print(f"[data_store_utils] Firestore init failed, falling back to JSON: {e}")
        _firestore_available = False


# ---------- File helpers ----------
def _read_file_store() -> Dict[str, Any]:
    if not os.path.exists(DATA_FILE):
        return DEFAULT_STORE.copy()
    with _lock:
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k in DEFAULT_STORE:
                if k not in data:
                    data[k] = DEFAULT_STORE[k]
            return data
        except Exception:
            return DEFAULT_STORE.copy()


def _write_file_store(data: Dict[str, Any]) -> None:
    with _lock:
        tmp = DATA_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, DATA_FILE)


# ---------- Public API ----------
def load_data() -> Dict[str, Any]:
    if USE_FIRESTORE and _firestore_available:
        try:
            doc_ref = _firestore_client.collection(FIRESTORE_COLLECTION).document(FIRESTORE_DOC_ID)
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict().get("payload", {})
                if isinstance(data, dict):
                    for k in DEFAULT_STORE:
                        if k not in data:
                            data[k] = DEFAULT_STORE[k]
                    return data
            return DEFAULT_STORE.copy()
        except Exception as e:
            print(f"[data_store_utils] Firestore read error, using JSON fallback: {e}")
            return _read_file_store()
    else:
        return _read_file_store()


def save_data(data: Dict[str, Any]) -> None:
    if USE_FIRESTORE and _firestore_available:
        try:
            doc_ref = _firestore_client.collection(FIRESTORE_COLLECTION).document(FIRESTORE_DOC_ID)
            doc_ref.set({"payload": data})
            return
        except Exception as e:
            print(f"[data_store_utils] Firestore write error, using JSON fallback: {e}")
    _write_file_store(data)
