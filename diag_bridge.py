#!/usr/bin/env python3
"""
Arduino Nano Bridge Diagnostic
================================
Diagnoses why the Arduino Nano TTL bridge can't communicate with XY6020.

This script:
1. Opens COM port WITHOUT resetting Arduino (DTR=False)
2. Reads Arduino boot messages at 9600 (startup baud)
3. Waits for auto-detection to complete
4. Then tries Modbus communication through the bridge
5. Also tries resetting the Arduino and reading messages

Usage:
    python diag_bridge.py COM9
"""

import sys
import time
import struct
import serial
import serial.tools.list_ports

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM9"


def calc_crc16(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc


def build_read_request(slave, register, count=1):
    frame = struct.pack('>BBH H', slave, 0x03, register, count)
    crc = calc_crc16(frame)
    frame += struct.pack('<H', crc)
    return frame


def try_modbus_read(ser, label=""):
    """Send Modbus read MODEL request and check response."""
    ser.reset_input_buffer()
    request = build_read_request(1, 0x0016, 1)  # Read MODEL register
    print(f"    TX: {request.hex(' ')}")
    ser.write(request)
    ser.flush()
    time.sleep(0.5)

    n = ser.in_waiting
    if n > 0:
        response = ser.read(n)
        print(f"    RX [{n} bytes]: {response.hex(' ')}")

        # Check if it's a valid Modbus response
        if len(response) >= 7 and response[1] == 0x03 and response[2] == 0x02:
            value = struct.unpack('>H', response[3:5])[0]
            rx_crc = struct.unpack('<H', response[5:7])[0]
            calc = calc_crc16(response[:5])
            if rx_crc == calc:
                print(f"    ✓ MODEL = 0x{value:04X}  (CRC OK)")
                return True
            else:
                print(f"    ✗ CRC mismatch (rx=0x{rx_crc:04X}, calc=0x{calc:04X})")
        else:
            # Try to decode as text (Arduino debug messages)
            try:
                text = response.decode('ascii', errors='replace').strip()
                if text:
                    print(f"    Text: {text}")
            except:
                pass
    else:
        print(f"    ✗ No response")
    return False


print("=" * 60)
print("  Arduino Nano Bridge Diagnostic")
print("=" * 60)
print()

# ── Show port info ──
for p in serial.tools.list_ports.comports():
    if p.device == PORT:
        print(f"  Port:   {p.device}")
        print(f"  Desc:   {p.description}")
        print(f"  HWID:   {p.hwid}")
        print(f"  VID:    0x{p.vid:04X}" if p.vid else "  VID:    N/A")
        print(f"  PID:    0x{p.pid:04X}" if p.pid else "  PID:    N/A")
        break
print()

# ══════════════════════════════════════════════════════════════
# TEST 1: Open WITHOUT DTR reset, read at 9600 (Arduino startup)
# ══════════════════════════════════════════════════════════════
print("─" * 60)
print("[Test 1] Open port WITHOUT reset (DTR=False), read at 9600")
print("─" * 60)
try:
    ser = serial.Serial(
        port=PORT, baudrate=9600,
        bytesize=8, parity=serial.PARITY_NONE, stopbits=1,
        timeout=1.0, dsrdtr=False, rtscts=False,
    )
    ser.dtr = False
    ser.rts = False
    time.sleep(0.3)

    # Read any pending data (Arduino might have sent boot messages)
    n = ser.in_waiting
    if n > 0:
        data = ser.read(n)
        try:
            text = data.decode('ascii', errors='replace')
            print(f"  Pending data [{n} bytes]: {text}")
        except:
            print(f"  Pending data [{n} bytes]: {data.hex(' ')}")
    else:
        print("  No pending data")

    # Try Modbus at 9600 (Arduino may have settled on this)
    print("\n  Trying Modbus at 9600 baud (current port setting):")
    try_modbus_read(ser, "9600")

    ser.close()
except Exception as e:
    print(f"  Error: {e}")

print()

# ══════════════════════════════════════════════════════════════
# TEST 2: Reset Arduino (DTR toggle), then read boot messages
# ══════════════════════════════════════════════════════════════
print("─" * 60)
print("[Test 2] Reset Arduino (DTR toggle), read boot messages")
print("─" * 60)
try:
    ser = serial.Serial(
        port=PORT, baudrate=9600,
        bytesize=8, parity=serial.PARITY_NONE, stopbits=1,
        timeout=2.0, dsrdtr=False, rtscts=False,
    )

    # Reset Arduino via DTR
    print("  Toggling DTR to reset Arduino...")
    ser.dtr = True
    time.sleep(0.1)
    ser.dtr = False
    time.sleep(0.1)

    # Read boot messages for 8 seconds (Arduino auto-detect takes time)
    print("  Waiting for Arduino boot messages (8 seconds)...")
    print()
    start = time.time()
    all_data = b""
    while time.time() - start < 8.0:
        n = ser.in_waiting
        if n > 0:
            chunk = ser.read(n)
            all_data += chunk
            try:
                text = chunk.decode('ascii', errors='replace')
                for line in text.split('\n'):
                    line = line.strip()
                    if line:
                        elapsed = time.time() - start
                        print(f"  [{elapsed:.1f}s] {line}")
            except:
                print(f"  [raw] {chunk.hex(' ')}")
        time.sleep(0.1)

    if not all_data:
        print("  ⚠ No boot messages received!")
        print("  Possible causes:")
        print("    - Arduino sketch not uploaded correctly")
        print("    - Wrong COM port (not the Arduino)")
        print("    - Arduino not powered")

    # Now try Modbus (Arduino should be in bridge mode)
    print()
    print("  Trying Modbus after Arduino boot:")
    found = False
    for baud in [9600, 19200, 57600, 115200]:
        ser.baudrate = baud
        time.sleep(0.1)
        print(f"\n  At {baud} baud:")
        if try_modbus_read(ser, str(baud)):
            found = True
            print(f"\n  ✓ SUCCESS at {baud} baud!")
            break

    if not found:
        print("\n  ✗ No Modbus response after Arduino boot")

    ser.close()
except Exception as e:
    print(f"  Error: {e}")

print()

# ══════════════════════════════════════════════════════════════
# TEST 3: Direct raw serial test (bypass Modbus, just echo)
# ══════════════════════════════════════════════════════════════
print("─" * 60)
print("[Test 3] Direct loopback test (send bytes, check echo)")
print("─" * 60)
try:
    ser = serial.Serial(
        port=PORT, baudrate=9600,
        bytesize=8, parity=serial.PARITY_NONE, stopbits=1,
        timeout=1.0, dsrdtr=False, rtscts=False,
    )
    ser.dtr = False
    ser.rts = False
    time.sleep(0.5)
    ser.reset_input_buffer()

    # Send a known byte pattern
    test_data = bytes([0xAA, 0x55, 0x01, 0x02, 0x03])
    print(f"  TX: {test_data.hex(' ')}")
    ser.write(test_data)
    ser.flush()
    time.sleep(0.5)

    n = ser.in_waiting
    if n > 0:
        response = ser.read(n)
        print(f"  RX [{n} bytes]: {response.hex(' ')}")
        try:
            text = response.decode('ascii', errors='replace').strip()
            if text:
                print(f"  Text: {text}")
        except:
            pass
    else:
        print("  No response (Arduino is forwarding to XY6020, not echoing back)")
        print("  This is NORMAL if XY6020 doesn't respond to these bytes")

    ser.close()
except Exception as e:
    print(f"  Error: {e}")

print()
print("=" * 60)
print("  Diagnostic Complete")
print("=" * 60)
print()
print("  If no boot messages in Test 2:")
print("    → Check that the sketch was UPLOADED to this Arduino")
print("    → Verify this is the correct COM port for Arduino Nano")
print()
print("  If boot messages but no Modbus response:")
print("    → Check XY6020 is POWERED ON")
print("    → Check wiring: Arduino D11 ← XY6020 TX")
print("    →                Arduino D10 → XY6020 RX")
print("    →                GND ↔ GND")
print("    → Try SWAPPING TX/RX wires")
print()
print("  If the Arduino detects XY6020 at a baud rate,")
print("  your wiring is correct and XY6020 is alive.")
