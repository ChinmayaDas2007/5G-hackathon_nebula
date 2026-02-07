import streamlit as st
import paho.mqtt.client as mqtt
import json
import time
import random
import threading

# --- CONFIGURATION ---
BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC_BASE = "nebula/ward1/bed"

# --- 1. SHARED LOGIC (Exact Copy from Ghost) ---
class PatientBed:
    def __init__(self, bed_id):
        self.bed_id = bed_id
        # Initial Vitals
        self.hr = random.randint(60, 90)
        self.spo2 = random.randint(96, 100)
        self.fluid = random.randint(50, 100)
        self.bp_sys = random.randint(110, 130)
        self.bp_dia = random.randint(70, 85)
        self.temp = random.uniform(36.5, 37.2)
        
        self.flow_rate = random.uniform(0.5, 2.0)
        self.status = "NORMAL"
        self.critical_timer = 0
        
        # GOD MODE FLASGS
        self.manual_mode = False # If True, auto-drift stops (except fluid)

    def update(self):
        # 1. FLUID LOGIC (Always runs, even in manual)
        self.fluid -= self.flow_rate
        if self.fluid <= 0: self.fluid = 100 
        
        # IF MANUAL MODE IS ON, SKIP VITALS UPDATE
        if self.manual_mode:
            return self.package_data()

        # --- AUTO DRIFT LOGIC (Only runs if NOT manual) ---
        self.hr += random.randint(-2, 2)
        self.hr = max(45, min(190, self.hr))

        if random.random() < 0.3: 
            self.spo2 += random.randint(-1, 1)
        self.spo2 = max(80, min(100, self.spo2))

        if random.random() < 0.5:
            self.bp_sys += random.randint(-2, 2)
            self.bp_dia += random.randint(-1, 1)
        self.bp_sys = max(90, min(180, self.bp_sys))
        self.bp_dia = max(60, min(110, self.bp_dia))

        if random.random() < 0.2:
            self.temp += random.uniform(-0.1, 0.1)
        self.temp = max(33.0, min(40.0, self.temp))

        # Critical Logic (Only in Auto)
        if self.status == "NORMAL" and random.random() < 0.01:
            self.status = "CRITICAL"
            self.critical_timer = 8 
            self.hr = random.randint(140, 170)
            self.spo2 = random.randint(80, 88)
            self.bp_sys = random.randint(70, 90)
            self.bp_dia = random.randint(40, 60)
        
        if self.status == "CRITICAL":
            self.critical_timer -= 1
            if self.critical_timer <= 0:
                self.status = "NORMAL"
                self.hr = random.randint(70, 90)
                self.spo2 = 98
                self.bp_sys = 120
                self.bp_dia = 80

        return self.package_data()

    def package_data(self):
        return {
            "id": self.bed_id,
            "hr": int(self.hr),
            "spo2": int(self.spo2),
            "bp": f"{int(self.bp_sys)}/{int(self.bp_dia)}",
            "temp": round(self.temp, 1),
            "fluid": int(self.fluid),
            "status": self.status,
            "timestamp": time.time()
        }

# --- 2. GLOBAL STATE (Thread-Safe Storage) ---
# We use cache_resource so the beds persist across Streamlit reloads
@st.cache_resource
def get_god_beds():
    # Initialize Beds 2 to 6
    return [PatientBed(f"BED-{i:03d}") for i in range(2, 7)]

god_beds = get_god_beds()

# --- 3. BACKGROUND THREAD (The Engine) ---
# This runs constantly to publish data for Beds 2-6
def simulation_loop():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "Nebula_God_Mode")
    try:
        client.connect(BROKER, PORT, 60)
        client.loop_start()
    except:
        return

    while True:
        for bed in god_beds:
            # This calls update(), which checks manual_mode internally
            data = bed.update() 
            topic = f"{TOPIC_BASE}/{data['id']}"
            client.publish(topic, json.dumps(data))
        
        time.sleep(1) # 1Hz Update Rate

# Start thread only once
if "sim_thread_started" not in st.session_state:
    t = threading.Thread(target=simulation_loop, daemon=True)
    t.start()
    st.session_state.sim_thread_started = True

# --- 4. STREAMLIT INTERFACE ---
st.set_page_config(page_title="God Mode Controller", page_icon="⚡")
st.title("⚡ God Mode: Beds 2-6")

# Sidebar Selector
selected_bed_id = st.sidebar.selectbox("Select Target Bed", [b.bed_id for b in god_beds])

# Find the object for the selected bed
current_bed = next(b for b in god_beds if b.bed_id == selected_bed_id)

st.header(f"Controlling: {current_bed.bed_id}")

# --- MANUAL CONTROL TOGGLE ---
# We use a checkbox to flip the 'manual_mode' switch in the object
is_manual = st.checkbox("🛠️ Enable Manual Control", value=current_bed.manual_mode)
current_bed.manual_mode = is_manual

if is_manual:
    st.success(f"MANUAL OVERRIDE ACTIVE. Auto-drift disabled for {selected_bed_id}.")
    
    col1, col2 = st.columns(2)
    with col1:
        new_hr = st.slider("Heart Rate (bpm)", 0, 200, int(current_bed.hr))
        new_spo2 = st.slider("SpO2 (%)", 0, 100, int(current_bed.spo2))
        new_temp = st.slider("Temperature (°C)", 30.0, 42.0, float(current_bed.temp))
    
    with col2:
        new_sys = st.slider("Systolic BP", 50, 200, int(current_bed.bp_sys))
        new_dia = st.slider("Diastolic BP", 30, 130, int(current_bed.bp_dia))
        new_status = st.selectbox("Status", ["NORMAL", "CRITICAL", "SEPSIS", "SHOCK"], index=0 if current_bed.status=="NORMAL" else 1)

    # Apply values immediately to the object
    # The background thread will pick these up in the next second
    current_bed.hr = new_hr
    current_bed.spo2 = new_spo2
    current_bed.temp = new_temp
    current_bed.bp_sys = new_sys
    current_bed.bp_dia = new_dia
    current_bed.status = new_status

else:
    st.info("🔄 Auto-Pilot Active. Values are drifting naturally.")
    st.markdown(f"""
    **Current Live Values:**
    * ❤️ **HR:** {int(current_bed.hr)}
    * 💨 **SpO2:** {int(current_bed.spo2)}%
    * 🩸 **BP:** {int(current_bed.bp_sys)}/{int(current_bed.bp_dia)}
    * 🌡️ **Temp:** {round(current_bed.temp, 1)}°C
    """)

st.markdown("---")
st.caption("💧 Saline level is always auto-draining.")
st.progress(int(current_bed.fluid))

# Auto-refresh the UI every 1 second to show the drifting values
if not is_manual:
    time.sleep(1)
    st.rerun()