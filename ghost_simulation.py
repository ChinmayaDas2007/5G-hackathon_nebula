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
        # --- INITIAL VITALS (Healthy-ish start) ---
        self.hr = random.randint(60, 90)
        self.spo2 = random.randint(96, 100)
        self.fluid = random.randint(50, 100)
        
        # New Vitals: BP and Temp
        self.bp_sys = random.randint(110, 130) # Systolic
        self.bp_dia = random.randint(70, 85)   # Diastolic
        self.temp = random.uniform(36.5, 37.2) # Celsius
        
        # Unique Flow Rate (0.5% to 2.0% per tick)
        self.flow_rate = random.uniform(0.5, 2.0)
        self.status = "NORMAL"
        self.critical_timer = 0

    def update(self):
        # 1. FLUID LOGIC (The Drip)
        self.fluid -= self.flow_rate
        if self.fluid <= 0:
            self.fluid = 100 # Nurse changed the bag
        
        # 2. HEART RATE DRIFT (+- 2 bpm)
        self.hr += random.randint(-2, 2)
        self.hr = max(45, min(190, self.hr))

        # 3. SPO2 DRIFT (+- 1 %)
        if random.random() < 0.3: 
            self.spo2 += random.randint(-1, 1)
        self.spo2 = max(80, min(100, self.spo2))

        # 4. BLOOD PRESSURE DRIFT (+- 2 mmHg)
        # as BP tends to fluctuate slightly
        if random.random() < 0.5:
            self.bp_sys += random.randint(-2, 2)
            self.bp_dia += random.randint(-1, 1)
        
        # Keep BP in realistic limits
        self.bp_sys = max(90, min(180, self.bp_sys))
        self.bp_dia = max(60, min(110, self.bp_dia))

        # 5. TEMP DRIFT (Very slow, +- 0.1 C)
        if random.random() < 0.2: # Changes rarely
            self.temp += random.uniform(-0.1, 0.1)
        self.temp = max(33.0, min(40.0, self.temp))

        # 6. CRITICAL EVENT LOGIC (Cardiac Arrest / Shock)
        # 1% chance to enter critical state
        if self.status == "NORMAL" and random.random() < 0.01:
            self.status = "CRITICAL"
            self.critical_timer = 8 # Lasts 8 seconds now
            
            # Force vitals to CRITICAL values
            self.hr = random.randint(140, 170)  # Tachycardia
            self.spo2 = random.randint(80, 88)  # Hypoxia
            self.bp_sys = random.randint(70, 90)# Hypotension (Shock)
            self.bp_dia = random.randint(40, 60)
        
        # Count down critical time
        if self.status == "CRITICAL":
            self.critical_timer -= 1
            if self.critical_timer <= 0:
                # Recover to Normal
                self.status = "NORMAL"
                self.hr = random.randint(70, 90)
                self.spo2 = 98
                self.bp_sys = 120
                self.bp_dia = 80

        # --- PACKAGING DATA ---
        return {
            "id": self.bed_id,
            "hr": int(self.hr),
            "spo2": int(self.spo2),
            "bp": f"{int(self.bp_sys)}/{int(self.bp_dia)}", # String format "120/80"
            "temp": round(self.temp, 1), # Round to 1 decimal
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

# --- INITIALIZE 44 BEDS (7 to 50) ---
# Modified range: Starts at 7, stops at 51 (so it includes 50)
beds = [PatientBed(f"BED-{i:03d}") for i in range(7, 51)]

print(f"🚀 Starting REALISTIC {len(beds)}-Node Simulation (Bed 007 - 050)...")

# --- MAIN LOOP ---
while True:
    for bed in beds:
        data = bed.update()
        
        topic = f"{TOPIC_BASE}/{data['id']}"
        client.publish(topic, json.dumps(data))
    
    print(".", end="", flush=True)
    time.sleep(1) # Updates every 1 second