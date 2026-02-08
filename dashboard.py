import streamlit as st
import paho.mqtt.client as mqtt
import json
import time
import queue
import pandas as pd
from patient_db import generate_patient_db
from ehr_manager import EHRManager

# --- PAGE CONFIG ---
st.set_page_config(page_title="Project Nebula", layout="wide", page_icon="🏥")
st.title("🏥 PROJECT NEBULA: 5G SMART WARD")

# --- INIT GLOBAL STATE ---
if "patient_db" not in st.session_state:
    st.session_state.patient_db = generate_patient_db(50)

if "ehr" not in st.session_state:
    st.session_state.ehr = EHRManager()

if "beds" not in st.session_state: 
    st.session_state.beds = {}

if "selected_patient" not in st.session_state:
    st.session_state.selected_patient = None

# --- SHARED FUNCTIONS ---
def get_risk_level(score):
    if score >= 7: return "#FF0000", "CRITICAL"
    elif score >= 5: return "#FF8C00", "URGENT"
    elif score >= 1: return "#FFD700", "MONITOR"
    return "#00FF00", "STABLE"

def calculate_news(hr, pulse, spo2, sys_bp, temp, rr):
    score = 0
    if rr <= 8 or rr >= 25: score += 3
    elif 21 <= rr <= 24: score += 2
    elif 9 <= rr <= 11: score += 1
    if spo2 <= 91: score += 3
    elif 92 <= spo2 <= 93: score += 2
    elif 94 <= spo2 <= 95: score += 1
    if sys_bp <= 90: score += 3
    elif 91 <= sys_bp <= 100: score += 2
    elif 101 <= sys_bp <= 110: score += 1
    elif sys_bp >= 220: score += 3
    if hr <= 40: score += 3
    elif 131 <= hr: score += 3
    elif 111 <= hr <= 130: score += 2
    elif 41 <= hr <= 50: score += 1
    elif 91 <= hr <= 110: score += 1
    if temp <= 35.0: score += 3
    elif temp >= 39.1: score += 2
    elif 35.1 <= temp <= 36.0: score += 1
    elif 38.1 <= temp <= 39.0: score += 1
    return score

# --- MQTT SETUP ---
@st.cache_resource
def get_mailbox(): return queue.Queue()
mailbox = get_mailbox()

def on_message(client, userdata, msg):
    try: mailbox.put(msg.payload.decode())
    except: pass

@st.cache_resource
def start_mqtt():
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "Nebula_Dash_Viewer")
        client.on_message = on_message
        client.connect("broker.hivemq.com", 1883, 60)
        client.subscribe("nebula/ward1/bed/#")
        client.loop_start()
        return client
    except: return None

client = start_mqtt()

# --- DATA PROCESSING ENGINE ---
def process_and_save_data():
    """Reads MQTT queue, updates State, and Saves to EHR DB."""
    now = time.time()
    while not mailbox.empty():
        try:
            payload = mailbox.get_nowait()
            data = json.loads(payload)
            
            bid = data.get('id', 'Unknown')
            hr = int(data.get('hr', 0))
            pulse = int(data.get('pulse', hr)) 
            spo2 = int(data.get('spo2', 98))
            temp = float(data.get('temp', 37.0))
            rr = int(data.get('rr', 16))
            bp_str = data.get('bp', "120/80")
            try: sys_bp = int(bp_str.split('/')[0])
            except: sys_bp = 120

            score = calculate_news(hr, pulse, spo2, sys_bp, temp, rr)
            color, label = get_risk_level(score)

            # SAVE TO EHR
            st.session_state.ehr.log_vitals(bid, hr, spo2, bp_str, temp, score, label)

            # UPDATE LIVE STATE
            st.session_state.beds[bid] = {
                **data, "news": score, "color": color, "label": label, "last": now
            }
        except Exception:
            continue

# --- SIDEBAR ALERTS (GLOBAL) ---
process_and_save_data() # Quick update on load
now = time.time()
# Filter Active Beds (Seen in last 60s)
active_beds = [b for k,b in st.session_state.beds.items() if (now - b['last'] < 60)]
sorted_beds = sorted(active_beds, key=lambda x: x['id'])
critical_beds = [b for b in sorted_beds if b['news'] >= 7 or b.get('status') == "CRITICAL"]

page = st.sidebar.radio("Navigation", ["🟢 Live Monitor", "📂 Patient Database"])

sidebar_placeholder = st.sidebar.empty()
with sidebar_placeholder.container():
    if critical_beds:
        st.header(f"🚨 Alerts ({len(critical_beds)})")
        for b in critical_beds:
            st.error(f"{b['id']} | NEWS: {b['news']} | {b['label']}")

# ==============================================================================
#  PAGE 1: PATIENT DATABASE
# ==============================================================================
if page == "📂 Patient Database":
    
    process_and_save_data() # Ensure background recording

    if st.session_state.selected_patient:
        selected_bed = st.session_state.selected_patient
        
        if st.button("⬅️ Back to Patient Grid"):
            st.session_state.selected_patient = None
            st.rerun()
            
        st.header(f"📄 EHR Record: {selected_bed}")
        
        p_row = st.session_state.patient_db[st.session_state.patient_db['Bed ID'] == selected_bed]
        
        if not p_row.empty:
            p_info = p_row.iloc[0]
            base_score = p_info.get('Baseline NEWS', 0)
            base_color, base_status = get_risk_level(base_score)

            # FORCE WHITE TEXT COLOR
            st.markdown(f"""
            <div style="background-color: #262730; padding: 20px; border-radius: 10px; border: 1px solid #444; color: white !important;">
                <h2 style="margin:0; color:#4DA6FF;">{p_info['Name']}</h2>
                <div style="font-size: 1.1em; margin-top: 10px; color: #ffffff;">
                    <b>Age:</b> {p_info['Age']} &nbsp;|&nbsp; 
                    <b>Condition:</b> {p_info['Condition']}
                </div>
                <hr style="border-color:#555;">
                <div style="color: #ffffff;">
                    <b>Baseline Assessment:</b> 
                    <span style="background-color:{base_color}; color:black; padding:2px 6px; border-radius:4px; font-weight:bold;">{base_status}</span> 
                    (NEWS Score: {base_score})
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            st.write("") 

            history_df = st.session_state.ehr.get_patient_history(selected_bed)
            
            if not history_df.empty:
                st.subheader("📈 Clinical Vitals Trends")
                history_df['timestamp'] = pd.to_datetime(history_df['timestamp'])
                chart_data = history_df[['timestamp', 'hr', 'spo2']].set_index('timestamp')
                st.line_chart(chart_data, color=["#FF0000", "#00FFFF"]) 
                
                with st.expander("View Raw Data Logs"):
                    st.dataframe(history_df.sort_values(by='timestamp', ascending=False), use_container_width=True)
            else:
                st.info("No live telemetry recorded yet. Please wait for incoming data...")
        else:
            st.error("Patient not found in database.")

    else:
        st.header("📂 Patient Directory")
        st.markdown("Select a patient to view detailed Electronic Health Records.")
        
        patients = st.session_state.patient_db.to_dict('records')
        cols = st.columns(4)
        for i, p in enumerate(patients):
            with cols[i % 4]:
                score = p.get('Baseline NEWS', 0)
                color, label = get_risk_level(score)
                
                st.markdown(f"""
                <div style="border: 1px solid #444; border-radius: 8px; padding: 15px; background-color: #1e1e1e; margin-bottom: 10px;">
                    <h4 style="margin:0; color:white;">{p['Bed ID']}</h4>
                    <div style="font-size:1.1em; font-weight:bold; color:#aaa; margin-bottom:5px;">{p['Name']}</div>
                    <div style="font-size:0.9em; color:#888;">{p['Condition']}</div>
                    <div style="margin-top:10px;">
                        <span style="background:{color}; color:black; padding:3px 8px; border-radius:4px; font-weight:bold; font-size:0.8em;">{label}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button(f"📂 Open EHR", key=f"btn_{p['Bed ID']}"):
                    st.session_state.selected_patient = p['Bed ID']
                    st.rerun()

    time.sleep(1)
    st.rerun()

# ==============================================================================
#  PAGE 2: LIVE MONITOR
# ==============================================================================
elif page == "🟢 Live Monitor":
    st.markdown("### 🧭 Live Monitor")
    st.markdown("---")

    metrics_placeholder = st.empty()
    grid_placeholder = st.empty()

    while True:
        # 1. PROCESS DATA
        process_and_save_data()
        
        # 2. RECALCULATE LIST & FIX KEYERROR
        now = time.time()
        active_beds_list = [b for k,b in st.session_state.beds.items() if (now - b['last'] < 60)]
        
        # *** FIX IS HERE: ADD 'is_offline' BEFORE SORTING ***
        for b in active_beds_list:
            b['age'] = int(now - b['last'])
            b['is_offline'] = b['age'] > 10
            
        sorted_beds = sorted(active_beds_list, key=lambda x: x['id'])
        critical_count = len([b for b in sorted_beds if b['news'] >= 7 or b.get('status') == "CRITICAL"])

        # 3. RENDER METRICS
        with metrics_placeholder.container():
            c1, c2, c3 = st.columns(3)
            c1.metric("Connected Beds", len(sorted_beds))
            c2.metric("Critical Patients", critical_count)
            c3.metric("DB Status", "LOGGING 🟢")
            st.divider()

        # 4. RENDER GRID
        with grid_placeholder.container():
            if len(sorted_beds) == 0:
                st.info("Waiting for data... Ensure simulation is running.")
            
            cols = st.columns(4)
            for i, b in enumerate(sorted_beds):
                with cols[i % 4]:
                    # Safer check for is_offline using .get() just in case
                    is_offline = b.get('is_offline', False)
                    border_color = b['color'] if not is_offline else "#444"
                    opacity = "1.0" if not is_offline else "0.5"
                    fluid = int(b.get('fluid', 0))
                    
                    st.markdown(f"""
    <div style="border: 2px solid {border_color}; border-radius: 10px; padding: 10px; background-color: #1e1e1e; opacity: {opacity}; margin-bottom: 10px; color: #ffffff;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <h4 style="margin:0; color:white;">{b['id']}</h4>
            <span style="background:{b['color']}; color:black; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:0.8em;">{b['label']}</span>
        </div>
        <hr style="margin: 5px 0; border-color: #333;">
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 5px; font-size: 0.9em;">
            <div>❤️ <b>HR:</b> {b.get('hr')}</div>
            <div>💓 <b>Pulse:</b> {b.get('pulse')}</div>
            <div>🫁 <b>RR:</b> {b.get('rr')}</div>
            <div>💨 <b>SpO2:</b> {b.get('spo2')}%</div>
            <div>🩸 <b>BP:</b> {b.get('bp')}</div>
            <div>🌡️ <b>Temp:</b> {b.get('temp')}°C</div>
        </div>
        <div style="margin-top:10px; font-size:0.9em; display:flex; justify-content:space-between; align-items:center;">
                <span>NEWS Score: <b>{b['news']}</b></span>
                <span style="color:#00bcd4;">💧 Saline: <b>{fluid}%</b></span>
        </div>
        <div style="margin-top:5px; font-size:0.7em; color:#ccc; text-align:right;">
            🕒 Updated: {b.get('age', 0)}s ago
        </div>
    </div>
    """, unsafe_allow_html=True)
                    st.progress(fluid/100)

        time.sleep(1)