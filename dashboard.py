import streamlit as st
import paho.mqtt.client as mqtt
import json
import time
import queue

# --- PAGE CONFIG ---
st.set_page_config(page_title="Project Nebula", layout="wide")
st.title("🏥 PROJECT NEBULA: 5G SMART WARD")

# --- STEP 1: THREAD-SAFE GLOBAL MAILBOX ---
# This creates a "Mailbox" that exists outside the session, safe for threads.
@st.cache_resource
def get_mailbox():
    return queue.Queue()

mailbox = get_mailbox()

# --- STEP 2: MQTT CALLBACK ---
def on_message(client, userdata, msg):
    try:
        mailbox.put(msg.payload.decode())
    except:
        pass

# --- STEP 3: START MQTT ---
@st.cache_resource
def start_mqtt():
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "Nebula_Dash_Viewer")
        client.on_message = on_message
        client.connect("broker.hivemq.com", 1883, 60)
        client.subscribe("nebula/ward1/bed/#")
        client.loop_start()
        return client
    except Exception as e:
        return None

client = start_mqtt()

# --- MAIN DASHBOARD LOOP ---
if 'data' not in st.session_state:
    st.session_state.data = {} 

if client is None:
    st.error("❌ Connection Failed. Check WiFi/Hotspot.")

placeholder = st.empty()

while True:
    # 1. Process Mailbox
    while not mailbox.empty():
        try:
            payload_str = mailbox.get()
            payload = json.loads(payload_str)
            bed_id = payload['id']
            st.session_state.data[bed_id] = payload
        except:
            pass

    # 2. Render Grid
    with placeholder.container():
        # Stats
        critical_count = sum(1 for b in st.session_state.data.values() if b.get('triage') == "RED")
        warning_count = sum(1 for b in st.session_state.data.values() if b.get('triage') == "ORANGE")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Active Nodes", f"{len(st.session_state.data)}/50")
        c2.metric("CRITICAL ALERTS", f"{critical_count}", delta_color="inverse")
        c3.metric("WARNINGS", f"{warning_count}", delta_color="off")
        
        st.markdown("---")

        # The Bed Grid
        cols = st.columns(5)
        sorted_beds = sorted(st.session_state.data.items())
        
        for index, (bed_id, info) in enumerate(sorted_beds):
            with cols[index % 5]:
                # Get Data (Safe Defaults)
                triage = info.get('triage', 'GREEN')
                msg = info.get('msg', 'Stable')
                bp = info.get('bp', '120/80')
                temp = info.get('temp', 37.0)
                spo2 = info.get('spo2', 99)
                hr = info['hr']

                # Dynamic Colors for CSS
                bg_color = "#0E1117" # Default Dark
                border_color = "#333"
                text_color = "#eee"

                if triage == "RED":
                    bg_color = "#440000" # Dark Red Background
                    border_color = "#ff0000"
                    text_color = "#ffcccc"
                elif triage == "ORANGE":
                    bg_color = "#443300" # Dark Orange/Brown
                    border_color = "#ffaa00"
                    text_color = "#ffddaa"

                # HTML Card
                st.markdown(f"""
                <div style="background-color: {bg_color}; border: 1px solid {border_color}; padding: 10px; border-radius: 8px; margin-bottom: 10px;">
                    <strong style="color: white; font-size: 1.1em;">{bed_id}</strong>
                    <div style="float: right; font-size: 0.8em; color: {border_color}; font-weight: bold;">{msg}</div>
                    <hr style="margin: 5px 0; border-color: #444;">
                    <div style="color: {text_color}; font-size: 0.9em;">
                        ❤️ <b>{hr}</b> <span style="font-size:0.8em">bpm</span> &nbsp;|&nbsp; 🩸 <b>{bp}</b>
                    </div>
                    <div style="color: {text_color}; font-size: 0.9em;">
                        🌡️ <b>{temp}°C</b> &nbsp;|&nbsp; 💨 <b>{spo2}%</b>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Fluid Bar (Saline)
                st.progress(int(info['fluid']))
                    
    time.sleep(0.5)