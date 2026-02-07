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
# THREAD-SAFE MAILBOX (MQTT → STREAMLIT)
# -------------------------------------------------
@st.cache_resource
def get_mailbox():
    return queue.Queue()

mailbox = get_mailbox()

# -------------------------------------------------
# MQTT CALLBACK
# -------------------------------------------------
def on_message(client, userdata, msg):
    try:
        mailbox.put(msg.payload.decode())
    except:
        pass

# -------------------------------------------------
# MQTT START (RUNS ONLY ONCE)
# -------------------------------------------------
@st.cache_resource
def start_mqtt():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "Nebula_Dashboard")
    client.on_message = on_message
    client.connect("broker.hivemq.com", 1883, 60)
    client.subscribe("nebula/ward1/bed/#")
    client.loop_start()
    return client

client = start_mqtt()

# -------------------------------------------------
# SESSION STATE
# -------------------------------------------------
if "data" not in st.session_state:
    st.session_state.data = {}

placeholder = st.empty()

# -------------------------------------------------
# PROCESS MQTT MESSAGES
# -------------------------------------------------
while not mailbox.empty():
    try:
        payload = json.loads(mailbox.get())
        bed_id = payload["id"]
        st.session_state.data[bed_id] = payload
    except:
        pass

# -------------------------------------------------
# DASHBOARD UI
# -------------------------------------------------
with placeholder.container():

    # ---------------- STATS ----------------
    critical_count = sum(
        1 for b in st.session_state.data.values()
        if b.get("status") == "CRITICAL"
    )

    high_risk_count = sum(
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
    c2.metric("CRITICAL ALERTS", critical_count)
    c3.metric("HIGH RISK (NEWS)", high_risk_count)

    st.markdown("---")
    
    # ---------------- SIDEBAR: CRITICAL ALERTS ----------------
    st.sidebar.title("🚨 CRITICAL PATIENTS")

    critical_beds = {
        bid: info for bid, info in st.session_state.data.items()
        if info.get("status") == "CRITICAL"
    }

    if not critical_beds:
        st.sidebar.success("No critical patients")
    else:
        for bed_id, info in critical_beds.items():
            hr = info.get("hr", 0)
            spo2 = info.get("spo2", 98)

            st.sidebar.markdown(f"""
            <div style="
                border:2px solid red;
                background:#330000;
                padding:10px;
                border-radius:8px;
                margin-bottom:8px;
            ">
                <strong>{bed_id}</strong><br>
                ❤️ HR: {hr} bpm<br>
                💨 SpO₂: {spo2}%<br>
                ⚠️ CRITICAL
            </div>
            """, unsafe_allow_html=True)
    
   

    # ---------------- BED GRID ----------------
    cols = st.columns(5)
    sorted_beds = sorted(st.session_state.data.items())

    for i, (bed_id, info) in enumerate(sorted_beds):
        with cols[i % 5]:

            # ---- SAFE DATA ----
            hr = info.get("hr", 0)
            spo2 = info.get("spo2", 98)
            sys_bp = info.get("sys_bp", 120)
            temp = info.get("temp", 37.0)
            fluid = int(info.get("fluid", 0))

            # ---- NEWS SCORE ----
            news_score = calculate_news(hr, spo2, sys_bp, temp)
            risk_color, risk_label = get_risk_level(news_score)

            # ---- ALERT LOGIC ----
            is_critical = (info.get("status") == "CRITICAL") or (risk_color == "RED")
            border = "2px solid red" if is_critical else "1px solid #444"

            # ---- BED CARD ----
            st.markdown(f"""
            <div style="border:{border}; padding:8px; border-radius:6px; margin-bottom:6px;">
                <strong>{bed_id}</strong><br>
                ❤️ HR: {hr} bpm<br>
                💨 SpO₂: {spo2}%<br>
                🧠 NEWS: <b style="color:{risk_color};">{risk_label}</b>
            </div>
            """, unsafe_allow_html=True)

            st.progress(fluid)

# -------------------------------------------------
# CONTROLLED REFRESH (STREAMLIT-SAFE)
# -------------------------------------------------
time.sleep(0.5)
