# peer_chat.py — updated for crisis escalation and improved UI
# Drop into same folder as your other modules. Requires: requests, python-dotenv
import streamlit as st
import requests, time, uuid, hashlib, os
from dotenv import load_dotenv

load_dotenv()
FIREBASE_DB_URL = os.getenv("FIREBASE_DB_URL", "").rstrip("/")
MOD_SECRET = os.getenv("MODERATOR_SECRET", "mod_secret")
ESCALATE_ENDPOINT = os.getenv("ESCALATE_ENDPOINT", "http://localhost:8000/escalate")
ESCALATE_SECRET = os.getenv("ESCALATE_SECRET", "")

# Channels for the MVP
CHANNELS = {
    "lobby": "👋 Main Lobby",
    "exams": "📚 Exam Anxiety",
    "parents": "👨‍👩‍👧‍👦 Parental Pressure",
    "peer": "👥 Peer Pressure",
    "relationship": "❤️ Relationship Issues",
    "general": "💬 General Support"
}

# --- Utility functions ---
def make_token():
    if "token" not in st.session_state:
        t = uuid.uuid4().hex
        st.session_state["token"] = t
        seed = hashlib.sha1(t.encode()).digest()[0]
        st.session_state["display_name"] = f"{['Oak','Ash','Pine','Maple'][seed%4]}-{str(abs(hash(t)))[-3:]}"
    return st.session_state["token"]

def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()

def firebase_patch(path, data):
    url = f"{FIREBASE_DB_URL}/{path}.json"
    try:
        requests.patch(url, json=data, timeout=6)
    except Exception:
        pass

def firebase_post(path, data):
    url = f"{FIREBASE_DB_URL}/{path}.json"
    try:
        r = requests.post(url, json=data, timeout=6)
        return r.json()
    except Exception:
        return {}

def firebase_get(path):
    url = f"{FIREBASE_DB_URL}/{path}.json"
    try:
        r = requests.get(url, timeout=6)
        return r.json() or {}
    except:
        return {}

# --- Simple filters / heuristics ---
PROFANITY = ["idiot","stupid","fuck"]
CRISIS_WORDS = ["kill myself","suicide","end my life","i want to die","im going to kill myself","i'm going to kill myself","want to end my life"]

def scan_message_for_risk(text):
    lower = text.lower()
    if any(kw in lower for kw in CRISIS_WORDS): return "crisis"
    if any(kw in lower for kw in PROFANITY): return "profanity"
    return "ok"

# --- Data interaction functions ---
def create_escalation_record(channel, token, display_name, message_excerpt):
    esc = {
        "id": "esc_" + uuid.uuid4().hex, "channel": channel, "token_hash": token_hash(token),
        "display_name": display_name, "last_message_excerpt": message_excerpt[:400],
        "requested_at": int(time.time()), "user_consent": False, "callback_number": None,
        "user_online": True, "last_seen_ts": int(time.time()), "status": "pending", "notes": ""
    }
    resp = firebase_post("escalations", esc)
    if isinstance(resp, dict) and "name" in resp:
        key = resp["name"]
        esc["id"] = key
        firebase_patch(f"escalations/{key}", {"id": key})
        return key
    return esc.get("id")

def update_escalation(esc_id, data):
    firebase_patch(f"escalations/{esc_id}", data)

def post_message(channel, token, name, text, auto_tag=None):
    msg = {
        "msg_id": uuid.uuid4().hex, "token_hash": token_hash(token), "display_name": name,
        "text": text, "created_at": int(time.time()), "auto_tag": auto_tag or ""
    }
    firebase_post(f"channels/{channel}/messages", msg)

def report_message(channel, msg_id, reason):
    firebase_post(f"flags/{channel}/{msg_id}", {"reason": reason, "ts": int(time.time()), "msg_id": msg_id})

def delete_message(channel, msg_id):
    firebase_patch(f"deleted/{channel}/{msg_id}", {"deleted": True, "ts": int(time.time())})

# --- UI DIALOG FOR CRISIS ESCALATION ---
@st.dialog("Immediate Support Required")
def show_escalation_dialog(esc_key, message_text):
    st.error("Crisis language detected in your message. A counsellor has been notified.")
    st.info("If you would like an immediate callback, please provide a phone number below. This is optional and will only be used for this emergency.")
    
    phone = st.text_input("Phone for emergency call (e.g., +9199...)", key=f"phone_{esc_key}")
    consent = st.checkbox("I consent to being contacted for emergency support regarding this matter.", key=f"consent_{esc_key}")

    if st.button("Submit Request", type="primary"):
        if consent:
            update_escalation(esc_key, {
                "user_consent": True, "callback_number": phone if phone else None, "last_seen_ts": int(time.time())
            })
            try:
                headers = {"Content-Type": "application/json"}
                if ESCALATE_SECRET: headers["X-ESCALATE-SECRET"] = ESCALATE_SECRET
                payload = {"esc_id": esc_key, "message": message_text[:800], "callback_number": phone or None, "channel": st.session_state.channel}
                requests.post(ESCALATE_ENDPOINT, json=payload, headers=headers, timeout=6)
                st.toast("✅ Request sent to counsellor. They will attempt to reach you.", icon="✅")
            except Exception:
                st.toast("Error: Could not contact escalation service. Please use emergency services.", icon="🚨")
        else:
            st.toast("A counsellor has been notified but you have not consented to a callback.", icon="ℹ️")
        st.rerun()

# ---- MAIN PUBLIC FUNCTION TO RUN CHAT UI ----
def run_chat():
    if not FIREBASE_DB_URL:
        st.error("FIREBASE_DB_URL not configured. Set it in your .env file.")
        return

    # --- CSS for Chat Bubbles and Layout ---
    st.markdown("""
        <style>
            :root { --user-bg: #172d42; --bot-bg: #262730; --crisis-bg: #421717; }
            .sidebar-card { background: rgba(255, 255, 255, 0.05); padding: 16px; border-radius: 12px; margin-bottom: 16px; }
            .chat-container { display: flex; flex-direction: column; gap: 12px; }
            .message-container { display: flex; flex-direction: column; padding: 10px 14px; border-radius: 12px; max-width: 80%; }
            .message-container.current-user { background-color: var(--user-bg); align-self: flex-end; }
            .message-container.other-user { background-color: var(--bot-bg); align-self: flex-start; }
            .message-container.bot { background-color: #0e2133; border-left: 3px solid #1c5885; }
            .message-container.crisis { background-color: var(--crisis-bg); border-left: 3px solid #b52929; }
            .message-author { font-weight: bold; font-size: 14px; margin-bottom: 4px; }
            .message-timestamp { font-size: 11px; color: #a1a1a1; align-self: flex-end; }
            .message-actions button { font-size: 12px; padding: 2px 8px; }
        </style>
    """, unsafe_allow_html=True)

    make_token()
    my_token_hash = token_hash(st.session_state["token"])

    # --- Main Layout ---
    col1, col2 = st.columns([2.5, 1])

    with col2: # Right-hand panel
        with st.container():
            st.markdown("<div class='sidebar-card'>", unsafe_allow_html=True)
            st.subheader("Channels")
            channel = st.radio("Select a channel:", list(CHANNELS.keys()), format_func=lambda k: CHANNELS[k], index=0, key="channel", label_visibility="collapsed")
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("<div class='sidebar-card'>", unsafe_allow_html=True)
            st.subheader("Your Identity")
            st.write(f"**Name:** `{st.session_state['display_name']}`")
            if st.button("Get New Anonymous Identity", use_container_width=True):
                st.session_state.pop("token", None)
                make_token()
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

            is_moderator = st.toggle("Enable Moderator Mode")
            if is_moderator:
                mod_pw = st.text_input("Moderator Secret:", type="password")
                is_moderator = (mod_pw == MOD_SECRET)
                if mod_pw and not is_moderator: st.warning("Incorrect secret.")

    with col1: # Left-hand chat panel
        st.subheader(CHANNELS[channel])

        # --- Message Display Area ---
        with st.container(height=500):
            st.markdown("<div class='chat-container'>", unsafe_allow_html=True)
            msgs_data = firebase_get(f"channels/{channel}/messages") or {}
            deleted = firebase_get(f"deleted/{channel}") or {}
            
            msgs = sorted([v | {"_key": k} for k, v in msgs_data.items()], key=lambda m: m.get("created_at",0))

            for m in msgs[-100:]: # Display last 100 messages
                msg_key = m.get("_key")
                if deleted.get(msg_key): continue

                is_me = m.get("token_hash") == my_token_hash
                is_bot = m.get("token_hash") == "bot"
                is_crisis = m.get("auto_tag") == "crisis"
                
                align_class = "current-user" if is_me else "other-user"
                type_class = "bot" if is_bot else "crisis" if is_crisis else ""
                
                st.markdown(f"<div class='message-container {align_class} {type_class}'>", unsafe_allow_html=True)
                st.markdown(f"<div class='message-author'>{m.get('display_name','Anon')}</div>", unsafe_allow_html=True)
                st.markdown(m.get("text",""))
                st.markdown(f"<div class='message-timestamp'>{time.strftime('%H:%M', time.localtime(m.get('created_at',0)))}</div>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

                if not is_me: # Actions for messages from others
                    action_cols = st.columns([1,1,5])
                    with action_cols[0]:
                        if st.button("Report", key=f"r-{msg_key}", use_container_width=True):
                            report_message(channel, msg_key, "user_reported")
                            st.toast("Message reported to moderators.", icon="🚩")
                    if is_moderator:
                        with action_cols[1]:
                            if st.button("Delete", key=f"d-{msg_key}", use_container_width=True):
                                delete_message(channel, msg_key)
                                st.toast("Message deleted.", icon="🗑️")
                                st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("---")
        
        # --- Message Input Form ---
        with st.form("msg_form", clear_on_submit=True):
            txt = st.text_area("Your message:", height=100, placeholder="Share your thoughts anonymously...")
            submitted = st.form_submit_button("Send Message", use_container_width=True, type="primary")

            if submitted and txt.strip():
                risk_type = scan_message_for_risk(txt)
                if risk_type == "crisis":
                    esc_key = create_escalation_record(channel, st.session_state["token"], st.session_state["display_name"], txt)
                    post_message(channel, st.session_state["token"], st.session_state["display_name"], txt, auto_tag="crisis")
                    show_escalation_dialog(esc_key, txt)
                elif risk_type == "profanity":
                    post_message(channel, st.session_state["token"], st.session_state["display_name"], txt, auto_tag="profanity")
                    st.toast("Please maintain a supportive tone in your messages.", icon="👋")
                else:
                    post_message(channel, st.session_state["token"], st.session_state["display_name"], txt)
                
                time.sleep(0.5) # Allow firebase time to update
                st.rerun()