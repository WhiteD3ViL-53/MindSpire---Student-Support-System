# Admin.py — MindSpire Admin / Counsellor Dashboard (with Auto-Refresh & Analytics)
# Save this file in the same folder as your project files (data_store_utils.py, .env, etc.)
# Requirements: pip install streamlit requests python-dotenv twilio pandas

import io
import csv
import os
import time
import json
import logging
from datetime import datetime
import pandas as pd

import streamlit as st
import requests
from dotenv import load_dotenv

from data_store_utils import load_data, save_data

load_dotenv()

# -----------------------
# Page config & styles
# -----------------------
st.set_page_config(page_title="MindSpire — Admin Dashboard", layout="wide")
st.markdown(
    """
    <style>
    :root{--bg:#081026;--card:#0b1220;--muted:#cfe8ff}
    body { background-color: var(--bg); color: #e6eef8; }
    .admin-wrap { max-width:1300px; margin:8px auto; }
    .admin-panel { background: linear-gradient(180deg, rgba(11,18,32,0.95), rgba(6,10,18,0.95)); padding:18px; border-radius:12px; box-shadow:0 10px 30px rgba(0,0,0,0.5); }
    .slot-box { width:100%; height:48px; border-radius:8px; display:flex; align-items:center; justify-content:center; font-weight:700; }
    .slot-available { background: linear-gradient(180deg,#1e7f34,#166826); color:#fff; }
    .slot-unavailable { background: linear-gradient(180deg,#b02a2a,#8a1f1f); color:#fff; }
    .slot-lunch { background: linear-gradient(180deg,#3f4750,#2b3137); color:#e6eef8; opacity:0.95; }
    .escalation-card { background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.1); padding:16px; border-radius:10px; margin-bottom:12px; }
    .small-muted { color:#9fb8d9; font-size:13px; }
    </style>
    """,
    unsafe_allow_html=True,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("admin")

# -----------------------
# Firebase helpers
# -----------------------
FIREBASE_DB_URL = os.getenv("FIREBASE_DB_URL", "").rstrip("/")

def fb_url(path: str) -> str:
    if not FIREBASE_DB_URL: raise RuntimeError("FIREBASE_DB_URL not configured in .env")
    return f"{FIREBASE_DB_URL}/{path}.json"

def fb_get(path: str):
    try:
        r = requests.get(fb_url(path), timeout=8)
        r.raise_for_status()
        return r.json() or {}
    except Exception as e:
        logger.exception(f"fb_get error for {path}: {e}")
        return {}

def fb_patch(path: str, data):
    try:
        r = requests.patch(fb_url(path), json=data, timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.exception(f"fb_patch error for {path}: {e}")
        return None

# -----------------------
# Local store & constants
# -----------------------
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
SLOTS = ["9-10 AM", "10-11 AM", "11-12 PM", "12-1 PM", "1-2 PM", "2-3 PM", "3-4 PM", "4-5 PM", "5-6 PM"]
LUNCH_SLOT_INDEX = SLOTS.index("1-2 PM")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "adminpass")

if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = False

# -----------------------
# Sidebar login
# -----------------------
st.sidebar.title("Admin Login")
pw = st.sidebar.text_input("Enter admin password", type="password")
if not pw:
    st.sidebar.info("Enter password to continue.")
    st.stop()
if pw != ADMIN_PASSWORD:
    st.sidebar.error("Incorrect password.")
    st.stop()

# -----------------------
# Admin UI
# -----------------------
st.markdown('<div class="admin-wrap">', unsafe_allow_html=True)
st.header("MindSpire — Admin / Counsellor Dashboard")
st.markdown("<div class='admin-panel'>", unsafe_allow_html=True)

tabs = st.tabs(["📊 Overview & Analytics", "📅 Bookings", "🗓️ Availability", "👥 Counsellors", "🚨 Escalations", "📋 Reports"])

def persist_and_rerun():
    """Saves data and reruns the app for a smooth refresh."""
    save_data(load_data()) # Save the current state of the store
    st.toast("Success!")
    time.sleep(1)
    st.rerun()

# --- Overview & Analytics ---
with tabs[0]:
    store = load_data() # Ensure data is fresh on each tab switch
    escs_data = fb_get("escalations") or {}

    c1, c2 = st.columns([3,1])
    with c1:
        st.subheader("Key Metrics")
    with c2:
        st.session_state.auto_refresh = st.checkbox("Enable Auto-Refresh (15s)", key="refresh_toggle_overview")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Bookings This Week", str(len(store.get("bookings", []))))
    pending_escs = [e for e in escs_data.values() if e.get("status") == "pending"]
    c2.metric("Pending Escalations", str(len(pending_escs)))
    c3.metric("Configured Counsellors", str(len(store.get("counsellors", []))))
    st.markdown("---")
    
    st.subheader("📊 Weekly Analytics")
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.markdown("##### Bookings by Day")
        bookings_df = pd.DataFrame(store.get("bookings", []))
        if not bookings_df.empty:
            bookings_per_day = bookings_df['day'].value_counts().sort_index()
            bookings_per_day.index = bookings_per_day.index.map(lambda d: DAYS[d])
            st.bar_chart(bookings_per_day)
        else:
            st.caption("No booking data to display.")

    with chart_col2:
        st.markdown("##### Escalations by Status")
        if escs_data:
            escs_df = pd.DataFrame(escs_data.values())
            status_counts = escs_df['status'].value_counts()
            st.bar_chart(status_counts)
        else:
            st.caption("No escalation data to display.")

# --- Bookings ---
with tabs[1]:
    store = load_data()
    st.subheader("Manage Bookings")
    st.markdown("To delete a booking, select its row and press the `Delete` key.")
    
    bookings = store.get("bookings", [])
    if not bookings:
        st.info("No bookings yet.")
    else:
        df_display = pd.DataFrame(bookings)
        df_display['Day'] = df_display['day'].apply(lambda x: DAYS[x])
        df_display['Time Slot'] = df_display['slot'].apply(lambda x: SLOTS[x])
        df_display = df_display[['Day', 'Time Slot', 'token', 'time']]
        df_display.rename(columns={'token': 'Booking Token', 'time': 'Timestamp'}, inplace=True)
        
        edited_df = st.data_editor(df_display, num_rows="dynamic", use_container_width=True, hide_index=True, key="booking_editor")
        
        if len(edited_df) < len(df_display):
            st.toast("Processing deletion...")
            original_tokens = set(df_display['Booking Token'])
            edited_tokens = set(edited_df['Booking Token'])
            deleted_tokens = original_tokens - edited_tokens
            
            new_bookings = [b for b in store['bookings'] if b['token'] not in deleted_tokens]
            
            for token in deleted_tokens:
                deleted_booking = next((b for b in store['bookings'] if b['token'] == token), None)
                if deleted_booking:
                    store['availability'][f"{deleted_booking['day']}_{deleted_booking['slot']}"] = True

            store['bookings'] = new_bookings
            persist_and_rerun()

# --- Availability ---
with tabs[2]:
    store = load_data()
    st.subheader("Manage Weekly Availability")
    for d_idx, day in enumerate(DAYS):
        cols = st.columns([1.2] + [1 for _ in SLOTS])
        cols[0].markdown(f"**{day}**")
        for s_idx, slot_label in enumerate(SLOTS):
            with cols[s_idx+1]:
                if s_idx == LUNCH_SLOT_INDEX:
                    st.markdown("<div class='slot-box slot-lunch'>Lunch</div>", unsafe_allow_html=True)
                elif store.get("availability", {}).get(f"{d_idx}_{s_idx}", True):
                    if st.button("Available", key=f"avail_{d_idx}_{s_idx}", use_container_width=True, type="primary"):
                        store["availability"][f"{d_idx}_{s_idx}"] = False
                        persist_and_rerun()
                else:
                    if st.button("Unavailable", key=f"unavail_{d_idx}_{s_idx}", use_container_width=True, type="secondary"):
                        store["availability"][f"{d_idx}_{s_idx}"] = True
                        persist_and_rerun()

# --- Counsellors ---
with tabs[3]:
    store = load_data()
    st.subheader("Manage Counsellors")
    for c in list(store.get("counsellors", [])):
        cols = st.columns([4, 1])
        cols[0].markdown(f"**{c.get('name')}** — {c.get('specialty')}")
        if cols[1].button(f"Remove", key=f"remc_{c.get('id')}"):
            store["counsellors"] = [x for x in store["counsellors"] if x.get("id") != c.get("id")]
            persist_and_rerun()
    
    with st.form("add_counsellor", clear_on_submit=True):
        st.subheader("Add New Counsellor")
        nc_name = st.text_input("Name")
        nc_spec = st.text_input("Specialty")
        if st.form_submit_button("Add Counsellor", type="primary"):
            new_id = max([c.get("id", 0) for c in store.get("counsellors", [])] + [0]) + 1
            store.setdefault("counsellors", []).append({"id": new_id, "name": nc_name, "specialty": nc_spec})
            persist_and_rerun()

# --- Escalations ---
with tabs[4]:
    c1, c2 = st.columns([3,1])
    with c1:
        st.subheader("Crisis Escalations")
    with c2:
        st.session_state.auto_refresh = st.checkbox("Enable Auto-Refresh (15s)", key="refresh_toggle_escalations")
        
    escs = fb_get("escalations") or {}
    
    if not escs:
        st.info("No escalations found.")
    else:
        esc_list = sorted(escs.values(), key=lambda x: x.get("requested_at", 0), reverse=True)
        for esc in esc_list:
            with st.container():
                st.markdown("<div class='escalation-card'>", unsafe_allow_html=True)
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"**ID:** `{esc.get('id', 'N/A')}` | **Status:** `{esc.get('status', 'pending')}`")
                    st.markdown(f"**Message:** *'{esc.get('last_message_excerpt', '...')}'*")
                with c2:
                    if st.button("Mark Completed", key=f"complete_{esc.get('id')}", use_container_width=True):
                        fb_patch(f"escalations/{esc.get('id')}", {"status": "completed"})
                        st.rerun()
                    if st.button("Mark No Answer", key=f"noans_{esc.get('id')}", use_container_width=True, type="secondary"):
                        fb_patch(f"escalations/{esc.get('id')}", {"status": "no_answer"})
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

# --- Reports ---
with tabs[5]:
    store = load_data()
    st.subheader("Download Reports")
    if st.button("Export Bookings to CSV"):
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["Day", "Time Slot", "Booking Token", "Timestamp"])
        for b in store.get("bookings", []):
            writer.writerow([DAYS[b["day"]], SLOTS[b["slot"]], b.get("token", ""), b.get("time", "")])
        st.download_button("Download bookings.csv", data=buf.getvalue(), file_name="bookings.csv", mime="text/csv")

    if st.button("Export Escalations to JSON"):
        escs_data = fb_get("escalations") or {}
        content = json.dumps(escs_data, indent=2)
        st.download_button("Download escalations.json", data=content, file_name="escalations.json", mime="application/json")

st.markdown("</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# Auto-refresh logic at the end of the script
if st.session_state.auto_refresh:
    time.sleep(15)
    st.rerun()