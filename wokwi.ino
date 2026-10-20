#include "secrets.h"
#include <Wire.h>
#include <WiFi.h>
#include <BlynkSimpleEsp32.h>
#include <RTClib.h>
#include <ESP32Servo.h>
#include <LiquidCrystal_I2C.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <HX711.h>
#include <Preferences.h>
#include <math.h>

constexpr int SERVO_PIN = 18, PH_PIN = 34, TURBIDITY_PIN = 33;
constexpr int TEMP_PIN = 14, HX_DT = 26, HX_SCK = 25;
constexpr unsigned long FEED_MS = 2000, COOLDOWN_MS = 10000;
// Jadwal asli. Setel RTC ke WIB sebelum penggunaan.
const uint8_t FEED_TIMES[][2] = {{23,42}, {23,47}, {17,14}, {17,16}};
constexpr float SCALE_FACTOR = 420.0f; // Kalibrasi perangkat nyata dalam gram.
constexpr bool ENABLE_EVENTS = false; // Buat event pakan_diberikan di Console terlebih dahulu.
RTC_DS1307 rtc;
LiquidCrystal_I2C lcd(0x27, 20, 4);
Servo feeder;
OneWire oneWire(TEMP_PIN);
DallasTemperature temperatureSensor(&oneWire);
HX711 scale;
Preferences storage;
BlynkTimer timer;
bool active = false, feeding = false, rtcReady = false, storageReady = false;
bool hasFed = false, tareReady = false;
unsigned long feedStarted = 0, lastFeed = 0, temperatureRequested = 0;
bool temperaturePending = false;
uint32_t scheduleDay[4] = {0, 0, 0, 0};
float temperature = NAN, ph = 0, weight = NAN, turbidity = 0;
String statusText = "Sistem OFF";

void publishState() {
  if (!Blynk.connected()) return;
  Blynk.virtualWrite(V6, active ? 1 : 0);
  Blynk.virtualWrite(V7, feeding ? 1 : 0);
  Blynk.virtualWrite(V8, statusText);
}
void setStatus(const String &message) {
  statusText = message;
  Serial.println(message);
  publishState();
}
bool startFeed(const char *source) {
  if (!active) { setStatus("Ditolak: sistem OFF"); return false; }
  if (feeding) { setStatus("Ditolak: sedang feeding"); return false; }
  if (hasFed && (unsigned long)(millis() - lastFeed) < COOLDOWN_MS) {
    setStatus("Ditolak: cooldown 10s"); return false;
  }
  feeding = true;
  hasFed = true;
  lastFeed = feedStarted = millis();
  feeder.write(90);
  setStatus(String("Pakan: ") + source);
  return true;
}
BLYNK_CONNECTED() {
  // Reset manual command: never sync/replay V3 on reconnect.
  Blynk.virtualWrite(V3, 0);
  publishState();
  Blynk.syncVirtual(V0);
}
BLYNK_WRITE(V0) {
  active = param.asInt() == 1;
  if (!active) {
    feeder.write(0);
    feeding = false;
  }
  setStatus(active ? "Sistem ON" : "Sistem OFF");
}
BLYNK_WRITE(V3) {
  if (param.asInt() == 1) {
    Blynk.virtualWrite(V3, 0);
    startFeed("manual/gestur");
  }
}
void serviceServo() {
  if (feeding && (unsigned long)(millis() - feedStarted) >= FEED_MS) {
    feeder.write(0);
    feeding = false;
    setStatus("Pakan selesai");
    if (ENABLE_EVENTS && Blynk.connected())
      Blynk.logEvent("pakan_diberikan", "Satu siklus pakan selesai");
  }
}
void readSensors() {
  // Monitoring remains available while dispensing is OFF.
  ph = analogRead(PH_PIN) * (14.0f / 4095.0f);
  turbidity = analogRead(TURBIDITY_PIN) * (100.0f / 4095.0f);
  if (scale.is_ready()) {
    if (!tareReady) {
      scale.set_offset(scale.read());
      tareReady = true; // Empty hopper during initial tare.
    } else {
      weight = scale.get_units(1);
      if (weight < 0) weight = 0;
    }
  } else {
    weight = NAN;
  }
  if (!temperaturePending) {
    temperatureSensor.requestTemperatures();
    temperatureRequested = millis();
    temperaturePending = true;
  }
}
void serviceTemperature() {
  if (temperaturePending && (unsigned long)(millis() - temperatureRequested) >= 750) {
    float value = temperatureSensor.getTempCByIndex(0);
    temperature = value == DEVICE_DISCONNECTED_C ? NAN : value;
    temperaturePending = false;
  }
}
void publishSensors() {
  if (!Blynk.connected()) return;
  Blynk.virtualWrite(V1, isnan(temperature) ? -127 : temperature);
  Blynk.virtualWrite(V2, ph);
  Blynk.virtualWrite(V4, isnan(weight) ? -1 : weight);
  Blynk.virtualWrite(V5, turbidity);
  publishState();
}
void checkSchedule() {
  if (!active || !rtcReady) return;
  DateTime now = rtc.now();
  uint32_t day = now.year() * 10000UL + now.month() * 100UL + now.day();
  for (int i = 0; i < 4; ++i) {
    if (now.hour() == FEED_TIMES[i][0] && now.minute() == FEED_TIMES[i][1] && scheduleDay[i] != day) {
      // Consume slot even when cooldown/manual feeding blocks it; no delayed surprise feed.
      scheduleDay[i] = day;
      if (storageReady) {
        String key = String("slot") + i;
        storage.putUInt(key.c_str(), day);
      }
      startFeed("jadwal");
    }
  }
}
void lcdLine(uint8_t row, String text) {
  text = text.substring(0, 20);
  while (text.length() < 20) text += ' ';
  lcd.setCursor(0, row);
  lcd.print(text);
}
void updateDisplay() {
  String clock = "RTC tidak tersedia";
  if (rtcReady) {
    DateTime now = rtc.now();
    char value[21];
    snprintf(value, sizeof(value), "%02u:%02u:%02u %s", now.hour(), now.minute(), now.second(), active ? "ON" : "OFF");
    clock = value;
  }
  lcdLine(0, clock);
  lcdLine(1, statusText);
  lcdLine(2, "T:" + (isnan(temperature) ? String("ERR") : String(temperature, 1)) + "C pH:" + String(ph, 1));
  lcdLine(3, "W:" + (isnan(weight) ? String("ERR") : String(weight, 0)) + "g NTU:" + String(turbidity, 0));
}
void reconnect() {
  if (WiFi.status() != WL_CONNECTED) WiFi.reconnect();
  else if (!Blynk.connected() && !feeding) Blynk.connect(300);
}
void setup() {
  Serial.begin(115200);
  feeder.setPeriodHertz(50);
  feeder.attach(SERVO_PIN, 500, 2400);
  feeder.write(0);
  Wire.begin(21, 22);
  lcd.init();
  lcd.backlight();
  rtcReady = rtc.begin();
  if (rtcReady && !rtc.isrunning()) rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
  if (!rtcReady) Serial.println("RTC gagal: jadwal dinonaktifkan; manual tersedia.");
  storageReady = storage.begin("feeding", false);
  for (int i = 0; i < 4 && storageReady; ++i) {
    String key = String("slot") + i;
    scheduleDay[i] = storage.getUInt(key.c_str(), 0);
  }
  analogReadResolution(12);
  temperatureSensor.begin();
  temperatureSensor.setWaitForConversion(false);
  scale.begin(HX_DT, HX_SCK);
  scale.set_scale(SCALE_FACTOR);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Blynk.config(BLYNK_AUTH_TOKEN, BLYNK_SERVER, 80);
  timer.setInterval(1000L, readSensors);
  timer.setInterval(3000L, publishSensors);
  timer.setInterval(1000L, checkSchedule);
  timer.setInterval(500L, updateDisplay);
  timer.setInterval(5000L, reconnect);
  updateDisplay();
}
void loop() {
  serviceServo();
  serviceTemperature();
  if (Blynk.connected()) Blynk.run();
  serviceServo();
  timer.run();
}
