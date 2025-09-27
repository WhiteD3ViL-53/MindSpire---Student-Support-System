# data_store_utils.py (Firebase-only version)
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

# --- Firebase Configuration ---
FIREBASE_DB_URL = os.getenv("FIREBASE_DB_URL", "").rstrip("/")
if not FIREBASE_DB_URL:
    raise RuntimeError("CRITICAL: FIREBASE_DB_URL is not configured in the environment.")

# The path within your database where the application data will be stored.
DATA_PATH = "/store/data"

DEFAULT_STORE = {
    "availability": {},
    "bookings": [],
    "counsellors": [],
}

def load_data():
    """
    Loads the entire data store from a single key in Firebase Realtime Database.
    If no data exists, it returns the default structure.
    """
    try:
        url = f"{FIREBASE_DB_URL}{DATA_PATH}.json"
        response = requests.get(url, timeout=8)
        response.raise_for_status()
        data = response.json()
        
        if data is None:
            return DEFAULT_STORE.copy()
        
        for key in DEFAULT_STORE:
            if key not in data:
                data[key] = DEFAULT_STORE[key]
        return data

    except requests.exceptions.RequestException as e:
        print(f"[data_store_utils] Firebase read error: {e}")
        return DEFAULT_STORE.copy()

def save_data(data):
    """
    Saves the entire data store to a single key in Firebase using a PUT request,
    which overwrites the existing data at that path.
    """
    try:
        url = f"{FIREBASE_DB_URL}{DATA_PATH}.json"
        response = requests.put(url, data=json.dumps(data), timeout=8)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"[data_store_utils] Firebase write error: {e}")
