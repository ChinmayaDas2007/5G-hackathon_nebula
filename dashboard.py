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
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "Nebula_Dash_v3")
        client.on_message = on_message
        client.connect("broker.hivemq.com", 1883, 60)
        client.subscribe("nebula/ward1/bed/#")
        client.loop_start()
        return client
    except: return None
client = start_mqtt()

if mode == "📋 Patient Records":
    st.subheader("📋 Patient Clinical Overview")
    records = st.session_state.patient_db.to_dict("records")
    cols = st.columns(4)
    for i, p in enumerate(records):
        with cols[i % 4]:
            color = "#e74c3c" if "CRITICAL" in p['Status'] else "#2ecc71"
            # ADDED: color: white
            st.markdown(f"""
            <div style="border:2px solid {color}; background:#0e1117; padding:15px; border-radius:10px; margin-bottom:15px; color:white;">
                <h4>{p['Bed ID']}</h4>
                ⚡ <b>HR:</b> {p['HR (Electrical)']} <br>
                💓 <b>Pulse:</b> {p['Pulse (Mech)']} <br>
                🫁 <b>RR:</b> {p['Resp. Rate']} <br>
                💨 <b>SpO₂:</b> {p['SpO₂ (%)']}%<br>
                🩸 <b>BP:</b> {p['Blood Pressure']}<br>
                <hr style="border-color:#333;">
                <b>NEWS: {p['NEWS Score']}</b> ({p['Status']})
            </div>
            """, unsafe_allow_html=True)

elif mode == "🟢 Live Monitor":
    sidebar_area = st.sidebar.empty()
    grid_area = st.empty()

    while True:
        now = time.time()
        while not mailbox.empty():
            try:
                data = json.loads(mailbox.get_nowait())
                bid = data['id']
                sys_bp = int(data['bp'].split('/')[0]) if 'bp' in data else 120
                rr = int(data.get('rr', 16))
                pulse = int(data.get('pulse', data.get('hr', 70))) # Fallback if missing
                
                # UPDATED: Pass PULSE to calculator
                score = calculate_news(data['hr'], pulse, data['spo2'], sys_bp, data['temp'], rr)
                color, label = get_risk_level(score)
                
                st.session_state.beds[bid] = {
                    **data, "news": score, "color": color, "label": label, "last": now, "pulse": pulse
                }
            except: continue

        st.session_state.beds = {k:v for k,v in st.session_state.beds.items() if now - v.get('last',0) < 15}
        sorted_beds = sorted(st.session_state.beds.values(), key=lambda x: x['id'])
        critical = [b for b in sorted_beds if b['news'] >= 7 or b.get('status') == "CRITICAL"]

        with sidebar_area.container():
            st.error(f"Critical: {len(critical)}")
            for b in critical:
                st.markdown(f"<div style='border:1px solid red; background:#400; padding:10px; color:white;'><b>{b['id']}</b> NEWS:{b['news']}</div>", unsafe_allow_html=True)

        with grid_area.container():
            cols = st.columns(4)
            for i, b in enumerate(sorted_beds):
                with cols[i % 4]:
                    border = "2px solid red" if b['news'] >= 7 else "1px solid #444"
                    bg = "#2b0000" if b['news'] >= 7 else "#0e1117"
                    fluid = int(b.get('fluid', 0))
                    
                    # ADDED: Color: White to main div
                    st.markdown(f"""
                    <div style="border:{border}; background:{bg}; padding:15px; border-radius:10px; margin-bottom:10px; color:white;">
                        <div style="display:flex; justify-content:space-between;">
                            <h4>{b['id']}</h4>
                            <b style="color:{b['color']}">{b['label']}</b>
                        </div>
                        <hr style="opacity:0.2;">
                        ♥️ <b>HR: {b['hr']}</b> <br>
                        💓 <b>Pulse: {b.get('pulse','--')}</b> <br>
                        🫁 <b>RR: {b.get('rr','--')}</b> <br>
                        💨 <b>SpO2:</b> {b['spo2']}% | 🩸 <b>BP:</b> {b.get('bp','--')}<br>
                        <br>
                        💧 Saline: {fluid}%
                        <div style="width:100%; background:#333; height:5px; margin-top:5px;">
                            <div style="width:{fluid}%; background:#00bcd4; height:5px;"></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        time.sleep(1)
        st.rerun()