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

# --- 1. SHARED LOGIC ---
class PatientBed:
    def __init__(self, bed_id):
        self.bed_id = bed_id
        self.hr = random.randint(60, 90)
        self.pulse = random.randint(58, 88)
        self.rr = random.randint(12, 20)
        self.spo2 = random.randint(96, 100)
        self.fluid = random.randint(50, 100)
        self.bp_sys = random.randint(110, 130)
        self.bp_dia = random.randint(70, 85)
        self.temp = random.uniform(36.5, 37.2)
        
        self.flow_rate = random.uniform(0.4, 0.7)
        self.status = "NORMAL"
        self.critical_timer = 0
        self.manual_mode = False 
        self.nurse_call = False 

    def update(self):
        self.fluid -= self.flow_rate
        if self.fluid <= 0: self.fluid = 100 
        
        if self.manual_mode:
            return self.package_data()

        # --- AUTO DRIFT ---
        self.hr += random.randint(-2, 2)
        self.hr = max(45, min(190, self.hr))
        
        self.pulse = self.hr - random.randint(0, 2)
        self.pulse = max(40, min(190, self.pulse))
        
        if random.random() < 0.2: 
            self.rr += random.randint(-1, 1)
        self.rr = max(8, min(40, self.rr))

        if random.random() < 0.3: self.spo2 += random.randint(-1, 1)
        self.spo2 = max(80, min(100, self.spo2))

        if random.random() < 0.5:
            self.bp_sys += random.randint(-2, 2)
            self.bp_dia += random.randint(-1, 1)
        self.bp_sys = max(90, min(180, self.bp_sys))
        self.bp_dia = max(60, min(110, self.bp_dia))

        if random.random() < 0.2: self.temp += random.uniform(-0.1, 0.1)
        self.temp = max(33.0, min(40.0, self.temp))

        # Critical Logic (UPDATED: 0.1% chance)
        if self.status == "NORMAL" and not self.nurse_call and random.random() < 0.001:
            self.status = "CRITICAL"
            self.critical_timer = 15 
            self.hr = random.randint(140, 170)
            self.pulse = random.randint(135, 165)
            self.rr = random.randint(28, 35) 
            self.spo2 = random.randint(80, 88)
            self.bp_sys = random.randint(70, 90)
            self.bp_dia = random.randint(40, 60)
        
        if self.status == "CRITICAL" and not self.nurse_call:
            self.critical_timer -= 1
            if self.critical_timer <= 0:
                self.status = "NORMAL"
                self.hr = random.randint(70, 90)
                self.pulse = self.hr - 2
                self.rr = random.randint(12, 20)
                self.spo2 = 98
                self.bp_sys = 120
                self.bp_dia = 80
        
        # --- FIX FOR NURSE CALL ---
        # Explicitly overwrite status so ESP8266 detects it
        if self.nurse_call:
            self.status = "NURSE CALL"
        elif self.status == "NURSE CALL" and not self.nurse_call:
            self.status = "NORMAL"

        return self.package_data()

    def package_data(self):
        return {
            "id": self.bed_id,
            "hr": int(self.hr),
            "pulse": int(self.pulse),
            "rr": int(self.rr),
            "spo2": int(self.spo2),
            "bp": f"{int(self.bp_sys)}/{int(self.bp_dia)}",
            "temp": round(self.temp, 1),
            "fluid": int(self.fluid),
            "status": self.status,
            "nurse_call": self.nurse_call,
            "timestamp": time.time()
        }

@st.cache_resource
def get_god_beds():
    return [PatientBed(f"BED-{i:03d}") for i in range(2, 7)]

god_beds = get_god_beds()

def simulation_loop():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "Nebula_God_Mode")
    try:
        client.connect(BROKER, PORT, 60)
        client.loop_start()
    except:
        return

    while True:
        for bed in god_beds:
            data = bed.update() 
            topic = f"{TOPIC_BASE}/{data['id']}"
            client.publish(topic, json.dumps(data))
        time.sleep(1) 

if "sim_thread_started" not in st.session_state:
    t = threading.Thread(target=simulation_loop, daemon=True)
    t.start()
    st.session_state.sim_thread_started = True

# --- STREAMLIT UI ---
st.set_page_config(page_title="God Mode Controller", page_icon="⚡")
st.title("⚡ God Mode: Beds 2-6")

selected_bed_id = st.sidebar.selectbox("Select Target Bed", [b.bed_id for b in god_beds])
current_bed = next(b for b in god_beds if b.bed_id == selected_bed_id)

st.header(f"Controlling: {current_bed.bed_id}")

col_main1, col_main2 = st.columns([1, 2])
with col_main1:
    if st.button("🚨 Call Nurse" if not current_bed.nurse_call else "✅ Clear Alarm", 
                 type="primary" if not current_bed.nurse_call else "secondary"):
        current_bed.nurse_call = not current_bed.nurse_call
        st.rerun()

is_manual = st.checkbox("🛠️ Enable Manual Control", value=current_bed.manual_mode)
current_bed.manual_mode = is_manual

if is_manual:
    st.success(f"MANUAL OVERRIDE ACTIVE.")
    
    col1, col2 = st.columns(2)
    with col1:
        new_hr = st.slider("Heart Rate (bpm)", 0, 200, int(current_bed.hr))
        new_pulse = st.slider("Pulse Rate", 0, 200, int(current_bed.pulse))
        new_rr = st.slider("Resp. Rate (bpm)", 0, 50, int(current_bed.rr)) 
        new_spo2 = st.slider("SpO2 (%)", 0, 100, int(current_bed.spo2))
    
    with col2:
        new_temp = st.slider("Temperature (°C)", 30.0, 42.0, float(current_bed.temp))
        new_sys = st.slider("Systolic BP", 50, 200, int(current_bed.bp_sys))
        new_dia = st.slider("Diastolic BP", 30, 130, int(current_bed.bp_dia))

    current_bed.hr = new_hr
    current_bed.pulse = new_pulse
    current_bed.rr = new_rr
    current_bed.spo2 = new_spo2
    current_bed.temp = new_temp
    current_bed.bp_sys = new_sys
    current_bed.bp_dia = new_dia

else:
    st.info("🔄 Auto-Pilot Active.")
    st.markdown(f"""
    **Current Live Values:**
    * ❤️ **HR:** {int(current_bed.hr)}
    * 💓 **Pulse:** {int(current_bed.pulse)}
    * 🫁 **RR:** {int(current_bed.rr)} (Breaths/min)
    * 💨 **SpO2:** {int(current_bed.spo2)}%
    * 🩸 **BP:** {int(current_bed.bp_sys)}/{int(current_bed.bp_dia)}
    * 🌡️ **Temp:** {round(current_bed.temp, 1)}°C
    * 🚨 **Nurse Call:** {"**ACTIVE**" if current_bed.nurse_call else "OFF"}
    """)

st.markdown("---")
st.caption("💧 Saline level is always auto-draining.")
st.progress(int(current_bed.fluid))

if not is_manual:
    time.sleep(1)
    st.rerun()