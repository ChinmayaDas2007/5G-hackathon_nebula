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
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "Nebula_Dash_Viewer_Final_v2")
        client.on_message = on_message
        client.connect("broker.hivemq.com", 1883, 60)
        client.subscribe("nebula/ward1/bed/#")
        client.loop_start()
        return client
    except:
        return None

client = start_mqtt()

# -------------------------------------------------
# SESSION STATE
# -------------------------------------------------
if "data" not in st.session_state:
    st.session_state.data = {}

# --- PLACEHOLDERS (CRITICAL FIX) ---
# We create these OUTSIDE the loop so they stay fixed
main_placeholder = st.empty()
sidebar_placeholder = st.sidebar.empty()

# -------------------------------------------------
# MAIN INFINITE LOOP
# -------------------------------------------------
while True:
    # 1. DRAIN THE MAILBOX (Update Data)
    while not mailbox.empty():
        try:
            payload = json.loads(mailbox.get())
            bed_id = payload["id"]
            
            # PARSE BP STRING IMMEDIATELY
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

    # 2. RENDER SIDEBAR (Using the Fixed Placeholder)
    with sidebar_placeholder.container():
        st.title("🚨 CRITICAL PATIENTS")
        
        # Filter for Critical or High Risk (Red)
        critical_beds = []
        for bid, info in st.session_state.data.items():
            # Check Status
            if info.get("status") == "CRITICAL":
                critical_beds.append((bid, info))
                continue
            
            # Check NEWS Score (Red Risk)
            news = calculate_news(
                info.get("hr", 0), info.get("spo2", 98), 
                info.get("sys_bp", 120), info.get("temp", 37.0)
            )
            if get_risk_level(news)[0] == "RED":
                critical_beds.append((bid, info))

        if not critical_beds:
            st.success("All Patients Stable")
        else:
            for bed_id, info in critical_beds:
                hr = info.get("hr", 0)
                spo2 = info.get("spo2", 98)
                st.markdown(f"""
                <div style="border:2px solid red; background:#330000; padding:10px; border-radius:8px; margin-bottom:8px;">
                    <strong>{bed_id}</strong><br>
                    ❤️ HR: {hr} | 💨 SpO₂: {spo2}%<br>
                    <b style="color:red">⚠️ ACTION REQUIRED</b>
                </div>
                """, unsafe_allow_html=True)

    # 3. RENDER MAIN UI (Using the Fixed Placeholder)
    with main_placeholder.container():
        
        # --- CALCULATE STATS ---
        critical_count = len(critical_beds)
        
        high_risk_count = sum(
            1 for b in st.session_state.data.values()
            if get_risk_level(calculate_news(
                b.get("hr", 0), b.get("spo2", 98), b.get("sys_bp", 120), b.get("temp", 37.0)
            ))[0] == "RED"
        )

        # --- TOP METRICS ---
        c1, c2, c3 = st.columns(3)
        c1.metric("Active Nodes", f"{len(st.session_state.data)}/50")
        c2.metric("CRITICAL ALERTS", critical_count)
        c3.metric("HIGH RISK (NEWS)", high_risk_count)
        
        st.markdown("---")

        # --- MAIN BED GRID ---
        cols = st.columns(5)
        sorted_beds = sorted(st.session_state.data.items())

        for i, (bed_id, info) in enumerate(sorted_beds):
            with cols[i % 5]:
                # Safe Data Extraction
                hr = info.get("hr", 0)
                spo2 = info.get("spo2", 98)
                sys_bp = info.get("sys_bp", 120)
                temp = info.get("temp", 37.0)
                fluid = int(info.get("fluid", 0))
                status = info.get("status", "NORMAL")
                
                # Logic
                news_score = calculate_news(hr, spo2, sys_bp, temp)
                risk_color, risk_label = get_risk_level(news_score)

                hr_color = "red" if (hr > 130 or hr < 50) else "#00ff00"
                spo2_color = "red" if spo2 < 90 else "#00ff00"
                badge_color = "red" if status == "CRITICAL" else "#2ecc71"
                
                # Check timestamps
                try:
                    ts = info.get("timestamp", time.time())
                    last_seen = int(time.time() - float(ts))
                except:
                    last_seen = 0

                # Alert Borders
                is_critical = (status == "CRITICAL") or (risk_color == "RED")
                border = "2px solid red" if is_critical else "1px solid #444"
                bg = "#220000" if is_critical else "#0e1117"

                # Render Card
                st.markdown(f"""
                <div style="border:{border}; background-color:{bg}; padding:10px; border-radius:8px; margin-bottom:6px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <strong>{bed_id}</strong>
                        <span style="background:{badge_color}; color:white; padding:2px 6px; border-radius:4px; font-size:12px;">
                            {status}
                        </span>
                    </div>
                    <div style="margin-top:5px; font-size:0.9em;">
                        ❤️ <span style="color:{hr_color}; font-weight:bold;">{hr}</span>
                        💨 <span style="color:{spo2_color}; font-weight:bold;">{spo2}%</span>
                    </div>
                    <div style="font-size:0.8em; color:#aaa;">
                         NEWS: <b style="color:{risk_color};">{risk_label}</b>
                    </div>
                    <div style="font-size:0.7em; color:#666; margin-top:4px;">
                        🕒 {last_seen}s ago
                    </div>
                </div>
                """, unsafe_allow_html=True)

                st.progress(fluid)

    # 4. CONTROL REFRESH RATE
    time.sleep(0.5)