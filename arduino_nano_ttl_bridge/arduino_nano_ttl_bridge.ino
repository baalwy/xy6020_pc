#include <SoftwareSerial.h>

// Arduino Nano USB <-> TTL Bridge for XY6020 (Modbus RTU)
// D11 = RX (connect to XY6020 TX)
// D10 = TX (connect to XY6020 RX)
// USB Serial = PC side (COM port)
//
// Baud: 115200, 8N1 on both sides

static const uint32_t PC_BAUD   = 9600;
static const uint32_t XY_BAUD   = 9600;
static const uint8_t  XY_RX_PIN = 11; // Nano receives from XY TX
static const uint8_t  XY_TX_PIN = 10; // Nano transmits to XY RX

SoftwareSerial xySerial(XY_RX_PIN, XY_TX_PIN);

void setup() {
  Serial.begin(PC_BAUD);
  xySerial.begin(XY_BAUD);

  // Keep loop tight and transparent for binary frames (Modbus RTU).
  // No parsing, no delays, no line-ending conversions.
}

void loop() {
  // PC (USB serial) -> XY6020 TTL
  while (Serial.available() > 0) {
    xySerial.write((uint8_t)Serial.read());
  }

  // XY6020 TTL -> PC (USB serial)
  while (xySerial.available() > 0) {
    Serial.write((uint8_t)xySerial.read());
  }
}
