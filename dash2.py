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
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "Nebula_Dashboard")
    client.on_message = on_message
    client.connect("broker.hivemq.com", 1883, 60)
    client.subscribe("nebula/ward1/bed/#")
    client.loop_start()
    return client

client = start_mqtt()

# -------------------------------------------------
# SESSION STATE & PLACEHOLDERS
# -------------------------------------------------
if "data" not in st.session_state:
    st.session_state.data = {}

main_placeholder = st.empty()
sidebar_placeholder = st.sidebar.empty()

# -------------------------------------------------
# MAIN LOOP (AS YOU WANT)
# -------------------------------------------------
while True:

    # ---------------- DRAIN MQTT MAILBOX ----------------
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

    # ---------------- SIDEBAR: CRITICAL PATIENTS ----------------
    with sidebar_placeholder.container():
        st.header("🚨 Live Critical Alerts")

        # 🔥 Dict = no duplicates
        critical_beds = {}

        for bid, info in st.session_state.data.items():
            hr = info.get("hr", 0)
            spo2 = info.get("spo2", 98)
            sys_bp = info.get("sys_bp", 120)
            temp = info.get("temp", 37.0)

            news = calculate_news(hr, spo2, sys_bp, temp)
            risk_color, _ = get_risk_level(news)

            if info.get("status") == "CRITICAL" or risk_color == "RED":
                critical_beds[bid] = info

        if not critical_beds:
            st.success("All Patients Stable")
        else:
            st.markdown(f"**Total Critical: {len(critical_beds)}**")
            for bed_id, info in critical_beds.items():
                st.markdown(f"""
                <div style="border:2px solid red; background:#330000;
                            padding:10px; border-radius:8px; margin-bottom:8px;">
                    <strong>{bed_id}</strong><br>
                    ❤️ HR: {info.get("hr", 0)}<br>
                    💨 SpO₂: {info.get("spo2", 98)}%<br>
                    ⚠️ CRITICAL
                </div>
                """, unsafe_allow_html=True)

    # ---------------- MAIN DASHBOARD ----------------
    with main_placeholder.container():

        # ✅ FIXED COUNT (fresh calculation, SAME logic)
        critical_count = sum(
            1 for info in st.session_state.data.values()
            if (
                info.get("status") == "CRITICAL" or
                get_risk_level(
                    calculate_news(
                        info.get("hr", 0),
                        info.get("spo2", 98),
                        info.get("sys_bp", 120),
                        info.get("temp", 37.0)
                    )
                )[0] == "RED"
            )
        )

        high_risk_count = sum(
            1 for info in st.session_state.data.values()
            if get_risk_level(
                calculate_news(
                    info.get("hr", 0),
                    info.get("spo2", 98),
                    info.get("sys_bp", 120),
                    info.get("temp", 37.0)
                )
            )[0] == "RED"
        )

        c1, c2, c3 = st.columns(3)
        c1.metric("Active Nodes", f"{len(st.session_state.data)}/50")
        c2.metric("Critical Alerts", critical_count)
        c3.metric("High Risk (NEWS)", high_risk_count)

        st.markdown("---")

        cols = st.columns(5)
        sorted_beds = sorted(st.session_state.data.items())

        for i, (bed_id, info) in enumerate(sorted_beds):
            with cols[i % 5]:

                hr = info.get("hr", 0)
                spo2 = info.get("spo2", 98)
                sys_bp = info.get("sys_bp", 120)
                temp = info.get("temp", 37.0)
                bp = info.get("bp", "120/80")
                fluid = int(info.get("fluid", 0))
                status = info.get("status", "NORMAL")

                news_score = calculate_news(hr, spo2, sys_bp, temp)
                risk_color, risk_label = get_risk_level(news_score)

                hr_color = "red" if hr > 130 or hr < 50 else "lime"
                spo2_color = "red" if spo2 < 90 else "lime"

                ts = info.get("timestamp", time.time())
                last_seen = int(time.time() - float(ts))

                is_critical = (status == "CRITICAL") or (risk_color == "RED")
                border = "2px solid red" if is_critical else "1px solid #444"
                bg = "#2a0a0a" if is_critical else "#0e1117"

                st.markdown(f"""
                <div style="border:{border}; background:{bg};
                            padding:10px; border-radius:8px; margin-bottom:6px;">
                    <strong>{bed_id}</strong><br>
                    ❤️ HR: <span style="color:{hr_color};">{hr}</span><br>
                    💨 SpO₂: <span style="color:{spo2_color};">{spo2}%</span><br>
                    🩸 BP: {bp}<br>
                    🌡️ Temp: {temp}°C<br>
                    🧠 NEWS: <b style="color:{risk_color};">{risk_label}</b><br>
                    🕒 {last_seen}s ago
                </div>
                """, unsafe_allow_html=True)

                st.progress(fluid)

    time.sleep(0.5)
