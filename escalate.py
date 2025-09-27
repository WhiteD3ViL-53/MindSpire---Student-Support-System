# escalate.py — Flask endpoint to perform escalation actions (calls / bridge / SMS)
# Usage: run this as a Flask app (e.g. python escalate.py) and expose it publicly (ngrok or server)
# Requirements: pip install flask requests python-dotenv twilio
import os, time, json, requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# Config
FIREBASE_DB_URL = os.getenv("FIREBASE_DB_URL", "").rstrip("/")
TW_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TW_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TW_FROM = os.getenv("TWILIO_NUMBER", "")
COUNSELLOR_NUMBER = os.getenv("COUNSELLOR_NUMBER", "")
ESCALATE_SECRET = os.getenv("ESCALATE_SECRET", "")
CALL_EVENTS_URL = os.getenv("CALL_EVENTS_URL", "")  # optional: Twilio will post here for status callbacks

# Basic check
if not FIREBASE_DB_URL:
    raise RuntimeError("FIREBASE_DB_URL not configured in env")

# Twilio client lazy import
try:
    from twilio.rest import Client as TwClient
    tw_client = TwClient(TW_SID, TW_TOKEN) if TW_SID and TW_TOKEN else None
except Exception:
    tw_client = None

def fb_patch(path, data):
    url = f"{FIREBASE_DB_URL}/{path}.json"
    try:
        r = requests.patch(url, json=data, timeout=6)
        return r.ok
    except Exception as e:
        return False

def fb_post(path, data):
    url = f"{FIREBASE_DB_URL}/{path}.json"
    try:
        r = requests.post(url, json=data, timeout=6)
        return r.json()
    except Exception as e:
        return {}

def fb_get(path):
    url = f"{FIREBASE_DB_URL}/{path}.json"
    try:
        r = requests.get(url, timeout=6)
        return r.json() or {}
    except:
        return {}

def log_attempt(esc_key, attempt_id, entry):
    # writes under escalations/{esc_key}/attempts/{attempt_id}
    fb_patch(f"escalations/{esc_key}/attempts/{attempt_id}", entry)
    # update last_tw_snapshot timestamp
    fb_patch(f"escalations/{esc_key}", {"last_tw_fetched_at": int(time.time())})

@app.route("/escalate", methods=["POST"])
def escalate():
    # Simple secret header auth
    if ESCALATE_SECRET:
        secret = request.headers.get("X-ESCALATE-SECRET") or request.args.get("secret")
        if secret != ESCALATE_SECRET:
            return jsonify({"error":"unauthorized"}), 401

    body = request.get_json() or {}
    esc_id = body.get("esc_id") or ("esc_" + uuid_hex())
    message = body.get("message", "")[:1000]
    callback_number = body.get("callback_number")  # may be None
    channel = body.get("channel", "unknown")
    ts = int(time.time())

    # ensure escalation exists in firebase (create minimal record if absent)
    existing = fb_get(f"escalations/{esc_id}") or {}
    if not existing:
        # create minimal escalation record
        esc = {
            "id": esc_id,
            "channel": channel,
            "last_message_excerpt": message[:400],
            "requested_at": ts,
            "user_consent": bool(callback_number),
            "callback_number": callback_number,
            "user_online": False,
            "status": "pending",
            "attempts": {}
        }
        fb_patch(f"escalations/{esc_id}", esc)
    else:
        # update fields if provided
        update = {"last_message_excerpt": message[:400], "user_online": False}
        if callback_number:
            update.update({"callback_number": callback_number, "user_consent": True})
        fb_patch(f"escalations/{esc_id}", update)

    # 1) Immediately notify counsellor by placing a brief Twilio call
    if tw_client and COUNSELLOR_NUMBER and TW_FROM:
        try:
            # TwiML to tell counsellor to check dashboard and mention esc_id
            twiml = f"<Response><Say voice='alice'>Alert. Escalation {esc_id} received. Check dashboard for details.</Say></Response>"
            call = tw_client.calls.create(
                to=COUNSELLOR_NUMBER,
                from_=TW_FROM,
                twiml=twiml,
                status_callback=CALL_EVENTS_URL or "",  # optional
                status_callback_event=["completed","answered","no-answer","failed"] if CALL_EVENTS_URL else None
            )
            attempt_id = call.sid or "counsellor_" + str(int(time.time()))
            log_attempt(esc_id, attempt_id, {
                "type":"call",
                "target":"counsellor",
                "to":COUNSELLOR_NUMBER,
                "from":TW_FROM,
                "status":"queued",
                "ts": ts,
                "call_sid": call.sid
            })
        except Exception as e:
            fb_patch(f"escalations/{esc_id}/attempts", {"notify_fail_"+str(ts): {"type":"notify","error": str(e), "ts":ts}})

    # 2) If callback_number provided, attempt to bridge user & counsellor via Twilio Conference (masked)
    if callback_number and tw_client and TW_FROM:
        conf_name = f"esc_conf_{esc_id}"
        try:
            # Call user into conference
            user_call = tw_client.calls.create(
                to=callback_number,
                from_=TW_FROM,
                twiml=f"<Response><Say voice='alice'>You are being connected to a counsellor for emergency support. Please stay on the line.</Say><Dial><Conference>{conf_name}</Conference></Dial></Response>",
                status_callback=CALL_EVENTS_URL or "",
                status_callback_event=["completed","answered","no-answer","failed"] if CALL_EVENTS_URL else None
            )
            log_attempt(esc_id, user_call.sid, {
                "type":"call",
                "target":"user",
                "to": callback_number,
                "from": TW_FROM,
                "status":"queued",
                "ts": ts,
                "call_sid": user_call.sid,
                "conference": conf_name
            })
            # Call counsellor into same conference
            if COUNSELLOR_NUMBER:
                counselor_call = tw_client.calls.create(
                    to=COUNSELLOR_NUMBER,
                    from_=TW_FROM,
                    twiml=f"<Response><Say voice='alice'>Connecting you to an escalation. Conference: {conf_name}.</Say><Dial><Conference>{conf_name}</Conference></Dial></Response>",
                    status_callback=CALL_EVENTS_URL or "",
                    status_callback_event=["completed","answered","no-answer","failed"] if CALL_EVENTS_URL else None
                )
                log_attempt(esc_id, counselor_call.sid, {
                    "type":"call",
                    "target":"counsellor",
                    "to": COUNSELLOR_NUMBER,
                    "from": TW_FROM,
                    "status":"queued",
                    "ts": ts,
                    "call_sid": counselor_call.sid,
                    "conference": conf_name
                })
        except Exception as e:
            # If conference failed, fallback to SMS to user
            try:
                if tw_client:
                    sms = tw_client.messages.create(
                        to=callback_number,
                        from_=TW_FROM,
                        body=f"We noticed you may be in crisis. We attempted to call you for Escalation {esc_id}. If you want support, reply or use this link: <your-portal-url>?esc={esc_id}"
                    )
                    log_attempt(esc_id, "sms_"+str(int(time.time())), {
                        "type":"sms",
                        "to": callback_number,
                        "from": TW_FROM,
                        "status":"sent",
                        "ts": int(time.time()),
                        "sid": sms.sid
                    })
            except Exception as e2:
                fb_patch(f"escalations/{esc_id}/attempts", {"fallback_fail_"+str(int(time.time())): {"error": str(e2), "ts": int(time.time())}})

    return jsonify({"ok":True, "esc_id": esc_id})

def uuid_hex():
    import uuid
    return uuid.uuid4().hex

if __name__ == "__main__":
    # run on port 8000 by default
    app.run(host="0.0.0.0", port=int(os.getenv("ESCALATE_PORT", 8000)), debug=True)
