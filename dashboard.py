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

# --- STEP 2: MQTT CALLBACK (The Listener) ---
def on_message(client, userdata, msg):
    # We only touch the global mailbox here. NOT st.session_state.
    try:
        mailbox.put(msg.payload.decode())
    except:
        pass

# --- STEP 3: START MQTT (Only Once) ---
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
if client is None:
    st.error("❌ Connection Failed. Check WiFi/Hotspot.")

# --- STEP 4: MAIN DASHBOARD LOOP ---
if 'data' not in st.session_state:
    st.session_state.data = {} 

placeholder = st.empty()

while True:
    # Process all messages in the mailbox
    while not mailbox.empty():
        try:
            payload_str = mailbox.get()
            payload = json.loads(payload_str)
            bed_id = payload['id']
            st.session_state.data[bed_id] = payload
        except:
            pass

    # Render the Grid
    with placeholder.container():
        # Stats
        critical_count = sum(1 for b in st.session_state.data.values() if b['status'] == "CRITICAL")
        
        c1, c2 = st.columns(2)
        c1.metric("Active Nodes", f"{len(st.session_state.data)}/50")
        c2.metric("CRITICAL ALERTS", f"{critical_count}")
        st.markdown("---")

        # The Bed Grid
        cols = st.columns(5)
        sorted_beds = sorted(st.session_state.data.items())
        
        for index, (bed_id, info) in enumerate(sorted_beds):
                    with cols[index % 5]:
                        # Dynamic Border Color
                        border = "2px solid red" if info['status'] == "CRITICAL" else "1px solid #333"
                        
                        # HTML Card for better data density
                        st.markdown(f"""
                        <div style="border: {border}; padding: 5px; border-radius: 5px; margin-bottom: 10px;">
                            <strong>{bed_id}</strong><br>
                            ❤️Hart rate {info['hr']} bpm | 💨sp02 {info.get('spo2', 98)}%
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Fluid Bar
                        st.progress(int(info['fluid']))
                    
    time.sleep(0.5)