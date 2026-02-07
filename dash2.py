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
        # Unique ID to prevent conflicts
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "Nebula_Dash_Final_Ultimate")
        client.on_message = on_message
        client.connect("broker.hivemq.com", 1883, 60)
        client.subscribe("nebula/ward1/bed/#")
        client.loop_start()
        return client
    except:
        return None

client = start_mqtt()

# -------------------------------------------------
# SESSION STATE & PLACEHOLDERS
# -------------------------------------------------
if "data" not in st.session_state:
    st.session_state.data = {}

# Create Placeholders ONCE
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
            
            # Helper: Parse Sys BP
            if "bp" in payload and isinstance(payload["bp"], str):
                try:
                    payload["sys_bp"] = int(payload["bp"].split("/")[0])
                except:
                    payload["sys_bp"] = 120
            else:
                payload["sys_bp"] = 120

            # Update the single source of truth
            st.session_state.data[bed_id] = payload
        except:
            pass

    # 2. DATA PROCESSING (Logic Fix)
    # Convert dict to list and calculate scores for sorting/filtering
    processed_beds = []
    for bed_id, info in st.session_state.data.items():
        # Calculate NEWS immediately for sorting
        hr = info.get("hr", 0)
        spo2 = info.get("spo2", 98)
        sys_bp = info.get("sys_bp", 120)
        temp = info.get("temp", 37.0)
        
        news_score = calculate_news(hr, spo2, sys_bp, temp)
        risk_color, risk_label = get_risk_level(news_score)
        
        # Determine if Critical (Status explicit OR High NEWS)
        is_critical = (info.get("status") == "CRITICAL") or (risk_color == "RED")
        
        processed_beds.append({
            "id": bed_id,
            "info": info,
            "news_score": news_score,
            "risk_color": risk_color,
            "risk_label": risk_label,
            "is_critical": is_critical
        })

    # SORTING LOGIC: Critical first, then by NEWS score (Desc), then ID
    sorted_beds = sorted(processed_beds, key=lambda x: (not x['is_critical'], -x['news_score'], x['id']))

    # FILTER CRITICAL FOR SIDEBAR
    critical_beds = [b for b in sorted_beds if b['is_critical']]

    # 3. RENDER SIDEBAR
    with sidebar_placeholder.container():
        st.header("🚨 CRITICAL PATIENTS")
        
        if not critical_beds:
            st.success("All Patients Stable")
        else:
            for bed in critical_beds:
                info = bed['info']
                st.markdown(f"""
                <div style="border:2px solid red; background:#330000; padding:10px; border-radius:8px; margin-bottom:8px;">
                    <strong>{bed['id']}</strong><br>
                    ❤️ {info.get('hr')} | 💨 {info.get('spo2')}%<br>
                    🩸 {info.get('bp')} | 🌡️ {info.get('temp')}°C<br>
                    <b style="color:red; font-size:0.9em">⚠️ NEWS: {bed['news_score']}</b>
                </div>
                """, unsafe_allow_html=True)

    # 4. RENDER MAIN GRID
    with main_placeholder.container():
        
        # --- TOP STATS ---
        critical_count = len(critical_beds)
        high_risk_count = sum(1 for b in processed_beds if b['risk_color'] == "RED")

        c1, c2, c3 = st.columns(3)
        c1.metric("Active Nodes", f"{len(processed_beds)}/50")
        c2.metric("CRITICAL ALERTS", critical_count)
        c3.metric("HIGH RISK (NEWS)", high_risk_count)
        
        st.markdown("---")

        # --- BED GRID ---
        cols = st.columns(5)

        # Iterate through the SORTED list
        for i, bed in enumerate(sorted_beds):
            with cols[i % 5]:
                info = bed['info']
                
                # Extract pre-calculated values
                risk_color = bed['risk_color']
                risk_label = bed['risk_label']
                status = info.get("status", "NORMAL")
                
                # Visuals
                hr_color = "#ff4444" if (info.get("hr") > 130 or info.get("hr") < 50) else "#00ff00"
                spo2_color = "#ff4444" if info.get("spo2") < 90 else "#00ff00"
                badge_color = "#ff0000" if status == "CRITICAL" else "#2ecc71"
                
                # Last Seen
                try:
                    ts = info.get("timestamp", time.time())
                    last_seen = int(time.time() - float(ts))
                except:
                    last_seen = 0

                # Border Logic
                border = "2px solid red" if bed['is_critical'] else "1px solid #444"
                bg = "#2a0a0a" if bed['is_critical'] else "#0e1117"

                st.markdown(f"""
                <div style="border:{border}; background-color:{bg}; padding:10px; border-radius:8px; margin-bottom:6px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <strong>{bed['id']}</strong>
                        <span style="background:{badge_color}; color:white; padding:2px 6px; border-radius:4px; font-size:12px;">
                            {status}
                        </span>
                    </div>
                    <div style="margin-top:8px; font-size:0.9em; line-height:1.4;">
                        ❤️ HR: <span style="color:{hr_color}; font-weight:bold;">{info.get('hr')}</span><br>
                        💨 SpO₂: <span style="color:{spo2_color}; font-weight:bold;">{info.get('spo2')}%</span><br>
                        🩸 BP: <b>{info.get('bp')}</b><br>
                        🌡️ Temp: <b>{info.get('temp')}°C</b>
                    </div>
                    <div style="margin-top:6px; font-size:0.8em; color:#aaa; border-top:1px solid #444; padding-top:4px;">
                         NEWS: <b style="color:{risk_color};">{risk_label}</b>
                    </div>
                    <div style="font-size:0.7em; color:#666; text-align:right;">
                        🕒 {last_seen}s ago
                    </div>
                </div>
                """, unsafe_allow_html=True)

                st.progress(int(info.get("fluid", 0)))

    # 5. CONTROL REFRESH RATE
    time.sleep(0.5)