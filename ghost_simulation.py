import paho.mqtt.client as mqtt
import json
import time
import random

# --- CONFIGURATION ---
BROKER = "broker.hivemq.com" 
PORT = 1883
TOPIC_BASE = "nebula/ward1/bed"

# --- SMART BED CLASS ---
class PatientBed:
    def __init__(self, bed_id):
        self.bed_id = bed_id
        # --- INITIAL VITALS ---
        self.hr = random.randint(60, 90)    # Electrical Heart Rate
        self.pulse = random.randint(58, 88) # Mechanical Pulse
        self.spo2 = random.randint(96, 100)
        self.rr = random.randint(12, 20)
        self.fluid = random.randint(50, 100)
        
        self.bp_sys = random.randint(110, 130)
        self.bp_dia = random.randint(70, 85)
        self.temp = random.uniform(36.5, 37.2)
        
        # SLOW Saline Flow (3 mins to drain)
        self.flow_rate = random.uniform(0.4, 0.7)
        self.status = "NORMAL"
        self.critical_timer = 0

    def update(self):
        # 1. FLUID LOGIC
        self.fluid -= self.flow_rate
        if self.fluid <= 0:
            self.fluid = 100 
        
        # 2. HEART RATE & PULSE DRIFT
        self.hr += random.randint(-2, 2)
        self.hr = max(45, min(190, self.hr))

        # Pulse follows HR but with slight variation
        self.pulse = self.hr - random.randint(0, 3)
        self.pulse = max(40, min(190, self.pulse))

        # 3. RESPIRATORY RATE DRIFT
        if random.random() < 0.2:
            self.rr += random.randint(-1, 1)
        self.rr = max(8, min(40, self.rr))

        # 4. SPO2 DRIFT
        if random.random() < 0.3: 
            self.spo2 += random.randint(-1, 1)
        self.spo2 = max(80, min(100, self.spo2))

        # 5. BP DRIFT
        if random.random() < 0.5:
            self.bp_sys += random.randint(-2, 2)
            self.bp_dia += random.randint(-1, 1)
        self.bp_sys = max(90, min(180, self.bp_sys))
        self.bp_dia = max(60, min(110, self.bp_dia))

        # 6. TEMP DRIFT
        if random.random() < 0.2: 
            self.temp += random.uniform(-0.1, 0.1)
        self.temp = max(33.0, min(40.0, self.temp))

       # 7. CRITICAL EVENT LOGIC (UPDATED: 0.02% chance)
       # This makes crashes much rarer (approx 1 every 2 mins for the whole ward)
        if self.status == "NORMAL" and random.random() < 0.0002:
            self.status = "CRITICAL"
            self.critical_timer = 15 
            
            # CRITICAL VALUES
            self.hr = random.randint(130, 160)
            self.pulse = random.randint(125, 155)
            self.rr = random.randint(28, 35)
            self.spo2 = random.randint(80, 88)
            self.bp_sys = random.randint(70, 90)
            self.bp_dia = random.randint(40, 60)
        
        if self.status == "CRITICAL":
            self.critical_timer -= 1
            if self.critical_timer <= 0:
                # Recover
                self.status = "NORMAL"
                self.hr = random.randint(70, 90)
                self.pulse = self.hr - 2
                self.rr = random.randint(12, 20)
                self.spo2 = 98
                self.bp_sys = 120
                self.bp_dia = 80

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
            "timestamp": time.time()
        }

# --- CONNECT & RUN ---
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "Nebula_Smart_Ghost")
try:
    client.connect(BROKER, PORT, 60)
    print(f"✅ Connected to 5G Cloud: {BROKER}")
except Exception as e:
    print(f"❌ Connection Failed: {e}")
    exit()

beds = [PatientBed(f"BED-{i:03d}") for i in range(7, 51)]
print(f"🚀 Starting REALISTIC {len(beds)}-Node Simulation (Bed 007 - 050)...")

while True:
    for bed in beds:
        data = bed.update()
        topic = f"{TOPIC_BASE}/{data['id']}"
        client.publish(topic, json.dumps(data))
    time.sleep(1)