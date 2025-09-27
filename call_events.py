# call_events.py — Twilio status callback collector (stores events into escalation attempts)
from flask import Flask, request, jsonify
import os, requests, time
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

FIREBASE_DB_URL = os.getenv("FIREBASE_DB_URL", "").rstrip("/")

def fb_patch(path, data):
    url = f"{FIREBASE_DB_URL}/{path}.json"
    try:
        r = requests.patch(url, json=data, timeout=6)
        return r.ok
    except:
        return False

def fb_post(path, data):
    url = f"{FIREBASE_DB_URL}/{path}.json"
    try:
        r = requests.post(url, json=data, timeout=6)
        return r.json()
    except:
        return {}

def fb_get(path):
    url = f"{FIREBASE_DB_URL}/{path}.json"
    try:
        r = requests.get(url, timeout=6)
        return r.json() or {}
    except:
        return {}

@app.route("/call-events", methods=["POST"])
def call_events():
    # Twilio POST contains fields such as CallSid, CallStatus, To, From, ConferenceSid etc.
    data = request.form.to_dict() or request.json or {}
    # Attempt to find escalation by conference name or by metadata
    call_sid = data.get("CallSid") or data.get("CallSid")
    call_status = data.get("CallStatus") or data.get("CallStatus")
    conference_name = data.get("ConferenceSid") or data.get("ConferenceName") or data.get("Conference")
    to_num = data.get("To")
    from_num = data.get("From")
    ts = int(time.time())

    # Simple heuristic: search for escalation which had an attempt with this call_sid
    # If not found, try to match by conference name contained in attempt entries
    # Gather all escalations (note: in prod, use indexed lookups)
    try:
        escs = fb_get("escalations") or {}
        target_esc = None
        target_attempt_key = None
        for k, v in (escs.items() if isinstance(escs, dict) else []):
            attempts = v.get("attempts", {}) or {}
            for aid, a in attempts.items():
                if aid == call_sid:
                    target_esc = k
                    target_attempt_key = aid
                    break
                # sometimes call_sid stored inside attempt object under call_sid field
                if isinstance(a, dict) and a.get("call_sid") == call_sid:
                    target_esc = k
                    target_attempt_key = aid
                    break
                # try conference name match
                if conference_name and isinstance(a, dict) and a.get("conference") and conference_name in str(a.get("conference")):
                    target_esc = k
                    target_attempt_key = aid
                    break
            if target_esc:
                break

        # fallback: if conference_name present, look for matching conf
        if not target_esc and conference_name:
            for k, v in (escs.items() if isinstance(escs, dict) else []):
                attempts = v.get("attempts", {}) or {}
                for aid, a in attempts.items():
                    if isinstance(a, dict) and a.get("conference") == conference_name:
                        target_esc = k
                        target_attempt_key = aid
                        break
                if target_esc:
                    break

        # If found, patch the attempt with status info
        if target_esc and target_attempt_key:
            patch = {
                "status": call_status,
                "last_event_ts": ts,
                "raw": data
            }
            fb_patch(f"escalations/{target_esc}/attempts/{target_attempt_key}", patch)
            # also update top-level status snapshot
            fb_patch(f"escalations/{target_esc}", {"last_tw_snapshot": {target_attempt_key: patch}, "last_tw_fetched_at": ts})
        else:
            # If we couldn't match, write to a generic call_events log (useful for debugging)
            fb_post("call_events_unmatched", {"call_sid": call_sid, "status": call_status, "to": to_num, "from": from_num, "raw": data, "ts": ts})
    except Exception as e:
        # best effort logging
        try:
            fb_post("call_events_errors", {"error": str(e), "raw": data, "ts": ts})
        except:
            pass

    # keep Twilio happy
    return jsonify({"ok": True}), 200

if __name__ == "__main__":
    app.run(port=int(os.getenv("CALL_EVENTS_PORT", 5001)), debug=True, host="0.0.0.0")
