import streamlit as st
import paho.mqtt.client as mqtt
import json
import time
import queue
from ews_logic import calculate_news, get_risk_level
from patient_db import generate_patient_db

st.set_page_config(page_title="Project Nebula", layout="wide")
st.title("🏥 PROJECT NEBULA: 5G SMART WARD")

st.markdown("### 🧭 Dashboard Mode")
mode = st.radio("Select View", ["🟢 Live Monitor", "📋 Patient Records"], horizontal=True)
st.markdown("---")

if "beds" not in st.session_state: st.session_state.beds = {}
if "patient_db" not in st.session_state: st.session_state.patient_db = generate_patient_db(50)

@st.cache_resource
def get_mailbox(): return queue.Queue()
mailbox = get_mailbox()

def on_message(client, userdata, msg):
    try: mailbox.put(msg.payload.decode())
    except: pass

@st.cache_resource
def start_mqtt():
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "Nebula_Dash_Ultimate")
        client.on_message = on_message
        client.connect("broker.hivemq.com", 1883, 60)
        client.subscribe("nebula/ward1/bed/#")
        client.loop_start()
        return client
    except: return None
client = start_mqtt()

# --- MODE 1: DOCTOR VIEW ---
if mode == "📋 Patient Records":
    st.subheader("📋 Patient Clinical Overview")
    records = st.session_state.patient_db.to_dict("records")
    cols = st.columns(4)
    for i, p in enumerate(records):
        with cols[i % 4]:
            color = "#e74c3c" if "CRITICAL" in p['Status'] else "#2ecc71"
            st.markdown(f"""
            <div style="border:2px solid {color}; background:#0e1117; padding:15px; border-radius:10px; margin-bottom:15px; color:white;">
                <h4>{p['Bed ID']}</h4>
                ⚡ <b>HR:</b> {p['HR (Electrical)']} <br>
                💓 <b>Pulse:</b> {p['Pulse (Mech)']} <br>
                🫁 <b>RR:</b> {p['Resp. Rate']} <br>
                💨 <b>SpO₂:</b> {p['SpO₂ (%)']}%<br>
                🩸 <b>BP:</b> {p['Blood Pressure']}<br>
                🌡️ <b>Temp:</b> {p['Temperature (°C)']}°C<br>
                <hr style="border-color:#333;">
                <b>NEWS: {p['NEWS Score']}</b> ({p['Status']})
            </div>
            """, unsafe_allow_html=True)

# --- MODE 2: LIVE MONITOR ---
elif mode == "🟢 Live Monitor":
    # 1. Create Placeholders ONCE
    sidebar_placeholder = st.sidebar.empty()
    metrics_placeholder = st.empty()
    grid_placeholder = st.empty()

    # 2. Infinite Loop (NO st.rerun)
    # This prevents the page from "dimming" or flashing
    while True:
        now = time.time()
        
        # A. Process Incoming Data
        while not mailbox.empty():
            try:
                data = json.loads(mailbox.get_nowait())
                bid = data['id']
                sys_bp = int(data['bp'].split('/')[0]) if 'bp' in data else 120
                rr = int(data.get('rr', 16))
                pulse = int(data.get('pulse', data.get('hr', 70)))
                
                score = calculate_news(data['hr'], pulse, data['spo2'], sys_bp, data['temp'], rr)
                color, label = get_risk_level(score)
                
                st.session_state.beds[bid] = {
                    **data, "news": score, "color": color, "label": label, "last": now, "pulse": pulse
                }
            except: continue

        # B. Clean & Sort
        # Mark beds as "OFFLINE" if no data for 10s, Delete if > 60s
        current_beds = []
        to_delete = []
        for bid, b in st.session_state.beds.items():
            age = now - b.get('last', 0)
            if age > 60: to_delete.append(bid)
            else:
                b['is_offline'] = (age > 10)
                b['age'] = int(age)
                current_beds.append(b)
        
        for k in to_delete: del st.session_state.beds[k]
        
        sorted_beds = sorted(current_beds, key=lambda x: x['id'])
        critical = [b for b in sorted_beds if not b.get('is_offline') and (b['news'] >= 7 or b.get('status') == "CRITICAL")]

        # C. Render Sidebar
        with sidebar_placeholder.container():
            st.header("🚨 Alerts")
            st.error(f"Critical: {len(critical)}")
            for b in critical:
                st.markdown(f"""
                <div style='border:1px solid red; background:#400; padding:10px; color:white; margin-bottom:5px; border-radius:5px;'>
                    <b>{b['id']}</b> NEWS:{b['news']}<br>
                    ❤️ {b['hr']} | 🫁 {b.get('rr','--')} | 💨 {b['spo2']}%
                </div>""", unsafe_allow_html=True)

        # D. Render Metrics
        with metrics_placeholder.container():
            c1, c2, c3 = st.columns(3)
            c1.metric("Active Beds", len(sorted_beds))
            c2.metric("Critical Alerts", len(critical))
            c3.metric("System Health", "ONLINE")
            st.divider()

        # E. Render Grid
        with grid_placeholder.container():
            cols = st.columns(4)
            for i, b in enumerate(sorted_beds):
                with cols[i % 4]:
                    # OFFLINE STATE
                    if b.get('is_offline'):
                        st.markdown(f"""
                        <div style="border:1px dashed #444; background:#1e1e1e; padding:15px; border-radius:10px; margin-bottom:10px; opacity:0.6;">
                            <h4 style="color:#888;">{b['id']}</h4>
                            <h3 style="color:#aaa;">📶 OFFLINE</h3>
                            <p style="color:#666; font-size:0.8em;">Last seen {b['age']}s ago</p>
                        </div>""", unsafe_allow_html=True)
                        continue

                    # NORMAL STATE
                    border = "2px solid red" if b['news'] >= 7 else "1px solid #444"
                    bg = "#2b0000" if b['news'] >= 7 else "#0e1117"
                    fluid = int(b.get('fluid', 0))
                    
                    # Error Handling for Sensors (-1 values)
                    def fmt(val, unit):
                        return f"{val} <span style='color:#aaa; font-size:0.8em'>{unit}</span>" if val != -1 else "<span style='color:yellow'>⚠️ ERR</span>"

                    st.markdown(f"""
                    <div style="border:{border}; background:{bg}; padding:15px; border-radius:10px; margin-bottom:10px; color:white;">
                        <div style="display:flex; justify-content:space-between;">
                            <h4>{b['id']}</h4>
                            <b style="color:{b['color']}">{b['label']}</b>
                        </div>
                        <hr style="opacity:0.2; margin:8px 0;">
                        ⚡ <b>HR:</b> {fmt(b['hr'], 'bpm')} <br>
                        💓 <b>Pulse:</b> {fmt(b.get('pulse', -1), 'bpm')} <br>
                        🫁 <b>RR:</b> {fmt(b.get('rr', -1), '/min')} <br>
                        💨 <b>SpO2:</b> {fmt(b['spo2'], '%')} <br>
                        🩸 <b>BP:</b> {b.get('bp','--')} <br>
                        🌡️ <b>Temp:</b> {b['temp']}°C <br>
                        <br>
                        💧 Saline: {fluid}%
                        <div style="width:100%; background:#333; height:5px; margin-top:5px; border-radius:2px;">
                            <div style="width:{fluid}%; background:#00bcd4; height:5px; border-radius:2px;"></div>
                        </div>
                        <div style="margin-top:8px; font-size:0.7em; color:#666; text-align:right;">
                            🕒 Updated: {b['age']}s ago
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        # 3. Sleep (Control Refresh Rate)
        time.sleep(1)