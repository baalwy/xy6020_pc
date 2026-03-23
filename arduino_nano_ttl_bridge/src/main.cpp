#include <Arduino.h>
#include <SoftwareSerial.h>

// Arduino Nano USB <-> TTL Bridge for XY6020 (Modbus RTU)
// D11 = RX (connect to XY6020 TX)
// D10 = TX (connect to XY6020 RX)
// USB Serial = PC side  (115200 baud)
// SoftSerial = XY6020 side (115200 baud)

static const uint32_t PC_BAUD   = 115200;
static const uint32_t XY_BAUD   = 115200;
static const uint8_t  XY_RX_PIN = 11;
static const uint8_t  XY_TX_PIN = 10;

SoftwareSerial xySerial(XY_RX_PIN, XY_TX_PIN);

void setup() {
  Serial.begin(PC_BAUD);
  xySerial.begin(XY_BAUD);
}

void loop() {
  // PC -> XY6020
  while (Serial.available() > 0) {
    xySerial.write((uint8_t)Serial.read());
  }
  // XY6020 -> PC
  while (xySerial.available() > 0) {
    Serial.write((uint8_t)xySerial.read());
  }
}
