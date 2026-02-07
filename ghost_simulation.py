import paho.mqtt.client as mqtt
import json
import time
import random

# --- CONFIGURATION ---
BROKER = "broker.hivemq.com" 
PORT = 1883
TOPIC_BASE = "nebula/ward1/bed"

# --- SMART BED CLASS ---
# This class remembers the state of each patient
class PatientBed:
    def __init__(self, bed_id):
        self.bed_id = bed_id
        # Initial Vitals (Healthy-ish start)
        self.hr = random.randint(60, 90)
        self.spo2 = random.randint(96, 100)
        self.fluid = random.randint(50, 100)
        # Unique Flow Rate for this bed (0.5% to 2.0% per tick)
        self.flow_rate = random.uniform(0.5, 2.0)
        self.status = "NORMAL"
        self.critical_timer = 0

    def update(self):
        # 1. FLUID LOGIC (The Drip)
        self.fluid -= self.flow_rate
        if self.fluid <= 0:
            self.fluid = 100 # Nurse changed the bag
        
        # 2. HEART RATE DRIFT (+- 2 bpm)
        drift = random.randint(-2, 2)
        self.hr += drift
        # Keeing within human limits
        self.hr = max(45, min(190, self.hr))

        # 3. SPO2 DRIFT (+- 1 %)
        # SpO2 tends to stay stable
        if random.random() < 0.3: # Only change 30% of the time 
            self.spo2 += random.randint(-1, 1)
        self.spo2 = max(80, min(100, self.spo2))

        # 4. CRITICAL EVENT LOGIC (Random Cardiac Arrest)
        # 1% chance to enter critical state, lasts for 5 ticks
        if self.status == "NORMAL" and random.random() < 0.01:
            self.status = "CRITICAL"
            self.critical_timer = 5
            # Force vitals to look bad instantly
            self.hr = random.randint(140, 170) 
            self.spo2 = random.randint(80, 88)
        
        # Count down critical time
        if self.status == "CRITICAL":
            self.critical_timer -= 1
            if self.critical_timer <= 0:
                self.status = "NORMAL"
                self.hr = random.randint(70, 90) # Recover
                self.spo2 = 98

        return {
            "id": self.bed_id,
            "hr": int(self.hr),
            "spo2": int(self.spo2),
            "fluid": int(self.fluid),
            "status": self.status,
            "timestamp": time.time()
        }

# --- CONNECT TO MQTT ---
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "Nebula_Smart_Ghost")
try:
    client.connect(BROKER, PORT, 60)
    print(f"✅ Connected to 5G Cloud: {BROKER}")
except Exception as e:
    print(f"❌ Connection Failed: {e}")
    exit()

# --- INITIALIZE 50 BEDS ---
beds = [PatientBed(f"BED-{i:03d}") for i in range(1, 51)]

print("🚀 Starting REALISTIC 50-Node Simulation...")

# --- MAIN LOOP ---
while True:
    for bed in beds:
        data = bed.update()
        
        topic = f"{TOPIC_BASE}/{data['id']}"
        client.publish(topic, json.dumps(data))
    
    print(".", end="", flush=True)
    time.sleep(1) # Updates every 1 second