import streamlit as st
import paho.mqtt.client as mqtt
import json
import time
import queue
from ews_logic import calculate_news, get_risk_level

# -------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------
st.set_page_config(page_title="Project Nebula", layout="wide")
st.title("🏥 PROJECT NEBULA: 5G SMART WARD")

# -------------------------------------------------
# MQQT & DATA STORAGE
# -------------------------------------------------
@st.cache_resource
def get_mailbox():
    return queue.Queue()

mailbox = get_mailbox()

if "beds" not in st.session_state:
    st.session_state.beds = {}

def on_message(client, userdata, msg):
    try:
        mailbox.put(msg.payload.decode())
    except:
        pass

@st.cache_resource
def start_mqtt():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "Nebula_Final_Fix_v3")
    client.on_message = on_message
    client.connect("broker.hivemq.com", 1883, 60)
    client.subscribe("nebula/ward1/bed/#")
    client.loop_start()
    return client

client = start_mqtt()

# UI Placeholders
sidebar_area = st.sidebar.empty()
metrics_area = st.empty()
grid_area = st.empty()

# -------------------------------------------------
# MAIN LOOP
# -------------------------------------------------
while True:
    now = time.time()

    # 1. PROCESS ALL MESSAGES IN QUEUE
    while not mailbox.empty():
        try:
            raw_msg = mailbox.get_nowait()
            data = json.loads(raw_msg)
            b_id = data['id']
            
            # NEWS Scoring logic
            sys_bp = int(data['bp'].split('/')[0]) if 'bp' in data else 120
            n_score = calculate_news(data['hr'], data['spo2'], sys_bp, data['temp'])
            r_color, r_label = get_risk_level(n_score)
            
            # Update data with fresh calculations
            st.session_state.beds[b_id] = {
                **data,
                "news_score": n_score,
                "risk_color": r_color,
                "risk_label": r_label,
                "is_critical": (n_score >= 7 or data.get('status') == "CRITICAL"),
                "last_seen": now
            }
        except:
            continue

    # 2. CLEANUP STALE DATA (Remove beds inactive for > 7 seconds)
    st.session_state.beds = {
        k: v for k, v in st.session_state.beds.items() 
        if now - v.get('last_seen', 0) < 7
    }

    # 3. SORT & FILTER (The "Real" Solution)
    # Re-calculate these every loop so counts are ALWAYS accurate
    all_active_beds = list(st.session_state.beds.values())
    
    # Sort by Score (High to Low)
    sorted_beds = sorted(all_active_beds, key=lambda x: x['news_score'], reverse=True)
    
    # Critical List (Only truly critical ones)
    critical_beds = [b for b in sorted_beds if b['is_critical']]

    # 4. RENDER SIDEBAR
    with sidebar_area.container():
        st.header("🚨 Live Critical Alerts")
        st.error(f"Total Critical: {len(critical_beds)}")
        
        for bed in critical_beds:
            st.markdown(f"""
            <div style="border:1px solid red; padding:10px; border-radius:5px; background:#2b0000; margin-bottom:5px;">
                <b>{bed['id']}</b> | NEWS: {bed['news_score']}<br>
                HR: {bed['hr']} | SpO2: {bed['spo2']}%
            </div>
            """, unsafe_allow_html=True)
        if not critical_beds:
            st.success("No Critical Patients")

    # 5. RENDER MAIN DASHBOARD
    with metrics_area.container():
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Active Beds", len(all_active_beds))
        c2.metric("Critical Alerts", len(critical_beds))
        c3.metric("System Health", "STABLE")
        st.divider()

    with grid_area.container():
        cols = st.columns(4)
        for i, bed in enumerate(sorted_beds):
            with cols[i % 4]:
                card_bg = "#330000" if bed['is_critical'] else "#0e1117"
                card_border = "2px solid red" if bed['is_critical'] else "1px solid #444"
                
                st.markdown(f"""
                <div style="border:{card_border}; background:{card_bg}; padding:15px; border-radius:10px; margin-bottom:10px;">
                    <h3 style="margin:0;">{bed['id']}</h3>
                    <p style="margin:5px 0;">Score: <b style="color:{bed['risk_color']}">{bed['news_score']} ({bed['risk_label']})</b></p>
                    <hr style="opacity:0.2;">
                    ❤️ HR: {bed['hr']}<br>
                    💨 SpO2: {bed['spo2']}%<br>
                    🌡️ Temp: {bed['temp']}°C
                </div>
                """, unsafe_allow_html=True)

    time.sleep(1)