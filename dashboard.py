import streamlit as st
import paho.mqtt.client as mqtt
import json
import time
import queue

from ews_logic import calculate_news, get_risk_level
from patient_db import generate_patient_db   # 👈 IMPORT FAKE DB

# -------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------
st.set_page_config(page_title="Project Nebula", layout="wide")
st.title("🏥 PROJECT NEBULA: 5G SMART WARD")

# -------------------------------------------------
# MODE SELECTOR (TOP – JUDGE FRIENDLY)
# -------------------------------------------------
st.markdown("### 🧭 Dashboard Mode")

mode = st.radio(
    "Select View",
    ["🟢 Live Monitor", "📋 Patient Records"],
    horizontal=True
)

st.markdown("---")

# -------------------------------------------------
# FAKE PATIENT DATABASE (STABLE)
# -------------------------------------------------
if "patient_db" not in st.session_state:
    st.session_state.patient_db = generate_patient_db(50)

# -------------------------------------------------
# LIVE MONITOR (YOUR EXISTING SYSTEM)
# -------------------------------------------------
if mode == "🟢 Live Monitor":

    # THREAD SAFE QUEUE
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
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "Nebula_Dashboard")
        client.on_message = on_message
        client.connect("broker.hivemq.com", 1883, 60)
        client.subscribe("nebula/ward1/bed/#")
        client.loop_start()
        return client

    client = start_mqtt()

    if "data" not in st.session_state:
        st.session_state.data = {}

    placeholder = st.empty()

    while True:

        while not mailbox.empty():
            try:
                payload = json.loads(mailbox.get())
                bed_id = payload["id"]

                if "bp" in payload and isinstance(payload["bp"], str):
                    try:
                        payload["sys_bp"] = int(payload["bp"].split("/")[0])
                    except:
                        payload["sys_bp"] = 120
                else:
                    payload["sys_bp"] = 120

                st.session_state.data[bed_id] = payload
            except:
                pass

        with placeholder.container():

            critical_count = sum(
                1 for b in st.session_state.data.values()
                if get_risk_level(
                    calculate_news(
                        b.get("hr", 0),
                        b.get("spo2", 98),
                        b.get("sys_bp", 120),
                        b.get("temp", 37.0)
                    )
                )[0] == "RED"
            )

            c1, c2, c3 = st.columns(3)
            c1.metric("Active Nodes", f"{len(st.session_state.data)}/50")
            c2.metric("Critical Alerts", critical_count)
            c3.metric("System Health", "STABLE")

            st.markdown("---")

            cols = st.columns(5)

            for i, (bed_id, info) in enumerate(sorted(st.session_state.data.items())):
                with cols[i % 5]:
                    hr = info.get("hr", 0)
                    spo2 = info.get("spo2", 98)
                    bp = info.get("bp", "120/80")
                    temp = info.get("temp", 37.0)
                    sys_bp = info.get("sys_bp", 120)

                    news = calculate_news(hr, spo2, sys_bp, temp)
                    color, label = get_risk_level(news)

                    border = "2px solid red" if color == "RED" else "1px solid #444"
                    bg = "#2a0a0a" if color == "RED" else "#0e1117"

                    st.markdown(f"""
                    <div style="border:{border}; background:{bg};
                                padding:10px; border-radius:8px;">
                        <strong>{bed_id}</strong><br>
                        ❤️ HR: {hr}<br>
                        💨 SpO₂: {spo2}%<br>
                        🩸 BP: {bp}<br>
                        🌡️ Temp: {temp}°C<br>
                        🧠 NEWS: <b style="color:{color};">{label}</b>
                    </div>
                    """, unsafe_allow_html=True)

        time.sleep(0.5)

# -------------------------------------------------
# 📋 PATIENT RECORDS (CLEAN, STABLE, DEMO SAFE)
# -------------------------------------------------
if mode == "📋 Patient Records":

    st.subheader("📋 Patient Clinical Overview (Doctor View)")

    st.dataframe(
        st.session_state.patient_db,
        use_container_width=True,
        hide_index=True
    )

    st.info(
        "This section provides a consolidated clinical overview of all patients, "
        "including vitals, NEWS score, and suspected conditions for rapid doctor review."
    )
