


/*
 * Smart Nursery — ESP32 Firmware
 * --------------------------------
 * Sensors : DHT11 (temp), Gas/Smoke (ADC), LDR (light), PIR (motion)
 * Outputs : 3x status LEDs, Room LED, Buzzer (LEDC PWM), Fan (L298), Servo (crib)
 * Comms   : Classic Bluetooth SPP ("SmartNursery") + USB Serial
 *
 * SINGLE-CHAR COMMANDS (identical on USB Serial AND Bluetooth):
 *   'T' -> int32_t temperature                (4 bytes, LE)
 *   'G' -> uint8_t gas_detected               (1 byte)
 *   'B' -> uint8_t baby_awake                 (1 byte)
 *   'A' -> int32_t temp | u8 gas | u8 awake   (6 bytes, packed)
 *   'I' -> CRY DETECTED  : servo + buzzer (2s pulse)
 *   'C' -> SERVO ONLY    : servo runs, no buzzer
 *   'S' -> STOP          : servo off + buzzer off + cry_detected = false
 *
 * TEXT COMMANDS (newline-terminated, USB or BT):
 *   "CRY_DETECTED" / "SERVO_START"  -> start servo
 *   "CRY_ENDED"    / "SERVO_STOP"   -> stop servo
 */

#include <ESP32Servo.h>
#include <math.h>
#include "DHT.h"
#include "BluetoothSerial.h"

// ------------------------------------------------------------------
// Bluetooth Serial Setup
// ------------------------------------------------------------------
#if !defined(CONFIG_BT_ENABLED) || !defined(CONFIG_BLUEDROID_ENABLED)
#error Bluetooth is not enabled! Please run make menuconfig and select it
#endif

BluetoothSerial SerialBT;

// ------------------------------------------------------------------
// Pin Definitions (ESP32 DevKit V1)
// ------------------------------------------------------------------
#define dht_pin           4      // DHT11 Temperature & Humidity Sensor
#define gas_sensor_pin    34     // Gas / Smoke Sensor (ADC1, input-only)
#define ldr_sensor_pin    35     // LDR Ambient Light Sensor (ADC1, input-only)
#define pir_sensor_pin    32     // PIR Motion Sensor

#define red_led           33     // High Temp Red LED
#define green_led         25     // Moderate Temp Green LED
#define blue_led          26     // Low Temp / Gas Blue LED
#define room_led          27     // Room Lamp LED
#define buzzer            14     // Buzzer Alarm

#define fan_in1           19     // L298 IN1 (Forward Direction)
#define fan_in2           23     // L298 IN2 (Backward Direction)
#define bed_servo_pin     18     // Crib Rocking Servo Motor

DHT dht(dht_pin, DHT11);

// ------------------------------------------------------------------
// Buzzer PWM config (replaces tone()/noTone() to avoid Servo timer conflict)
// ------------------------------------------------------------------
#define BUZZER_FREQ         2000
#define BUZZER_RESOLUTION   8      // 8-bit -> duty range 0-255
#define BUZZER_DUTY_ON      128    // ~50% duty = audible tone
#define BUZZER_DUTY_OFF     0

Servo bedServo;

// ------------------------------------------------------------------
// Live sensor / system state
// ------------------------------------------------------------------
int  current_temperature = 25;
unsigned long start_time = 0;
int  time_for_temp_check = 1000;

bool gas_detected        = false;
bool baby_awake          = false;
bool laptop_cry_detected = false;

// ------------------------------------------------------------------
// Bluetooth status
// ------------------------------------------------------------------
bool bluetooth_started = false;

// ------------------------------------------------------------------
// Gas / smoke sensor threshold
// ------------------------------------------------------------------
const float smoke_alert_threshold = 1.8;   // v_gas <= 1.2V means smoke detected

// ------------------------------------------------------------------
// LDR light thresholds (voltage-based)
// ------------------------------------------------------------------
const float ldr_bright_threshold = 1.3;    // above this = BRIGHT
const float ldr_dark_threshold   = 1.1;    // below this = DARK

// ------------------------------------------------------------------
// Sensor debug print timing
// ------------------------------------------------------------------
unsigned long last_sensor_print  = 0;
int sensor_print_interval        = 1000;

// ------------------------------------------------------------------
// Binary Bluetooth protocol packet
// ------------------------------------------------------------------
struct __attribute__((packed)) SensorPacket {
  int32_t temp;
  uint8_t gas;
  uint8_t is_baby_awake;
};

// ------------------------------------------------------------------
// Previous-state trackers for proactive BT alerts
// ------------------------------------------------------------------
bool prev_baby_awake = false;
bool prev_gas        = false;
bool prev_temp_alert = false;
int  high_temp_alert_threshold = 40;

// ------------------------------------------------------------------
// Buzzer auto-off for 'I' command
// ------------------------------------------------------------------
unsigned long buzzer_alert_until = 0;
const unsigned long BUZZER_ALERT_MS = 2000;

// ------------------------------------------------------------------
// Text line buffers (non-blocking) — one per port
// ------------------------------------------------------------------
String bt_line_buffer    = "";
String usb_line_buffer   = "";
const unsigned int MAX_LINE = 64;

// ------------------------------------------------------------------
// Function prototypes
// ------------------------------------------------------------------
int  check_temp();
bool check_gas();
void check_sensors_and_serial();
void check_pir_baby_awake();
void print_sensor_status();
void fan_led_function(int temp);
void alarm(unsigned long current_time);
void handle_servo(unsigned long current_time);

char read_char_from(Stream &port);
char read_char_usb();
char read_char_bt();
void handle_char_command(char order, Stream &port);
void handle_text_command(String command, Stream &replyPort);
void poll_stream(Stream &port, String &lineBuffer);

void handle_usb_serial();
void handle_bluetooth();
void bluetooth_tx();

void buzzer_short_alert();
void reply_both(const String &msg);

// ==================================================================
// SETUP
// ==================================================================
void setup() {
  Serial.begin(115200);

  dht.begin();

  if (!SerialBT.begin("SmartNursery")) {
    bluetooth_started = false;
    Serial.println("BT Start Failed!");
  } else {
    bluetooth_started = true;
    Serial.println("Bluetooth Ready. Pair with SmartNursery");
  }

  pinMode(dht_pin,        INPUT);
  pinMode(gas_sensor_pin, INPUT);
  pinMode(ldr_sensor_pin, INPUT);
  pinMode(pir_sensor_pin, INPUT);

  pinMode(red_led,   OUTPUT);
  pinMode(green_led, OUTPUT);
  pinMode(blue_led,  OUTPUT);
  pinMode(room_led,  OUTPUT);

  pinMode(fan_in1, OUTPUT);
  pinMode(fan_in2, OUTPUT);

  // Servo FIRST, so it gets a clean LEDC timer/channel
  bedServo.setPeriodHertz(50);
  bedServo.attach(bed_servo_pin, 500, 2400);
  bedServo.write(0);

  // Buzzer after the servo, using ledcAttach
  ledcAttach(buzzer, BUZZER_FREQ, BUZZER_RESOLUTION);
  ledcWrite(buzzer, BUZZER_DUTY_OFF);

  start_time = millis();
}

// ==================================================================
// LOOP
// ==================================================================
void loop() {
  unsigned long current_time = millis();

  if (current_time - start_time >= (unsigned long)time_for_temp_check) {
    start_time = current_time;
    current_temperature = check_temp();
  }

  check_gas();
  check_pir_baby_awake();
  fan_led_function(current_temperature);
  alarm(current_time);
  handle_servo(current_time);

  // --- Handle both input ports ---
  handle_usb_serial();
  handle_bluetooth();

  // --- Periodic status print ---
  if (current_time - last_sensor_print >= (unsigned long)sensor_print_interval) {
    last_sensor_print = current_time;
    print_sensor_status();
  }

  bluetooth_tx();

  delay(50);
}

// ==================================================================
// TEMPERATURE
// ==================================================================
int check_temp() {
  float temp = dht.readTemperature();
  if (isnan(temp)) {
    return current_temperature;
  }
  return (int)roundf(temp);
}

// ==================================================================
// GAS / SMOKE
// ==================================================================
bool check_gas() {
  int   vr        = analogRead(gas_sensor_pin);
  float vr_analog = vr * (3.3f / 4095.0f);
  float v_gas     = 3.3f - vr_analog;

  static bool last_gas_state = false;

  if (v_gas <= smoke_alert_threshold) {
    gas_detected = true;
    if (!last_gas_state) {
      Serial.println("GAS_ALERT: Smoke detected!");
      last_gas_state = true;
    }
    return true;
  } else {
    gas_detected = false;
    if (last_gas_state) {
      Serial.println("GAS_CLEAR: Air is normal.");
      last_gas_state = false;
    }
    return false;
  }
}

// ==================================================================
// PIR BABY-AWAKE DETECTION + ROOM LIGHT
// ==================================================================
void check_pir_baby_awake() {
  static unsigned long pir_high_start = 0;
  static unsigned long pir_low_start  = 0;
  static bool          pir_was_high   = false;
  static int           pir_high_count = 0;

  int           pirVal = digitalRead(pir_sensor_pin);
  unsigned long now    = millis();

  if (pirVal == HIGH) {
    pir_low_start = 0;

    if (!pir_was_high) {
      pir_high_start = now;
      pir_was_high   = true;
    } else if (now - pir_high_start >= 10000) {
      pir_high_count++;
      pir_was_high   = false;
      pir_high_start = 0;
      Serial.print("PIR HIGH 10s count: ");
      Serial.println(pir_high_count);

      if (pir_high_count >= 2) {
        baby_awake     = true;
        pir_high_count = 0;
        Serial.println("BABY_AWAKE: PIR HIGH for 10s x2 detected!");
      }
    }
  } else {
    pir_was_high   = false;
    pir_high_start = 0;

    if (pir_low_start == 0) {
      pir_low_start = now;
    } else if (now - pir_low_start >= 6000) {
      if (pir_high_count != 0 || baby_awake) {
        Serial.println("BABY_SLEEP: No motion for 6s, count reset.");
      }
      pir_high_count = 0;
      baby_awake     = false;
      pir_low_start  = 0;
    }
  }

  int   ldrVal      = analogRead(ldr_sensor_pin);
  float ldrVoltage  = ldrVal * (3.3f / 4095.0f);
  bool  is_room_dark = (ldrVoltage < ldr_dark_threshold);

  if (is_room_dark && (baby_awake || laptop_cry_detected)) {
    digitalWrite(room_led, HIGH);
  } else {
    digitalWrite(room_led, LOW);
  }
}

// ==================================================================
// SENSOR STATUS PRINT
// ==================================================================
void print_sensor_status() {
  int   ldrVal     = analogRead(ldr_sensor_pin);
  float ldrVoltage = ldrVal * (3.3f / 4095.0f);
  int   gasRaw     = analogRead(gas_sensor_pin);
  float gasVoltage = gasRaw * (3.3f / 4095.0f);
  float v_gas      = 3.3f - gasVoltage;
  int   pirVal     = digitalRead(pir_sensor_pin);

  Serial.println("---------- Sensor Status ----------");

  Serial.print("Bluetooth: ");
  Serial.println(bluetooth_started ? "STARTED" : "NOT STARTED");

  Serial.print("Temperature: ");
  Serial.print(current_temperature);
  Serial.println(" C");

  Serial.print("Gas/Smoke -> raw: ");
  Serial.print(gasRaw);
  Serial.print(" | v_gas: ");
  Serial.print(v_gas, 3);
  Serial.print(" V | Detected: ");
  Serial.println(gas_detected ? "YES" : "no");

  Serial.print("Light (LDR) -> raw: ");
  Serial.print(ldrVal);
  Serial.print(" | voltage: ");
  Serial.print(ldrVoltage, 3);
  Serial.print(" V | ");
  if (ldrVoltage > ldr_bright_threshold) {
    Serial.println("BRIGHT");
  } else if (ldrVoltage < ldr_dark_threshold) {
    Serial.println("DARK");
  } else {
    Serial.println("DIM");
  }

  Serial.print("PIR -> ");
  Serial.println(pirVal == HIGH ? "motion right now" : "no motion right now");

  Serial.print("Baby awake: ");
  Serial.println(baby_awake ? "YES" : "no");

  Serial.print("Cry detected (from laptop): ");
  Serial.println(laptop_cry_detected ? "YES" : "no");

  Serial.println("------------------------------------");
}

// ==================================================================
// TEXT COMMAND HANDLER (shared by USB + BT)
// ==================================================================
void handle_text_command(String command, Stream &replyPort) {
  if (command.length() == 0) return;

  if (command == "CRY_DETECTED" || command == "SERVO_START") {
    laptop_cry_detected = true;
    Serial.println("Command Received: CRY_DETECTED");
    replyPort.println("Command Received: CRY_DETECTED");
  }
  else if (command == "CRY_ENDED" || command == "SERVO_STOP") {
    laptop_cry_detected = false;
    buzzer_alert_until  = 0;
    ledcWrite(buzzer, BUZZER_DUTY_OFF);
    Serial.println("Command Received: CRY_ENDED");
    replyPort.println("Command Received: CRY_ENDED");
  }
  else {
    replyPort.print("Unknown command: ");
    replyPort.println(command);
  }
}

// ==================================================================
// SERVO CONTROL
// ==================================================================
void handle_servo(unsigned long current_time) {
  static unsigned long last_servo_update = 0;
  static int servo_angle     = 0;
  static int servo_direction = 1;

  if (laptop_cry_detected) {
    if (current_time - last_servo_update >= 300) {
      last_servo_update = current_time;
      servo_angle += (servo_direction * 45);

      if (servo_angle >= 90) {
        servo_angle     = 90;
        servo_direction = -1;
      } else if (servo_angle <= 0) {
        servo_angle     = 0;
        servo_direction = 1;
      }
      bedServo.write(servo_angle);
    }
  } else {
    bedServo.write(0);
    servo_angle     = 0;
    servo_direction = 1;
  }
}

// ==================================================================
// FAN + LED LOGIC
// ==================================================================
void fan_led_function(int temp) {
  if (gas_detected == false) {
    if (temp < 25) {
      digitalWrite(blue_led,  HIGH);
      digitalWrite(green_led, LOW);
      digitalWrite(red_led,   LOW);
      digitalWrite(fan_in1,   LOW);
      digitalWrite(fan_in2,   LOW);
    } else if (temp >= 25 && temp < 30) {
      digitalWrite(blue_led,  LOW);
      digitalWrite(green_led, HIGH);
      digitalWrite(red_led,   LOW);
      digitalWrite(fan_in1,   HIGH);
      digitalWrite(fan_in2,   LOW);
    } else if (temp >= 30) {
      digitalWrite(blue_led,  LOW);
      digitalWrite(green_led, LOW);
      digitalWrite(red_led,   HIGH);
      digitalWrite(fan_in1,   HIGH);
      digitalWrite(fan_in2,   LOW);
    }
  } else {
    digitalWrite(blue_led,  HIGH);
    digitalWrite(green_led, HIGH);
    digitalWrite(red_led,   HIGH);
    digitalWrite(fan_in1,   LOW);
    digitalWrite(fan_in2,   HIGH);
  }
}

// ==================================================================
// BUZZER ALARM
// ==================================================================
void alarm(unsigned long current_time) {
  if (buzzer_alert_until != 0) {
    if (current_time < buzzer_alert_until) {
      ledcWrite(buzzer, BUZZER_DUTY_ON);
      return;
    } else {
      buzzer_alert_until = 0;
      ledcWrite(buzzer, BUZZER_DUTY_OFF);
    }
  }

  unsigned long time_for_buzzer = 300;
  unsigned long time_for_pause  = 300;

  static bool          buzzer_state     = false;
  static unsigned long last_change_time = 0;

  if (!gas_detected) {
    ledcWrite(buzzer, BUZZER_DUTY_OFF);
    buzzer_state = false;
    return;
  }

  unsigned long buzzer_threshold = buzzer_state ? time_for_buzzer : time_for_pause;

  if (current_time - last_change_time >= buzzer_threshold) {
    last_change_time = current_time;
    buzzer_state     = !buzzer_state;

    if (buzzer_state) {
      ledcWrite(buzzer, BUZZER_DUTY_ON);
    } else {
      ledcWrite(buzzer, BUZZER_DUTY_OFF);
    }
  }
}

// ==================================================================
// HELPERS
// ==================================================================
void buzzer_short_alert() {
  buzzer_alert_until = millis() + BUZZER_ALERT_MS;
  ledcWrite(buzzer, BUZZER_DUTY_ON);
}

void reply_both(const String &msg) {
  Serial.println(msg);
  if (SerialBT.hasClient()) {
    SerialBT.println(msg);
  }
}

// ==================================================================
// UNIVERSAL CHARACTER READER — same logic for USB & BT
// ------------------------------------------------------------------
// Reads one of the recognized single-char commands from the stream.
// Returns '\0' if nothing valid is available.
// ==================================================================
char read_char_from(Stream &port) {
  if (!port.available()) return '\0';

  char next = port.peek();
  if (next == 'T' || next == 'G' || next == 'B' || next == 'A' ||
      next == 'I' || next == 'C' || next == 'S') {

    char order = (char)port.read();

    Serial.print("[RX] Received char: '");
    Serial.print(order);
    Serial.println("'");

    // swallow optional CR/LF after a single-char command
    if (port.available() && port.peek() == '\r') port.read();
    if (port.available() && port.peek() == '\n') port.read();

    return order;
  }
  return '\0';
}

// ==================================================================
// UNIVERSAL COMMAND HANDLER — same for USB & BT
// ==================================================================
void handle_char_command(char order, Stream &port) {
  switch (order) {

    case 'T': {
      int32_t t = (int32_t)current_temperature;
      port.write((uint8_t*)&t, sizeof(t));
      break;
    }

    case 'G': {
      uint8_t g = gas_detected ? 1 : 0;
      port.write(&g, sizeof(g));
      break;
    }

    case 'B': {
      uint8_t b = baby_awake ? 1 : 0;
      port.write(&b, sizeof(b));
      break;
    }

    case 'A': {
      SensorPacket packet;
      packet.temp          = (int32_t)current_temperature;
      packet.gas           = gas_detected ? 1 : 0;
      packet.is_baby_awake = baby_awake ? 1 : 0;
      port.write((uint8_t*)&packet, sizeof(packet));
      break;
    }

    case 'I': {
      // CRY DETECTED: servo + buzzer
      laptop_cry_detected = true;
      reply_both("[RX] 'I' -> CRY DETECTED (servo + buzzer)");
      buzzer_short_alert();
      break;
    }

    case 'C': {
      // SERVO ONLY: no buzzer
      laptop_cry_detected = true;
      reply_both("[RX] 'C' -> SERVO ONLY (no buzzer)");
      break;
    }

    case 'S': {
      // STOP: servo off + buzzer off + cry_detected = false
      laptop_cry_detected = false;
      buzzer_alert_until  = 0;
      ledcWrite(buzzer, BUZZER_DUTY_OFF);
      reply_both("[RX] 'S' -> STOP (servo off, buzzer off)");
      break;
    }

    default:
      Serial.print("Unknown order: ");
      Serial.println(order);
      break;
  }
}

// ==================================================================
// UNIVERSAL STREAM POLLER — reads chars and text lines
// ==================================================================
void poll_stream(Stream &port, String &lineBuffer) {
  // 1) Try a single-char command first
  char order = read_char_from(port);
  if (order != '\0') {
    handle_char_command(order, port);
    return;
  }

  // 2) Non-blocking multi-char line accumulator
  while (port.available()) {
    char c = (char)port.read();

    if (c == '\n') {
      lineBuffer.trim();
      if (lineBuffer.length() > 0) {
        handle_text_command(lineBuffer, port);
      }
      lineBuffer = "";
    } else if (c != '\r') {
      lineBuffer += c;
      if (lineBuffer.length() > MAX_LINE) {
        lineBuffer = "";   // overflow guard
      }
    }
  }
}

// ==================================================================
// USB SERIAL HANDLER
// ==================================================================
void handle_usb_serial() {
  poll_stream(Serial, usb_line_buffer);
}

// ==================================================================
// BLUETOOTH HANDLER
// ==================================================================
void handle_bluetooth() {
  poll_stream(SerialBT, bt_line_buffer);
}

// ==================================================================
// BLUETOOTH — TX NOTIFICATIONS
// ==================================================================
void bluetooth_tx() {
  if (!SerialBT.hasClient()) {
    prev_baby_awake = baby_awake;
    prev_gas        = gas_detected;
    prev_temp_alert = current_temperature > high_temp_alert_threshold;
    return;
  }

  if (baby_awake && !prev_baby_awake) {
    SerialBT.println("Baby is awake and light is on");
  }
  if (gas_detected && !prev_gas) {
    SerialBT.println("Dangerous gas detected");
  }
  bool temp_alert = current_temperature > high_temp_alert_threshold;
  if (temp_alert && !prev_temp_alert) {
    SerialBT.println("Temperature is too high");
  }

  prev_baby_awake = baby_awake;
  prev_gas        = gas_detected;
  prev_temp_alert = temp_alert;
}