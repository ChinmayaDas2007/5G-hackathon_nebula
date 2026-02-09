#include <WiFi.h>
#include <PubSubClient.h>
#include <ESP32Encoder.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include "soc/soc.h"             
#include "soc/rtc_cntl_reg.h"    

// --- WIFI & MQTT CONFIG ---
const char* ssid = "Sad";        
const char* password = "87654321";
const char* mqtt_server = "broker.hivemq.com";

// --- PIN MAPPING ---
#define POT_SPO2_PIN 34    
#define POT_BP_PIN 33      
#define TEMP_PIN 32        
#define ROTARY_CLK 25      
#define ROTARY_DT 26       
#define NURSE_BTN 27       
#define LED_PIN 2          // Blue Onboard LED (Heartbeat)
#define NURSE_LED_PIN 4    // Red External LED (Alert)

// --- LIMITS ---
const int HR_MIN = 40;   const int HR_MAX = 180;
const int SPO2_MIN = 80; const int SPO2_MAX = 100;
const int BP_MIN = 90;   const int BP_MAX = 180;

// --- OBJECTS ---
WiFiClient espClient;
PubSubClient client(espClient);
ESP32Encoder encoder;
OneWire oneWire(TEMP_PIN);
DallasTemperature sensors(&oneWire);

// --- VARIABLES ---
long lastMsgTime = 0;
unsigned long previousBlinkMillis = 0;
unsigned long lastTempRequest = 0; // For Async Temp
int ledState = LOW;
float currentTemp = 36.5; // Start with a safe default

void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);

  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    digitalWrite(LED_PIN, !digitalRead(LED_PIN)); // Fast blink while connecting
    delay(100);
    Serial.print(".");
  }

  digitalWrite(LED_PIN, LOW);
  Serial.println("\nWiFi Connected!");
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    if (client.connect("Nebula_Physical_BED001")) {
      Serial.println("connected");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      delay(2000); // Wait a bit before retrying
    }
  }
}

void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0); // Disable brownout detector

  Serial.begin(115200);
  
  pinMode(NURSE_BTN, INPUT_PULLUP);
  pinMode(LED_PIN, OUTPUT);       
  pinMode(NURSE_LED_PIN, OUTPUT); 
  
  pinMode(ROTARY_CLK, INPUT_PULLUP);
  pinMode(ROTARY_DT, INPUT_PULLUP);

  // --- SENSOR SETUP ---
  sensors.begin();
  // CRITICAL FIX: Make temp sensor NON-BLOCKING
  sensors.setWaitForConversion(false); 
  sensors.requestTemperatures(); // Start the first read

  setup_wifi();
  
  client.setServer(mqtt_server, 1883);
  encoder.attachHalfQuad(ROTARY_DT, ROTARY_CLK);
  encoder.setCount(75); // Start at 75 BPM
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  // --- A. READ SENSORS (INSTANT RESPONSE) ---
  
  // 1. HEART RATE (Encoder + "Humanizing" Logic)
  long encoderCount = encoder.getCount();
  if (encoderCount < HR_MIN) { encoder.setCount(HR_MIN); encoderCount = HR_MIN; }
  if (encoderCount > HR_MAX) { encoder.setCount(HR_MAX); encoderCount = HR_MAX; }
  
  int baseHr = (int)encoderCount;
  
  // Add "Natural Breathing" Variation (Random -2 to +2 bpm)
  int breathing = 0;
  if (millis() % 2000 < 1000) breathing = 1; else breathing = -1;
  int finalHr = baseHr + breathing;

  // 2. SPO2 (Potentiometer)
  int rawSpo2 = analogRead(POT_SPO2_PIN);
  int spo2 = map(rawSpo2, 0, 4095, SPO2_MIN, SPO2_MAX);

  // 3. Blood Pressure (Potentiometer)
  int rawBP = analogRead(POT_BP_PIN);
  int sys_bp = map(rawBP, 0, 4095, BP_MIN, BP_MAX);
  int dia_bp = sys_bp - 40; // Simple logic for Diastolic

  // 4. TEMPERATURE (ASYNC LOGIC - NO LAG)
  if (millis() - lastTempRequest >= 1000) {
    float t = sensors.getTempCByIndex(0); // Read the result from LAST request
    
    // Validate result (-127 is error)
    if (t > -100) {
      if (t < 34.0) t = 34.0;
      if (t > 41.0) t = 41.0;
      currentTemp = t;
    }
    
    sensors.requestTemperatures(); // Tell sensor to start NEXT reading
    lastTempRequest = millis();
  }

  // --- B. NURSE & STATUS LOGIC ---
  bool nursePressed = (digitalRead(NURSE_BTN) == LOW);
  
  if (nursePressed) {
    digitalWrite(NURSE_LED_PIN, HIGH);
  } else {
    digitalWrite(NURSE_LED_PIN, LOW);
  }

  // Determine Status
  String status = "NORMAL";
  if (nursePressed) {
    status = "NURSE CALL"; 
  } 
  else if (finalHr > 140 || spo2 < 90 || currentTemp > 38.0) {
    status = "CRITICAL"; 
  }
  else if (finalHr > 110 || spo2 < 94) {
    status = "WARNING"; 
  }

  // --- C. DYNAMIC HEARTBEAT LED ---
  int beatInterval = 60000 / max(finalHr, 40); 
  
  unsigned long currentMillis = millis();
  if (currentMillis - previousBlinkMillis >= beatInterval) { 
    previousBlinkMillis = currentMillis;
    ledState = (ledState == LOW) ? HIGH : LOW; 
    digitalWrite(LED_PIN, ledState);
  }

  // --- D. UPLOAD TO CLOUD (Every 1 Sec) ---
  long now = millis();
  if (now - lastMsgTime > 1000) {
    lastMsgTime = now;

    // --- UPDATED JSON CONSTRUCTION ---
    String json = "{";
    json += "\"id\": \"BED-001\",";
    json += "\"hr\": " + String(finalHr) + ",";
    json += "\"pulse\": " + String(finalHr) + ","; // FIX: Pulse = HR
    json += "\"rr\": 18,";                          // FIX: Constant RR = 18
    json += "\"spo2\": " + String(spo2) + ",";
    json += "\"bp\": \"" + String(sys_bp) + "/" + String(dia_bp) + "\",";
    json += "\"temp\": " + String(currentTemp, 1) + ",";
    json += "\"fluid\": 90,"; 
    json += "\"status\": \"" + status + "\",";
    json += "\"timestamp\": " + String(now/1000);
    json += "}";

    // Print to Serial for debugging
    Serial.print("HR: "); Serial.print(finalHr);
    Serial.print(" | Pulse: "); Serial.print(finalHr);
    Serial.print(" | RR: 18"); 
    Serial.print(" | Status: "); Serial.println(status);
    
    client.publish("nebula/ward1/bed/BED-001", json.c_str());
  }
}