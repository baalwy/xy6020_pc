/*
 * Arduino Nano — Transparent TTL Bridge for XY6020 (Modbus RTU)
 * ==============================================================
 *
 * PURPOSE:
 *   Acts as a USB-to-TTL bridge between a PC and the XY6020 power supply.
 *   The PC talks to the Nano's Hardware Serial (USB), and the Nano relays
 *   everything to/from the XY6020 via SoftwareSerial.
 *
 * AUTO-DETECTION:
 *   On startup the sketch tries each supported baud rate on SoftwareSerial
 *   (9600 → 19200 → 57600 → 115200) and sends a Modbus "read MODEL register"
 *   request.  When the XY6020 answers, the sketch locks both sides to that
 *   baud rate and enters transparent bridge mode.
 *
 *   If no response is found, falls back to 9600 (most reliable).
 *
 * WIRING (Arduino Nano):
 *   D11 (SoftSerial RX)  ←  XY6020 TX
 *   D10 (SoftSerial TX)  →  XY6020 RX
 *   GND                  ←→ XY6020 GND
 *   USB                  ←→ PC
 *
 *   IMPORTANT: Do NOT connect 5V/VIN unless you know what you're doing.
 *   The XY6020 communication port is TTL-level (5V or 3.3V).
 *
 * LED FEEDBACK (built-in LED, pin 13):
 *   - Fast blink during auto-detection
 *   - Solid ON when XY6020 found and bridge is active
 *   - Slow blink if no XY6020 detected (fallback mode)
 *
 * SOFTWARESERIAL RELIABILITY NOTES:
 *   On ATmega328P @ 16 MHz, SoftwareSerial reliability by baud rate:
 *     9600  — Very reliable ✓
 *     19200 — Reliable ✓
 *     57600 — Borderline, usually works
 *     115200— Unreliable ✗ (frequent frame errors)
 *   If XY6020 is set to 115200, consider using a direct FTDI/CP2102 adapter
 *   instead of Arduino Nano, or change XY6020 to 9600/19200 first.
 *
 * BAUD RATE CODES (per GY21208.docx, register 0x0019):
 *   0=1200, 1=2400, 2=4800, 3=9600, 4=19200, 5=57600, 6=115200
 */

#include <SoftwareSerial.h>

// ── Pin Configuration ──
static const uint8_t  XY_RX_PIN = 11;   // Nano receives from XY6020 TX
static const uint8_t  XY_TX_PIN = 10;   // Nano transmits to XY6020 RX
static const uint8_t  LED_PIN   = 13;   // Built-in LED

// ── Baud rates to try (order: most reliable first) ──
static const uint32_t BAUD_LIST[]   = { 9600, 19200, 57600, 115200 };
static const uint8_t  BAUD_COUNT    = sizeof(BAUD_LIST) / sizeof(BAUD_LIST[0]);
static const uint32_t FALLBACK_BAUD = 9600;

// ── Modbus read MODEL request: slave=1, func=0x03, reg=0x0016, count=1 ──
// Pre-computed CRC for speed
static const uint8_t READ_MODEL_REQ[] = {0x01, 0x03, 0x00, 0x16, 0x00, 0x01, 0x65, 0x0E};
static const uint8_t MODEL_RESP_LEN   = 7;  // slave(1)+func(1)+bytes(1)+data(2)+crc(2)

SoftwareSerial xySerial(XY_RX_PIN, XY_TX_PIN);

uint32_t activeBaud = 0;

// ── CRC16 for Modbus RTU ──
uint16_t calcCRC16(const uint8_t* data, uint8_t len) {
    uint16_t crc = 0xFFFF;
    for (uint8_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (uint8_t j = 0; j < 8; j++) {
            if (crc & 0x0001) {
                crc >>= 1;
                crc ^= 0xA001;
            } else {
                crc >>= 1;
            }
        }
    }
    return crc;
}

// ── Try one baud rate: returns true if XY6020 responds ──
bool tryBaud(uint32_t baud) {
    xySerial.end();
    xySerial.begin(baud);
    delay(50);

    // Flush any stale data
    while (xySerial.available()) xySerial.read();

    // Send the read MODEL request
    for (uint8_t i = 0; i < sizeof(READ_MODEL_REQ); i++) {
        xySerial.write(READ_MODEL_REQ[i]);
    }
    xySerial.flush();

    // Wait for response (timeout: 500ms)
    uint32_t start = millis();
    uint8_t  buf[16];
    uint8_t  idx = 0;

    while (millis() - start < 500) {
        if (xySerial.available()) {
            if (idx < sizeof(buf)) {
                buf[idx++] = xySerial.read();
            } else {
                xySerial.read(); // discard overflow
            }
        }
    }

    // Validate response: at least 7 bytes, slave=0x01, func=0x03, bytecount=0x02
    if (idx >= MODEL_RESP_LEN &&
        buf[0] == 0x01 &&
        buf[1] == 0x03 &&
        buf[2] == 0x02) {
        // Verify CRC
        uint16_t rxCrc = (uint16_t)buf[5] | ((uint16_t)buf[6] << 8);
        uint16_t calcCrc = calcCRC16(buf, 5);
        if (rxCrc == calcCrc) {
            return true;
        }
    }
    return false;
}

// ── Auto-detect XY6020 baud rate ──
uint32_t autoDetectBaud() {
    for (uint8_t attempt = 0; attempt < 2; attempt++) {
        for (uint8_t i = 0; i < BAUD_COUNT; i++) {
            // Blink LED fast during detection
            digitalWrite(LED_PIN, !digitalRead(LED_PIN));

            // Send status to PC (at current PC baud, for debug)
            // PC may or may not see this depending on its baud setting
            Serial.print(F("[BRIDGE] Trying "));
            Serial.print(BAUD_LIST[i]);
            Serial.println(F(" baud..."));

            if (tryBaud(BAUD_LIST[i])) {
                Serial.print(F("[BRIDGE] XY6020 found at "));
                Serial.print(BAUD_LIST[i]);
                Serial.println(F(" baud!"));
                return BAUD_LIST[i];
            }
            delay(100);
        }
    }
    return 0; // Not found
}

void setup() {
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, LOW);

    // Start PC serial at a known rate for initial diagnostics
    Serial.begin(9600);
    xySerial.begin(9600);

    delay(200);

    Serial.println();
    Serial.println(F("========================================"));
    Serial.println(F("  Arduino Nano TTL Bridge for XY6020"));
    Serial.println(F("  Auto-detecting XY6020 baud rate..."));
    Serial.println(F("========================================"));

    // ── Auto-detect ──
    activeBaud = autoDetectBaud();

    if (activeBaud == 0) {
        // No response — fall back to 9600
        activeBaud = FALLBACK_BAUD;
        Serial.println(F("[BRIDGE] No XY6020 detected!"));
        Serial.print(F("[BRIDGE] Fallback to "));
        Serial.println(activeBaud);

        // Slow blink to indicate no device found
        for (uint8_t i = 0; i < 6; i++) {
            digitalWrite(LED_PIN, !digitalRead(LED_PIN));
            delay(500);
        }
    }

    // ── Set both sides to the detected/fallback baud rate ──
    Serial.print(F("[BRIDGE] Setting both sides to "));
    Serial.print(activeBaud);
    Serial.println(F(" baud"));
    Serial.println(F("[BRIDGE] Entering transparent bridge mode..."));
    Serial.println(F("========================================"));
    delay(100);

    // Restart both serial ports at the active baud rate
    Serial.end();
    delay(50);
    Serial.begin(activeBaud);

    xySerial.end();
    delay(50);
    xySerial.begin(activeBaud);

    // Clear buffers
    delay(100);
    while (Serial.available()) Serial.read();
    while (xySerial.available()) xySerial.read();

    // LED solid ON = bridge active
    digitalWrite(LED_PIN, HIGH);
}

void loop() {
    // ── PC (USB Hardware Serial) → XY6020 (SoftwareSerial) ──
    while (Serial.available() > 0) {
        xySerial.write((uint8_t)Serial.read());
    }

    // ── XY6020 (SoftwareSerial) → PC (USB Hardware Serial) ──
    while (xySerial.available() > 0) {
        Serial.write((uint8_t)xySerial.read());
    }
}
