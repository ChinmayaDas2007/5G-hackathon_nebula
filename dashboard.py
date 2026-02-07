import streamlit as st
import paho.mqtt.client as mqtt
import json
import time
import queue

# Importing the ews logic
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
# MQTT CALLBACK
# -------------------------------------------------
def on_message(client, userdata, msg):
    try:
        mailbox.put(msg.payload.decode())
    except:
        pass

# -------------------------------------------------
# MQTT START
# -------------------------------------------------
@st.cache_resource
def start_mqtt():
    try:
        # Use a unique ID to avoid conflict with God Mode
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "Nebula_Dash_Viewer_Main")
        client.on_message = on_message
        client.connect("broker.hivemq.com", 1883, 60)
        client.subscribe("nebula/ward1/bed/#")
        client.loop_start()
        return client
    except Exception as e:
        return None

client = start_mqtt()

# -------------------------------------------------
# SESSION STATE
# -------------------------------------------------
if "data" not in st.session_state:
    st.session_state.data = {}

placeholder = st.empty()

# -------------------------------------------------
# MAIN LOOP (THE FIX IS HERE)
# -------------------------------------------------
while True:
    # 1. PROCESS ALL NEW MESSAGES
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

    # ---------------- BED GRID ----------------
    cols = st.columns(5)
    sorted_beds = sorted(st.session_state.data.items())

        for i, (bed_id, info) in enumerate(sorted_beds):
            with cols[i % 5]:
                # --- PARSE DATA ---
                bp_str = info.get("bp", "120/80")
                try:
                    sys_bp = int(bp_str.split("/")[0])
                    dia_bp = int(bp_str.split("/")[1])
                except:
                    sys_bp, dia_bp = 120, 80

                hr = info.get("hr", 0)
                spo2 = info.get("spo2", 98)
                temp = info.get("temp", 37.0)
                fluid = int(info.get("fluid", 50))
                status = info.get("status", "NORMAL")

                # --- CALCULATE NEWS SCORE ---
                news_score = calculate_news(hr, spo2, sys_bp, temp)
                risk_color, risk_label = get_risk_level(news_score)

                # --- DETERMINE COLORS ---
                # Priority: CRITICAL Status > RED Risk > ORANGE Risk
                if status == "CRITICAL" or risk_color == "RED":
                    border_color = "red"
                    bg_color = "#440000" # Deep Red
                    display_status = "CRITICAL"
                elif status == "SEPSIS" or risk_color == "ORANGE":
                    border_color = "orange"
                    bg_color = "#442200" # Deep Orange
                    display_status = "WARNING"
                else:
                    border_color = "#333"
                    bg_color = "#0E1117" # Default Black
                    display_status = "STABLE"

                # --- RENDER CARD ---
                st.markdown(f"""
                <div style="
                    border: 2px solid {border_color}; 
                    background-color: {bg_color};
                    padding: 10px; 
                    border-radius: 8px; 
                    margin-bottom: 10px;">
                    <div style="display:flex; justify-content:space-between;">
                        <strong>{bed_id}</strong>
                        <span style="color:{border_color}; font-weight:bold">{display_status}</span>
                    </div>
                    <hr style="margin: 5px 0; border-color: #555;">
                    <div style="font-size: 0.9rem; line-height: 1.4;">
                        ❤️ <b>HR:</b> {hr} <br>
                        💨 <b>SpO2:</b> {spo2}% <br>
                        🩸 <b>BP:</b> {sys_bp}/{dia_bp} <br>
                        🌡️ <b>Temp:</b> {temp}°C
                    </div>
                    <div style="margin-top:8px; padding:4px; background-color:{risk_color if risk_color != 'GREEN' else '#222'}; color:{'black' if risk_color!='GREEN' else 'white'}; text-align:center; border-radius:4px; font-weight:bold; font-size: 0.8rem;">
                        {risk_label}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Fluid Bar
                bar_color = "red" if fluid < 15 else "#00ff00"
                st.markdown(f"""<style>.stProgress .st-bo {{background-color: {bar_color};}}</style>""", unsafe_allow_html=True)
                st.progress(fluid)

    # 3. SLEEP TO PREVENT CPU MELTDOWN
    time.sleep(0.5)
