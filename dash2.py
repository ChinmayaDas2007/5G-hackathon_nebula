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
# THREAD-SAFE MAILBOX
# -------------------------------------------------
@st.cache_resource
def get_mailbox():
    return queue.Queue()

mailbox = get_mailbox()

# -------------------------------------------------
# MQTT SETUP
# -------------------------------------------------
def on_message(client, userdata, msg):
    try:
        mailbox.put(msg.payload.decode())
    except:
        pass

@st.cache_resource
def start_mqtt():
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "Nebula_Dash_Final_Fix")
        client.on_message = on_message
        client.connect("broker.hivemq.com", 1883, 60)
        client.subscribe("nebula/ward1/bed/#")
        client.loop_start()
        return client
    except:
        return None

client = start_mqtt()

# -------------------------------------------------
# SESSION STATE & LAYOUT CONTAINERS
# -------------------------------------------------
if "data" not in st.session_state:
    st.session_state.data = {}

# Define placeholders ONCE to prevent duplication
main_placeholder = st.empty()
sidebar_placeholder = st.sidebar.empty()

# -------------------------------------------------
# MAIN DASHBOARD LOOP
# -------------------------------------------------
while True:
    current_time = time.time()
    
    # --- STEP 1: HIGH-SPEED BATCH UPDATE (The Fix) ---
    # Instead of updating session_state 50 times (slow), 
    # we collect all updates in a local dict and update ONCE.
    batch_updates = {}
    
    # Drain the ENTIRE queue instantly
    while not mailbox.empty():
        try:
            payload = json.loads(mailbox.get())
            bed_id = payload["id"]
            
            # Helper: Parse Sys BP safely
            if "bp" in payload and isinstance(payload["bp"], str):
                try:
                    payload["sys_bp"] = int(payload["bp"].split("/")[0])
                except:
                    payload["sys_bp"] = 120
            else:
                payload["sys_bp"] = 120
            
            # Store in batch (overwriting previous messages for this bed)
            batch_updates[bed_id] = payload
        except:
            pass
    
    # Update the main state with the batch
    if batch_updates:
        st.session_state.data.update(batch_updates)

    # --- STEP 2: REMOVE OFFLINE BEDS (Ghost Protocol) ---
    # If a bed hasn't sent data in 5 seconds, delete it.
    offline_beds = []
    for bed_id, info in st.session_state.data.items():
        last_seen = info.get("timestamp", 0)
        if current_time - last_seen > 5.0:  # 5 Second Timeout
            offline_beds.append(bed_id)
            
    for bed_id in offline_beds:
        del st.session_state.data[bed_id]

    # --- STEP 3: RECALCULATE LOGIC ---
    processed_beds = []
    
    for bed_id, info in st.session_state.data.items():
        # 1. Extract Vitals
        hr = info.get("hr", 0)
        spo2 = info.get("spo2", 98)
        sys_bp = info.get("sys_bp", 120)
        temp = info.get("temp", 37.0)
        
        # 2. Calculate NEWS Score
        news_score = calculate_news(hr, spo2, sys_bp, temp)
        risk_color, risk_label = get_risk_level(news_score)
        
        # 3. Determine Criticality (Status Flag OR High Score)
        is_critical = (info.get("status") == "CRITICAL") or (risk_color == "RED")
        
        processed_beds.append({
            "id": bed_id,
            "info": info,
            "news_score": news_score,
            "risk_color": risk_color,
            "risk_label": risk_label,
            "is_critical": is_critical
        })

    # Sort: Critical -> NEWS Score -> ID
    sorted_beds = sorted(processed_beds, key=lambda x: (not x['is_critical'], -x['news_score'], x['id']))
    
    # Filter Critical List (Freshly calculated)
    critical_list = [b for b in sorted_beds if b['is_critical']]

    # --- STEP 4: RENDER SIDEBAR ---
    with sidebar_placeholder.container():
        st.header("🚨 CRITICAL ALERTS")
        st.caption(f"Active Critical Cases: {len(critical_list)}")
        
        if not critical_list:
            st.success("All Patients Stable")
        else:
            for bed in critical_list:
                info = bed['info']
                st.markdown(f"""
                <div style="border:2px solid #ff4b4b; background-color:#2d0e0e; padding:10px; border-radius:5px; margin-bottom:10px;">
                    <strong>{bed['id']}</strong>
                    <br>Score: <b style="color:#ff4b4b">{bed['news_score']}</b>
                    <br><span style="font-size:0.8em">HR: {info.get('hr')} | SpO2: {info.get('spo2')}%</span>
                </div>
                """, unsafe_allow_html=True)

    # --- STEP 5: RENDER MAIN DASHBOARD ---
    with main_placeholder.container():
        # Summary Metrics
        c1, c2, c3 = st.columns(3)
        c1.metric("Active Beds", len(sorted_beds))
        c2.metric("Critical Patients", len(critical_list))
        c3.metric("System Status", "ONLINE", delta="Live 5G")
        st.divider()

        # Grid Layout
        cols = st.columns(5)
        for i, bed in enumerate(sorted_beds):
            with cols[i % 5]:
                info = bed['info']
                status = info.get("status", "NORMAL")
                
                # Dynamic Styling
                border_color = "red" if bed['is_critical'] else "#444"
                bg_color = "#2a0a0a" if bed['is_critical'] else "#0e1117"
                badge_color = "#e74c3c" if status == "CRITICAL" else "#27ae60"
                
                st.markdown(f"""
                <div style="border:1px solid {border_color}; background-color:{bg_color}; padding:10px; border-radius:8px; margin-bottom:10px;">
                    <div style="display:flex; justify-content:space-between;">
                        <b>{bed['id']}</b>
                        <span style="background:{badge_color}; color:white; padding:1px 6px; border-radius:4px; font-size:0.7em;">{status}</span>
                    </div>
                    <div style="margin-top:5px; font-size:0.9em;">
                        ❤️ {info.get('hr')} | 💨 {info.get('spo2')}%<br>
                        🩸 {info.get('bp')} | 🌡️ {info.get('temp')}
                    </div>
                    <div style="margin-top:5px; border-top:1px solid #333; padding-top:5px; font-size:0.8em; color:#aaa;">
                        RISK: <b style="color:{bed['risk_color']}">{bed['risk_label']}</b>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # Refresh Rate (Slightly slower to allow batching)
    time.sleep(1)