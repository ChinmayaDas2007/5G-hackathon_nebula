import streamlit as st
import paho.mqtt.client as mqtt
import json
import time
import queue
from ews_logic import calculate_news, get_risk_level
from patient_db import generate_patient_db

# -------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------
st.set_page_config(page_title="Project Nebula", layout="wide")
st.title("🏥 PROJECT NEBULA: 5G SMART WARD")

# -------------------------------------------------
# MODE SELECTOR
# -------------------------------------------------
st.markdown("### 🧭 Dashboard Mode")
mode = st.radio(
    "Select View",
    ["🟢 Live Monitor", "📋 Patient Records"],
    horizontal=True
)
st.markdown("---")

# -------------------------------------------------
# SESSION STATE INITIALIZATION
# -------------------------------------------------
if "beds" not in st.session_state:
    st.session_state.beds = {}

if "patient_db" not in st.session_state:
    st.session_state.patient_db = generate_patient_db(50)

# -------------------------------------------------
# MQTT SETUP (Shared)
# -------------------------------------------------
@st.cache_resource
def get_mailbox():
    return queue.Queue()

mailbox = get_mailbox()

def on_message(client, userdata, msg):
    try:
        mailbox.put(msg.payload.decode())
    except:
        pass

@st.cache_resource
def start_mqtt():
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "Nebula_Final_Integrated")
        client.on_message = on_message
        client.connect("broker.hivemq.com", 1883, 60)
        client.subscribe("nebula/ward1/bed/#")
        client.loop_start()
        return client
    except:
        return None

client = start_mqtt()

# =================================================
# 📋 PATIENT RECORDS (Doctor View)
# =================================================
if mode == "📋 Patient Records":
    st.subheader("📋 Patient Clinical Overview (Doctor View)")
    st.caption("All patients summarized for rapid clinical decision-making")

    records = st.session_state.patient_db.to_dict("records")
    cols = st.columns(4)

    for i, p in enumerate(records):
        with cols[i % 4]:
            status_color = {
                "STABLE": "#2ecc71",
                "MONITOR": "#f1c40f",
                "CRITICAL": "#e74c3c"
            }.get(p["Status"], "#999")

            st.markdown(
                f"""
                <div style="
                    border:2px solid {status_color};
                    background:#0e1117;
                    padding:18px;
                    border-radius:14px;
                    min-height:300px;
                    margin-bottom:20px;
                ">
                    <h3 style="margin-bottom:10px;">{p['Bed ID']}</h3>
                    ❤️ <b>HR:</b> {p['Heart Rate (bpm)']} bpm<br>
                    💨 <b>SpO₂:</b> {p['SpO₂ (%)']}%<br>
                    🩸 <b>BP:</b> {p['Blood Pressure']}<br>
                    🌡️ <b>Temp:</b> {p['Temperature (°C)']} °C<br>
                    <hr style="border:0.5px solid #333; margin:10px 0;">
                    🧠 <b>NEWS:</b> {p['NEWS Score']}
                    <span style="color:{status_color}; font-weight:bold;">
                        ({p['Status']})
                    </span>
                    <hr style="border:0.5px solid #333; margin:10px 0;">
                    📝 <b>Clinical Note:</b><br>
                    <i>{p['Clinical Notes']}</i>
                </div>
                """,
                unsafe_allow_html=True
            )

# =================================================
# 🟢 LIVE MONITOR (Live Triage)
# =================================================
elif mode == "🟢 Live Monitor":
    # UI Placeholders for the loop
    sidebar_area = st.sidebar.empty()
    metrics_area = st.empty()
    grid_area = st.empty()

    while True:
        now = time.time()

        # 1. Drain Mailbox and update State
        while not mailbox.empty():
            try:
                raw_msg = mailbox.get_nowait()
                data = json.loads(raw_msg)
                b_id = data['id']
                
                # Parse Systolic BP
                sys_bp = int(data['bp'].split('/')[0]) if 'bp' in data else 120
                n_score = calculate_news(data['hr'], data['spo2'], sys_bp, data['temp'])
                r_color, r_label = get_risk_level(n_score)
                
                # Update Dictionary (Key-based to prevent duplicates)
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

        # 2. Cleanup Stale Data (Timeout after 8s)
        st.session_state.beds = {
            k: v for k, v in st.session_state.beds.items() 
            if now - v.get('last_seen', 0) < 8
        }

        # 3. Data Prep
        all_active = list(st.session_state.beds.values())
        
        # FIX: Changed sorting to use Bed ID instead of criticality
        sorted_beds = sorted(all_active, key=lambda x: x['id']) 
        
        critical_beds = [b for b in all_active if b['is_critical']]

        # 4. Render Sidebar
        with sidebar_area.container():
            st.header("🚨 Live Critical Alerts")
            st.error(f"Total Critical: {len(critical_beds)}")
            for bed in critical_beds:
                st.markdown(f"""
                <div style="border:1px solid red; padding:10px; border-radius:5px; background:#2b0000; margin-bottom:5px;">
                    <b>{bed['id']}</b> | NEWS: {bed['news_score']}<br>
                    ❤️ HR: {bed['hr']} | 💨 SpO2: {bed['spo2']}% | 🩸 BP: {bed.get('bp', 'N/A')}
                </div>
                """, unsafe_allow_html=True)
            if not critical_beds:
                st.success("No Critical Patients")

        # 5. Render Metrics
        with metrics_area.container():
            c1, c2, c3 = st.columns(3)
            c1.metric("Active Beds", len(all_active))
            c2.metric("Critical Alerts", len(critical_beds))
            c3.metric("System Health", "STABLE")
            st.divider()

        # 6. Render Grid
        with grid_area.container():
            cols = st.columns(4)
            for i, bed in enumerate(sorted_beds):
                with cols[i % 4]:
                    bg = "#2b0000" if bed['is_critical'] else "#0e1117"
                    border = "2px solid red" if bed['is_critical'] else "1px solid #444"
                    
                    st.markdown(f"""
                    <div style="border:{border}; background:{bg}; padding:15px; border-radius:10px; margin-bottom:10px; min-height:220px;">
                        <h4 style="margin:0;">{bed['id']}</h4>
                        <p style="color:{bed['risk_color']}; margin:5px 0;">{bed['risk_label']} (Score: {bed['news_score']})</p>
                        <hr style="opacity:0.1; margin:5px 0;">
                        ❤️ HR: {bed['hr']}<br>
                        💨 SpO2: {bed['spo2']}%<br>
                        🩸 BP: {bed.get('bp', 'N/A')}<br>
                        🌡️ Temp: {bed['temp']}°C
                    </div>
                    """, unsafe_allow_html=True)

        time.sleep(1)
        st.rerun()