#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <ArduinoJson.h> 

// --- WIFI CONFIG ---
const char* ssid = "Sad";
const char* password = "87654321";
const char* mqtt_server = "broker.hivemq.com";

// --- PIN DEFINITIONS ---
#define LED_BED1 16   // D0
#define LED_BED2 14   // D5
#define LED_BED3 12   // D6
#define LED_BED4 13   // D7
#define BUZZER_PIN 15 // D8
#define BUTTON_PIN 0  // D3 (Flash Button)
#define CRITICAL_LED_PIN 2 // D4 (Red LED)

// --- OLED CONFIG ---
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1 
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// --- VARIABLES ---
WiFiClient espClient;
PubSubClient client(espClient);

// Smart Alarm Variables
bool alarmSilenced = false;
int previousCriticalCount = 0; // To detect NEW emergencies
unsigned long lastButtonPress = 0;
unsigned long lastBuzzerToggle = 0;
unsigned long lastDisplayUpdate = 0;
bool buzzerState = false;

// Status Message Temp Show
unsigned long messageTimer = 0;
bool showingMessage = false;

struct BedState {
  bool isCritical;
  bool isSalineLow;
  bool isNurseCall;
};
BedState beds[5]; 

// --- NEWS LOGIC ---
int calculateNEWS(int hr, int pulse, int spo2, int sys_bp, float temp, int rr) {
  int score = 0;
  if (rr <= 8) score += 3;
  else if (rr >= 9 && rr <= 11) score += 1;
  else if (rr >= 12 && rr <= 20) score += 0;
  else if (rr >= 21 && rr <= 24) score += 2;
  else score += 3;

  if (spo2 <= 91) score += 3;
  else if (spo2 >= 92 && spo2 <= 93) score += 2;
  else if (spo2 >= 94 && spo2 <= 95) score += 1;
  else score += 0; 

  if (temp <= 35.0) score += 3;
  else if (temp >= 35.1 && temp <= 36.0) score += 1;
  else if (temp >= 36.1 && temp <= 38.0) score += 0;
  else if (temp >= 38.1 && temp <= 39.0) score += 1;
  else score += 2; 

  if (sys_bp <= 90) score += 3;
  else if (sys_bp >= 91 && sys_bp <= 100) score += 2;
  else if (sys_bp >= 101 && sys_bp <= 110) score += 1;
  else score += 0; 

  if (hr <= 40) score += 3;
  else if (hr >= 41 && hr <= 50) score += 1;
  else if (hr >= 51 && hr <= 90) score += 0;
  else if (hr >= 91 && hr <= 110) score += 1;
  else if (hr >= 111 && hr <= 130) score += 2;
  else score += 3; 

  if (pulse <= 40) score += 3;
  else if (pulse >= 41 && pulse <= 50) score += 1;
  else if (pulse >= 51 && pulse <= 90) score += 0;
  else if (pulse >= 91 && pulse <= 110) score += 1;
  else if (pulse >= 111 && pulse <= 130) score += 2;
  else score += 3;

  return score;
}

void setup_wifi() {
  delay(10);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }
}

void callback(char* topic, byte* payload, unsigned int length) {
  String message = "";
  for (int i = 0; i < length; i++) message += (char)payload[i];
  
  StaticJsonDocument<512> doc; 
  DeserializationError error = deserializeJson(doc, message);
  if (error) return;

  const char* bedIdStr = doc["id"];
  String statusStr = doc["status"];
  int fluid = doc["fluid"];
  
  int hr = doc["hr"];
  int pulse = doc["pulse"];
  int rr = doc["rr"];
  int spo2 = doc["spo2"];
  float temp = doc["temp"];
  String bp = doc["bp"];
  
  int sys_bp = 120;
  int slashIndex = bp.indexOf('/');
  if (slashIndex > 0) sys_bp = bp.substring(0, slashIndex).toInt();

  int bedNum = 0;
  if (String(bedIdStr).indexOf("001") > 0) bedNum = 1;
  else if (String(bedIdStr).indexOf("002") > 0) bedNum = 2;
  else if (String(bedIdStr).indexOf("003") > 0) bedNum = 3;
  else if (String(bedIdStr).indexOf("004") > 0) bedNum = 4;

  if (bedNum == 0) return;

  int newsScore = calculateNEWS(hr, pulse, spo2, sys_bp, temp, rr);
  
  beds[bedNum].isCritical = (newsScore >= 8);
  beds[bedNum].isSalineLow = (fluid < 20);
  beds[bedNum].isNurseCall = (statusStr == "NURSE CALL");
}

void reconnect() {
  while (!client.connected()) {
    String clientId = "ESP8266NurseHub-";
    clientId += String(random(0xffff), HEX);
    if (client.connect(clientId.c_str())) {
      client.subscribe("nebula/ward1/bed/#");
    } else {
      delay(5000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  
  pinMode(LED_BED1, OUTPUT);
  pinMode(LED_BED2, OUTPUT);
  pinMode(LED_BED3, OUTPUT);
  pinMode(LED_BED4, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(CRITICAL_LED_PIN, OUTPUT);

  Wire.begin(4, 5); 
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) { 
    for(;;);
  }
  display.display();
  delay(1000); 

  setup_wifi();
  client.setServer(mqtt_server, 1883);
  client.setCallback(callback);
  
  display.clearDisplay();
  display.setTextSize(2);
  display.setTextColor(WHITE);
  display.setCursor(0, 20);
  display.println("SYSTEM OK");
  display.display();
}

void showStatus(String title, String bedsList) {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(WHITE);
  display.setCursor(0, 0);
  display.println(title);
  display.drawLine(0, 10, 128, 10, WHITE);
  
  display.setTextSize(2);
  display.setCursor(0, 25);
  display.println(bedsList); 
  display.display();
}

void showTempMessage(String msg1, String msg2) {
  display.clearDisplay();
  display.setTextSize(2);
  display.setCursor(0, 10);
  display.println(msg1);
  display.setCursor(0, 35);
  display.println(msg2);
  display.display();
}

void loop() {
  if (!client.connected()) reconnect();
  client.loop();
  unsigned long currentMillis = millis();

  // --- 1. SMART BUTTON LOGIC (Non-Blocking) ---
  if (digitalRead(BUTTON_PIN) == LOW) {
    // Check if enough time passed since last press (Debounce)
    if (currentMillis - lastButtonPress > 300) { 
      alarmSilenced = !alarmSilenced; // Toggle
      lastButtonPress = currentMillis;
      
      // Trigger temporary message
      showingMessage = true;
      messageTimer = currentMillis;
      
      if (alarmSilenced) {
        showTempMessage("ALARM", "SILENCED");
        digitalWrite(BUZZER_PIN, LOW); // Stop noise instantly
      } else {
        showTempMessage("ALARM", "ENABLED");
      }
    }
  }

  // Clear temp message after 1.5 seconds
  if (showingMessage && (currentMillis - messageTimer > 1500)) {
    showingMessage = false;
  }

  // --- 2. AGGREGATE STATUS ---
  String critBeds = "";
  String salineBeds = "";
  String callBeds = "";
  
  int criticalCount = 0;
  bool anySaline = false;
  bool anyCall = false;

  for (int i = 1; i <= 4; i++) {
    // LED Management
    int pin = -1;
    if (i==1) pin = LED_BED1; else if (i==2) pin = LED_BED2;
    else if (i==3) pin = LED_BED3; else if (i==4) pin = LED_BED4;

    if (beds[i].isCritical || beds[i].isSalineLow || beds[i].isNurseCall) {
      digitalWrite(pin, HIGH);
    } else {
      digitalWrite(pin, LOW);
    }

    if (beds[i].isCritical) {
      if (critBeds != "") critBeds += ",";
      critBeds += String(i);
      criticalCount++;
    }
    if (beds[i].isSalineLow) {
      if (salineBeds != "") salineBeds += ",";
      salineBeds += String(i);
      anySaline = true;
    }
    if (beds[i].isNurseCall) {
      if (callBeds != "") callBeds += ",";
      callBeds += String(i);
      anyCall = true;
    }
  }

  // --- 3. SMART WAKE-UP LOGIC ---
  // If the situation gets WORSE (more critical beds than before), UN-SILENCE the alarm
  if (criticalCount > previousCriticalCount) {
    alarmSilenced = false; 
  }
  previousCriticalCount = criticalCount;

  // --- 4. BUZZER & RED LED LOGIC ---
  int beepDelay = 0; 
  bool isRedLedActive = false;

  if (criticalCount > 0) {
    beepDelay = 200; // FAST BEEP
    isRedLedActive = true;
  } else if (anySaline) {
    beepDelay = 1000; // SLOW BEEP
  } else {
    beepDelay = 0; // OFF
  }

  // Execute Buzzer
  if (beepDelay > 0 && !alarmSilenced) {
    if (currentMillis - lastBuzzerToggle >= beepDelay) {
      lastBuzzerToggle = currentMillis;
      buzzerState = !buzzerState;
      digitalWrite(BUZZER_PIN, buzzerState ? HIGH : LOW);
      
      // Flicker Red LED only if Critical
      if (isRedLedActive) {
         digitalWrite(CRITICAL_LED_PIN, buzzerState ? HIGH : LOW);
      }
    }
  } else {
    digitalWrite(BUZZER_PIN, LOW);
    
    // VISUAL WARNING: If Silenced but Critical, Keep RED LED ON
    if (criticalCount > 0 && alarmSilenced) {
       digitalWrite(CRITICAL_LED_PIN, HIGH);
    } else {
       digitalWrite(CRITICAL_LED_PIN, LOW);
    }
  }

  // --- 5. DISPLAY PRIORITY LOGIC ---
  // Only update display if we are NOT showing a temporary "Silenced" message
  if (!showingMessage && (currentMillis - lastDisplayUpdate > 200)) {
    lastDisplayUpdate = currentMillis;

    if (criticalCount > 0) {
      showStatus("CRITICAL ALERT", "BED " + critBeds);
    } 
    else if (anySaline) {
      showStatus("REPLACE SALINE", "BED " + salineBeds);
    } 
    else if (anyCall) {
      showStatus("ATTEND PATIENT", "BED " + callBeds);
    } 
    else {
      showStatus("SYSTEM STATUS", "ALL CLEAR");
      alarmSilenced = false; // Reset silence if everything is clear
    }
  }
}