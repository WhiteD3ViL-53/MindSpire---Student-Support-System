# mental.py — MindSpire (Student dashboard) — Final Version
# Save to same folder as peer_chat.py, data_store_utils.py, .env
# Requirements: pip install streamlit requests python-dotenv

import os
from datetime import datetime
import secrets
import string
import uuid
import hashlib
import time

import streamlit as st
import streamlit.components.v1 as components
import requests
from dotenv import load_dotenv

from data_store_utils import load_data, save_data

# Optional peer_chat integration
try:
    import peer_chat
    _PEER_CHAT_AVAILABLE = True
except Exception:
    peer_chat = None
    _PEER_CHAT_AVAILABLE = False

load_dotenv()

# -----------------------
# Constants
# -----------------------
# Define view names as constants for easier maintenance
VIEW_CHAT = "Chatbot"
VIEW_BOOKING = "Book Counsellor"
VIEW_FORUM = "Peer Support Forum"
VIEW_RESOURCES_AV = "Audio/Video Library"
VIEW_RESOURCES_EXERCISES = "Guided Exercises"
VIEW_RESOURCES_PLAYHUB = "PlayHub (Beta)"

# -----------------------
# Firebase helper (optional)
# -----------------------
FIREBASE_DB_URL = os.getenv("FIREBASE_DB_URL", "").rstrip("/")

def fb_post(path, data):
    if not FIREBASE_DB_URL: return {}
    try:
        r = requests.post(f"{FIREBASE_DB_URL}/{path}.json", json=data, timeout=6)
        return r.json() or {}
    except Exception: return {}

def fb_patch(path, data):
    if not FIREBASE_DB_URL: return {}
    try:
        r = requests.patch(f"{FIREBASE_DB_URL}/{path}.json", json=data, timeout=6)
        return r.json() or {}
    except Exception: return {}

def fb_get(path):
    if not FIREBASE_DB_URL: return {}
    try:
        r = requests.get(f"{FIREBASE_DB_URL}/{path}.json", timeout=6)
        return r.json() or {}
    except Exception: return {}

# -----------------------
# Page config + CSS
# -----------------------
st.set_page_config(page_title="MindSpire — Student", layout="wide", initial_sidebar_state="collapsed")
st.markdown(
    """
    <style>
    :root{--bg:#081026;--card:#0b1220;--muted:#cfe8ff;--accent:#173247}
    body { background-color: var(--bg); color: #e6eef8; }
    .main-wrap { max-width:1100px; margin:12px auto; padding:8px; }
    .full-card { background: linear-gradient(180deg, rgba(11,18,32,0.95), rgba(6,10,18,0.95)); border-radius:14px; padding:22px; margin-bottom:16px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
    .small-muted { color:#9fb8d9; font-size:13px; margin-bottom: 8px; }
    .slot-box { width:100%; height:56px; border-radius:8px; display:flex; align-items:center; justify-content:center; font-weight:700; }
    .slot-lunch { background: linear-gradient(180deg,#3f4750,#2b3137); color:#e6eef8; opacity:0.95; }
    .resource-card { background:#071021; border-radius:12px; padding:14px; box-shadow: 0 8px 20px rgba(0,0,0,0.5); height: 100%; display: flex; flex-direction: column; justify-content: space-between;}
    .resource-title { font-weight:700; color:#e6eef8; margin-bottom:6px; }
    .card-center-title { text-align: center; }
    .booking-token-display { font-size: 14px; font-weight: bold; text-align: center; color: #a6ffaf; letter-spacing: 1px; font-family: monospace; padding: 4px; background-color: rgba(30, 127, 52, 0.3); border-radius: 4px; margin-bottom: 8px; }
    
    /* CSS for Bigger Emoji Buttons */
    .stButton button {
        border-radius: 12px;
    }
    .mood-button button {
        font-size: 26px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .mood-text {
        text-align: center;
        font-weight: bold;
        font-size: 1.1em;
        margin-top: 10px;
    }
    @media (max-width:900px){ .resource-grid { grid-template-columns: 1fr; } }
    </style>
    """, unsafe_allow_html=True,
)

# -----------------------
# Data and State Setup
# -----------------------
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
SLOTS = ["9-10 AM", "10-11 AM", "11-12 PM", "12-1 PM", "1-2 PM", "2-3 PM", "3-4 PM", "4-5 PM", "5-6 PM"]
LUNCH_SLOT_INDEX = SLOTS.index("1-2 PM")
today_idx = datetime.now().weekday()

def make_token(n=8): return "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(n))
def key(d, s): return f"{d}_{s}"
def is_past_locked(d): return d < today_idx

# Initialize all session state variables
for key_ in ["show_chat", "show_booking", "show_forum"]:
    if key_ not in st.session_state: st.session_state[key_] = False
for key_ in ["active_resource_view", "active_resource"]:
    if key_ not in st.session_state: st.session_state[key_] = None
if "bookmarks" not in st.session_state: st.session_state.bookmarks = set()
if "selected_mood" not in st.session_state: st.session_state.selected_mood = 3 # Default to 'Okay'

# Load shared data store
store = load_data()
for d in range(7):
    for s in range(len(SLOTS)):
        if key(d, s) not in store["availability"]:
            store["availability"][key(d, s)] = not is_past_locked(d)
save_data(store)

# -----------------------
# Resources List
# -----------------------
RESOURCES = [
    {"id":"v1","title":"Study Tips: Beat Exam Stress","desc":"Short practical techniques to reduce exam anxiety and study more effectively.","tags":["study","stress","exams"],"type":"video","url":"https://youtu.be/Jk4WpJpjq7k?si=1uEEMycG3OLXiA3q"},
    {"id":"v2","title":"Active Revision Techniques","desc":"Learn active recall and spaced repetition tricks to boost retention.","tags":["study","revision"],"type":"video","url":"https://youtu.be/izJ3yhXPJ60?si=F2hVzpxUH9KTfWlp"},
    {"id":"v3","title":"Time Management for Students","desc":"How to plan study blocks, breaks and get more done with less stress.","tags":["productivity","planning"],"type":"video","url":"https://youtu.be/APS6t-auzM4?si=pXy-akR5jrefQgpk"},
    {"id":"v4","title":"Focus & Concentration Exercises","desc":"Short exercises to improve focus during study sessions.","tags":["focus","exercise"],"type":"video","url":"https://youtu.be/zklPS8qlW6c?si=p4Gjfmdh_gNm8TDp"},
    {"id":"ncert","title":"NCERT Resources","desc":"Official NCERT textbooks and resources (national curriculum materials).","tags":["ncert","textbook"],"type":"link","url":"https://ncert.nic.in/"},
    {"id":"v5","title":"Short Mindfulness Break (5 min)","desc":"A short guided grounding exercise to calm nerves and re-centre.","tags":["mindfulness","breathing"],"type":"video","url":"https://youtu.be/mdo19qOX-E4?si=LLcpUOqDGbOQsBbv"},
    {"id":"v6","title":"Guided Breathing for Stress","desc":"Simple breathing practice to reduce acute stress and nervousness.","tags":["breathing","relaxation"],"type":"video","url":"https://youtu.be/Nlz8yKG0ySU?si=d8He7OH82EC7ugvT"},
    {"id":"v7","title":"Quick Grounding Audio","desc":"A short grounding audio to use between study sessions.","tags":["audio","grounding"],"type":"video","url":"https://youtu.be/eAK14VoY7C0?si=35IjvElVRG-ID0mK"},
    {"id":"v8","title":"Study Break Movement","desc":"Two-minute movement routine to refresh posture and attention.","tags":["movement","wellbeing"],"type":"video","url":"https://youtu.be/deAIK86Hyxk?si=YBrcNiJP8ahMsvY8"},
    {"id":"v9","title":"Sleep & Memory Tips","desc":"Short tips to improve sleep quality for better learning and memory.","tags":["sleep","health"],"type":"video","url":"https://youtu.be/bPM-FDTuit8?si=14VV0WiujOV5cul0"},
    {"id":"v10","title":"7-minute Focus Practice","desc":"A short practice to build concentration and reduce distractibility.","tags":["focus","practice"],"type":"video","url":"https://youtu.be/iyY_LVKfOO0?si=YW8dfJtEwmLMdV1j"},
    {"id":"v11","title":"Calm Your Mind — Guided Short","desc":"Brief guided exercise to de-escalate anxious thoughts.","tags":["anxiety","calm"],"type":"video","url":"https://youtu.be/hzvT0vy5cjE?si=YeFeCEkoI0LDb2bn"},
    {"id":"v12","title":"Study Motivation & Habits","desc":"How to form small habits that keep motivation steady over time.","tags":["motivation","habits"],"type":"video","url":"https://youtu.be/N6NlJgSf7r0?si=cuFk13rIaLy3mWY6"},
    {"id":"v13","title":"Active Note-taking Strategies","desc":"Effective note patterns to make reviewing faster and clearer.","tags":["notes","study"],"type":"video","url":"https://youtu.be/RJHZ01TzY9M?si=NMPskFPf8NT1vHdx"},
    {"id":"v14","title":"Stress-to-Action: Small Steps","desc":"How to convert stress into small practical steps you can take now.","tags":["stress","action"],"type":"video","url":"https://youtu.be/7NLfpsNHmZI?si=zCBGbc4h9AHg4bX8"},
    {"id":"gm1","title":"Guided Meditation — Self-Love","desc":"A gentle guided meditation to build self-compassion and calm.","tags":["meditation","self-love"],"type":"video","url":"https://youtu.be/vj0JDwQLof4?si=-3AI1c7f60JKhcSn"},
    {"id":"gm2","title":"Guided Relaxation — Body Scan","desc":"A short body scan meditation to relieve tension and stress.","tags":["meditation","relaxation"],"type":"video","url":"https://youtu.be/sfSDQRdIvTc?si=JAWlk4la8ZtV0D-K"},
    {"id":"gm3","title":"Breathing & Grounding Session","desc":"Breath-led grounding practice for quick resets during the day.","tags":["meditation","breathing"],"type":"video","url":"https://youtu.be/uNmKzlh55Fo?si=fPV3KbDffre6ttBn"},
    {"id":"gm4","title":"Short Guided Calm (video)","desc":"A concise calm practice for pre-sleep or study breaks.","tags":["meditation","calm"],"type":"video","url":"https://youtu.be/C4bofW53sO8?si=yinXXWC4CqahOwDx"},
    {"id":"gm5","title":"Self-care Meditation (7 min)","desc":"Self-care focused practice to improve mood and perspective.","tags":["meditation","self-care"],"type":"video","url":"https://youtu.be/blbv5UTBCGg?si=W0W6QvTILD6kNMUl"},
    {"id":"mi1","title":"Mindset: Controlling Thoughts 1","desc":"Techniques for noticing and gently redirecting unhelpful thoughts.","tags":["mindset","thoughts"],"type":"video","url":"https://youtu.be/22wpwgpy7fY?si=ZbUXEGNZeD7p0gl5"},
    {"id":"mi2","title":"Cognitive Strategies for Focus","desc":"How to shift thinking patterns that distract from study.","tags":["mindset","focus"],"type":"video","url":"https://youtu.be/U_ilabJbPKU?si=IvpT9vNE9G6vEHZA"},
    {"id":"mi3","title":"Thought Reframing Basics","desc":"Short guide to reframing negative thoughts into neutral steps.","tags":["reframing","cbt"],"type":"video","url":"https://youtu.be/nqxviz_G4Uo?si=KLfVRcmmQxIK_eD8"},
    {"id":"mi4","title":"Sustaining Attention Techniques","desc":"Practical steps to keep attention from wandering during work.","tags":["attention","techniques"],"type":"video","url":"https://youtu.be/KzW84p4bCzA?si=stKdsbcfW81c9-TF"},
    {"id":"mi5","title":"Managing Overthinking","desc":"Short methods to interrupt overthinking cycles and ground yourself.","tags":["overthinking","mindset"],"type":"video","url":"https://youtu.be/nnSRJ5PRPWQ?si=W20BQjBabnR80pqX"},
    {"id":"pod1","title":"Mental Health Podcast — Ep.1","desc":"A thoughtful conversation about coping with stress and study life.","tags":["podcast","mental-health"],"type":"video","url":"https://youtu.be/MFyEwdpC5pM?si=Ts-jLPxH5FvnaaAP"},
    {"id":"pod2","title":"Mental Health Podcast — Ep.2","desc":"Stories, tips and small steps from mental health practitioners.","tags":["podcast","support"],"type":"video","url":"https://youtu.be/9EqrUK7ghho?si=ydVsJeRZFjsqQVS-"},
    {"id":"pod3","title":"Mental Health Podcast — Tools","desc":"Practical tools for everyday wellbeing and stress management.","tags":["podcast","tools"],"type":"video","url":"https://youtu.be/Kqya9ql7hM0?si=DKuKPTpQzOO3-ytj"},
    {"id":"pod4","title":"Mental Health Podcast — Study Life","desc":"Advice for students balancing study and wellbeing.","tags":["podcast","students"],"type":"video","url":"https://youtu.be/YcGXViwXItM?si=mhATIev5NxG-XHlC"},
    {"id":"pod5","title":"Mental Health Podcast — Self-care","desc":"Episode focused on self-care routines that actually work.","tags":["podcast","self-care"],"type":"video","url":"https://youtu.be/YWBuwJTuWGo?si=FFfthEyOYEa4N8Vs"},
]

# -----------------------
# Helper Functions
# -----------------------

def create_mood_check(score, note):
    """Saves a mood check record to the data store."""
    rec = { "id": "mood_" + uuid.uuid4().hex, "score": int(score), "note": note or "", "ts": int(time.time()) }
    if FIREBASE_DB_URL: fb_post("mood_checks", rec)
    store.setdefault("mood_checks", []).append(rec)
    save_data(store)

def display_resources_ui(resource_list, section_title):
    """Renders the UI for browsing and filtering resources."""
    st.markdown("Search, filter, and save resources to your bookmarks. Everything is anonymous.")
    q_col, tag_col, view_col = st.columns([5, 3, 2])
    query = q_col.text_input("Search", placeholder="Search titles...", key=f"query_{section_title}", label_visibility="collapsed")
    all_tags = sorted({tag for r in resource_list for tag in r.get("tags", [])})
    selected_tags = tag_col.multiselect("Filter by tags", all_tags, key=f"tags_{section_title}")
    view_choice = view_col.radio("View", ["All", "Bookmarked"], index=0, key=f"view_{section_title}")

    def matches(r):
        if view_choice == "Bookmarked" and r["id"] not in st.session_state.bookmarks: return False
        if selected_tags and not set(selected_tags).issubset(set(r.get("tags", []))): return False
        if query and not (query.lower() in r["title"].lower() or query.lower() in r["desc"].lower()): return False
        return True

    filtered_resources = [r for r in resource_list if matches(r)]
    st.markdown(f"Found **{len(filtered_resources)}** resource(s).")
    st.markdown("---")
    
    if not filtered_resources:
        st.info("No resources match your search criteria.")
    else:
        cols = st.columns(3)
        for i, res in enumerate(filtered_resources):
            with cols[i % 3]:
                st.markdown(f"<div class='resource-card'><div class='resource-title'>{res['title']}</div><div class='small-muted'>{res['desc']}</div>", unsafe_allow_html=True)
                b_col1, b_col2 = st.columns(2)
                if b_col1.button("Open", key=f"res_{res['id']}", use_container_width=True): 
                    st.session_state.active_resource = res['id']
                    st.rerun()
                is_bookmarked = res['id'] in st.session_state.bookmarks
                if b_col2.button("✓ Saved" if is_bookmarked else "Save", key=f"bm_{res['id']}", use_container_width=True, type="secondary"):
                    st.session_state.bookmarks.remove(res['id']) if is_bookmarked else st.session_state.bookmarks.add(res['id'])
                    st.toast("Bookmarks updated!")
                    st.rerun()
                st.markdown("</div><br/>", unsafe_allow_html=True)

    if st.session_state.active_resource:
        active_res = next((r for r in RESOURCES if r['id'] == st.session_state.active_resource), None)
        if active_res:
            with st.expander("Now viewing: " + active_res['title'], expanded=True):
                if active_res['type'] == 'video': st.video(active_res['url'])
                else: st.markdown(f"➡️ [Open Link in New Tab]({active_res['url']})")
                if st.button("Close Viewer"):
                    st.session_state.active_resource = None
                    st.rerun()

def handle_nav_switch():
    """Callback function to switch between full-screen views."""
    selection = st.session_state.get("nav_switcher")
    if not selection or selection == "— Switch to another view —": return
    st.session_state.show_chat = (selection == VIEW_CHAT)
    st.session_state.show_booking = (selection == VIEW_BOOKING)
    st.session_state.show_forum = (selection == VIEW_FORUM)
    st.session_state.active_resource_view = selection if selection.startswith(("Audio", "Guided", "PlayHub")) else None

def render_fullscreen_nav(current_view_title):
    """Renders the universal navigation header for all full-screen views."""
    view_options = [VIEW_CHAT, VIEW_BOOKING, VIEW_FORUM, VIEW_RESOURCES_AV, VIEW_RESOURCES_EXERCISES, VIEW_RESOURCES_PLAYHUB]
    c1, c2, c3 = st.columns([4, 3, 3])
    with c1: st.markdown(f"<h2>{current_view_title}</h2>", unsafe_allow_html=True)
    with c2: st.selectbox("Switch to:", options=["— Switch to another view —"] + view_options, key="nav_switcher", on_change=handle_nav_switch, label_visibility="collapsed")
    with c3:
        if st.button("✖ Close & Return to Dashboard", use_container_width=True, type="secondary"):
            st.session_state.show_chat, st.session_state.show_booking, st.session_state.show_forum, st.session_state.active_resource_view, st.session_state.active_resource = False, False, False, None, None
            st.rerun()
    st.markdown("---")

# -----------------------
# FULL-SCREEN VIEW ROUTER
# -----------------------

if st.session_state.show_chat:
    render_fullscreen_nav("MindSpire Chat")
    botpress_url = "https://cdn.botpress.cloud/webchat/v3.2/shareable.html?configUrl=https://files.bpcontent.cloud/2025/09/13/22/20250913220458-U8RB73H5.json"
    components.html(f'<style>iframe{{height:calc(100vh - 150px)}}</style><iframe src="{botpress_url}" style="width:100%; border:0;" allow="microphone; camera;"></iframe>', height=700)
    st.stop()

if st.session_state.show_booking:
    render_fullscreen_nav("Book a Counsellor")
    header_cols = st.columns([1.5] + [1 for _ in SLOTS])
    header_cols[0].markdown("<strong>Day</strong>", unsafe_allow_html=True)
    for i, s in enumerate(SLOTS): header_cols[i+1].markdown(f"<div style='text-align:center;font-weight:700'>{s}</div>", unsafe_allow_html=True)
    st.markdown("---")

    for d_idx, day in enumerate(DAYS):
        row_cols = st.columns([1.5] + [1 for _ in SLOTS])
        row_cols[0].markdown(f"<h4>{day}</h4>", unsafe_allow_html=True)
        for s_idx, slot_label in enumerate(SLOTS):
            with row_cols[s_idx+1]:
                if s_idx == LUNCH_SLOT_INDEX:
                    st.markdown("<div class='slot-box slot-lunch'>Lunch</div>", unsafe_allow_html=True)
                elif is_past_locked(d_idx):
                    st.button("Past", key=f"past_{d_idx}_{s_idx}", use_container_width=True, disabled=True)
                elif store["availability"].get(key(d_idx, s_idx)):
                    if st.button("Book", key=f"book_{d_idx}_{s_idx}", use_container_width=True, type="primary"):
                        token = make_token(8)
                        store["availability"][key(d_idx, s_idx)] = False
                        store.setdefault("bookings", []).append({"day": d_idx, "slot": s_idx, "token": token, "time": datetime.now().isoformat()})
                        save_data(store)
                        st.toast(f"✅ Booked! Your token: {token}", icon="✅")
                        time.sleep(2)
                        st.rerun()
                else:
                    booking_record = next((b for b in store.get("bookings", []) if b.get("day") == d_idx and b.get("slot") == s_idx), None)
                    if booking_record:
                        st.markdown(f"<div class='booking-token-display'>{booking_record['token']}</div>", unsafe_allow_html=True)
                        if st.button("Cancel", key=f"cancel_{d_idx}_{s_idx}", use_container_width=True, type="secondary"):
                            store["availability"][key(d_idx, s_idx)] = True
                            store["bookings"] = [b for b in store["bookings"] if not (b["day"] == d_idx and b["slot"] == s_idx)]
                            save_data(store)
                            st.toast(f"✅ Booking for {day} at {slot_label} cancelled.", icon="✅")
                            time.sleep(2)
                            st.rerun()
                    else:
                        st.button("Booked", key=f"unavailable_{d_idx}_{s_idx}", use_container_width=True, disabled=True)
    st.stop()

if st.session_state.show_forum:
    render_fullscreen_nav(VIEW_FORUM)
    if _PEER_CHAT_AVAILABLE: peer_chat.run_chat()
    else: st.error("Peer chat module not found.")
    st.stop()

if st.session_state.active_resource_view:
    render_fullscreen_nav(st.session_state.active_resource_view)
    if st.session_state.active_resource_view == VIEW_RESOURCES_AV:
        display_resources_ui([r for r in RESOURCES if r.get("type") in ["video", "audio", "link", "podcast"]], VIEW_RESOURCES_AV)
    elif st.session_state.active_resource_view == VIEW_RESOURCES_EXERCISES:
        tags = ["exercise", "breathing", "mindfulness", "relaxation", "meditation", "grounding", "calm"]
        display_resources_ui([r for r in RESOURCES if any(t in r.get("tags", []) for t in tags)], VIEW_RESOURCES_EXERCISES)
    elif st.session_state.active_resource_view == VIEW_RESOURCES_PLAYHUB:
        st.info("Relaxing games and puzzles to de-stress. This feature is in development.")
        components.html('<div class="full-card" style="text-align:center;"><h4>Coming Soon!</h4></div>', height=150)
    st.stop()

# -----------------------
# MAIN PAGE DASHBOARD
# -----------------------
st.markdown('<div class="main-wrap">', unsafe_allow_html=True)
c1, c2 = st.columns([1, 8])
logo_path = "MindSpire.png" if os.path.exists("MindSpire.png") else "logo.png"
if os.path.exists(logo_path):
    with c1: st.image(logo_path, width=120)
with c2:
    st.title("MindSpire Student Support")
    st.markdown("A prototype for mental wellbeing, designed for students.")
st.markdown("---")

# --- Quick Mood Check Card (with big emoji buttons) ---
st.markdown('<div class="full-card">', unsafe_allow_html=True)
st.markdown("<h4>Quick Mood Check</h4>", unsafe_allow_html=True)
st.markdown("<div class='small-muted'>A simple, anonymous check-in to help us understand campus wellbeing.</div>", unsafe_allow_html=True)

mood_options = {
    1: {"emoji": "😔", "label": "Very low"}, 2: {"emoji": "😟", "label": "Low"},
    3: {"emoji": "😐", "label": "Okay"}, 4: {"emoji": "🙂", "label": "Good"},
    5: {"emoji": "😊", "label": "Very good"}
}

cols = st.columns(5)
for value, mood in mood_options.items():
    with cols[value-1]:
        is_selected = (st.session_state.selected_mood == value)
        if st.button(mood["emoji"], key=f"mood_btn_{value}", use_container_width=True, type="primary" if is_selected else "secondary"):
            st.session_state.selected_mood = value
            st.rerun()

st.markdown(f"<div class='mood-text'>{mood_options[st.session_state.selected_mood]['label']}</div>", unsafe_allow_html=True)
st.markdown("<br/>", unsafe_allow_html=True)

note_col, submit_col = st.columns([3, 1])
with note_col:
    mood_note = st.text_input("Optional note:", key="mood_note_input", placeholder="Anything on your mind?", label_visibility="collapsed")
with submit_col:
    if st.button("Submit Mood", key="submit_mood_final", use_container_width=True, type="primary"):
        create_mood_check(st.session_state.selected_mood, mood_note)
        st.toast("✅ Thanks, your mood has been recorded!", icon="✅")
        time.sleep(2)
        st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

# --- Navigation Cards ---
c1, c2 = st.columns(2)
with c1:
    st.markdown('<div class="full-card">', unsafe_allow_html=True)
    st.markdown("<h4 class='card-center-title'>🤖 Talk to Chatbot</h4>", unsafe_allow_html=True)
    st.markdown("<div class='small-muted'>Confidential, empathetic chat for immediate support.</div>", unsafe_allow_html=True)
    if st.button("Open Chatbot", use_container_width=True):
        st.session_state.show_chat = True
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
with c2:
    st.markdown('<div class="full-card">', unsafe_allow_html=True)
    st.markdown("<h4 class='card-center-title'>📅 Book Counsellor</h4>", unsafe_allow_html=True)
    st.markdown("<div class='small-muted'>Schedule a confidential session with campus services.</div>", unsafe_allow_html=True)
    if st.button("Book a Session", use_container_width=True):
        st.session_state.show_booking = True
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

c1, c2 = st.columns(2)
with c1:
    st.markdown('<div class="full-card">', unsafe_allow_html=True)
    st.markdown("<h4 class='card-center-title'>👥 Peer Support Forum</h4>", unsafe_allow_html=True)
    st.markdown("<div class='small-muted'>Connect anonymously with fellow students in moderated channels.</div>", unsafe_allow_html=True)
    if st.button("Open Forum", use_container_width=True):
        st.session_state.show_forum = True
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
with c2:
    st.markdown('<div class="full-card">', unsafe_allow_html=True)
    st.markdown("<h4 class='card-center-title'>📚 Resources Hub</h4>", unsafe_allow_html=True)
    st.markdown("<div class='small-muted'>Curated guides, videos, and exercises for wellbeing.</div>", unsafe_allow_html=True)
    def set_resource_view():
        choice = st.session_state.resource_selector
        if choice != "— Select a category —": st.session_state.active_resource_view = choice
    st.selectbox("Explore:", ("— Select a category —", VIEW_RESOURCES_AV, VIEW_RESOURCES_EXERCISES, VIEW_RESOURCES_PLAYHUB), key="resource_selector", on_change=set_resource_view, label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)

# --- Footer ---
st.markdown('---')
st.caption("© 2025 MindSpire — For demonstration purposes only. If you are in crisis, please contact local emergency services immediately.")

st.markdown('</div>', unsafe_allow_html=True)
