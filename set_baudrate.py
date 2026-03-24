#!/usr/bin/env python3
"""
XY6020 Baud Rate Reset Tool
============================
Auto-detects the current baud rate of the XY6020 module on a given COM port,
then writes the default baud code (6 = 115200) to register 0x0019.

Usage:
    python set_baudrate.py              # auto-detect port and reset to 115200
    python set_baudrate.py COM7         # specify port
    python set_baudrate.py COM7 9600    # specify port and target baud rate

Per GY21208.docx, the baud rate codes are:
    0=1200, 1=2400, 2=4800, 3=9600, 4=19200, 5=57600, 6=115200
"""

import sys
import time
import struct
import serial
import serial.tools.list_ports

# ── Baud rate code mapping (per GY21208.docx) ──
BAUD_CODE_TO_RATE = {
    0: 1200,
    1: 2400,
    2: 4800,
    3: 9600,
    4: 19200,
    5: 57600,
    6: 115200,
}
BAUD_RATE_TO_CODE = {v: k for k, v in BAUD_CODE_TO_RATE.items()}

# Register addresses
REG_MODEL = 0x0016
REG_BAUDRATE = 0x0019

# Baud rates to try during auto-detection (most common first)
AUTO_BAUD_RATES = [115200, 57600, 38400, 19200, 9600, 4800, 2400, 1200]

DEFAULT_SLAVE = 1


def calc_crc16(data):
    """Calculate Modbus RTU CRC16."""
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
    """Build Modbus function 0x03 read request."""
    frame = struct.pack('>BBH H', slave, 0x03, register, count)
    crc = calc_crc16(frame)
    frame += struct.pack('<H', crc)
    return frame


def build_write_request(slave, register, value):
    """Build Modbus function 0x06 write single register request."""
    frame = struct.pack('>BBH H', slave, 0x06, register, value)
    crc = calc_crc16(frame)
    frame += struct.pack('<H', crc)
    return frame


def try_read_register(ser, slave, register):
    """Try to read a register. Returns value on success or None on failure."""
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    time.sleep(0.05)

    request = build_read_request(slave, register, 1)
    ser.write(request)
    ser.flush()
    time.sleep(0.3)

    n = ser.in_waiting
    if n >= 7:
        response = ser.read(n)
        if response[1] == 0x03 and len(response) >= 7:
            value = struct.unpack('>H', response[3:5])[0]
            rx_crc = struct.unpack('<H', response[5:7])[0]
            calc = calc_crc16(response[:5])
            if rx_crc == calc:
                return value
    return None


def write_register(ser, slave, register, value):
    """Write a single register. Returns True on success."""
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    time.sleep(0.05)

    request = build_write_request(slave, register, value)
    ser.write(request)
    ser.flush()
    time.sleep(0.3)

    n = ser.in_waiting
    if n >= 8:
        response = ser.read(n)
        # Echo back: slave, 0x06, reg_hi, reg_lo, val_hi, val_lo, crc_lo, crc_hi
        if len(response) >= 8 and response[1] == 0x06:
            written_val = struct.unpack('>H', response[4:6])[0]
            return written_val == value
    return False


def open_serial(port, baudrate):
    """Open serial port with safe settings."""
    ser = serial.Serial(
        port=port,
        baudrate=baudrate,
        bytesize=8,
        parity=serial.PARITY_NONE,
        stopbits=1,
        timeout=1.0,
        dsrdtr=False,
        rtscts=False,
    )
    ser.dtr = False
    ser.rts = False
    time.sleep(0.2)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    return ser


def list_ports():
    """List available serial ports."""
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("  No serial ports found!")
        return []
    for p in ports:
        print(f"  {p.device:10s} | {p.description} | {p.hwid}")
    return ports


def auto_detect_baud(port, slave=DEFAULT_SLAVE):
    """Try all baud rates and return the working one, or None."""
    for baud in AUTO_BAUD_RATES:
        print(f"  Trying {baud:>7d} baud ... ", end="", flush=True)
        try:
            ser = open_serial(port, baud)
            # Try reading MODEL register (0x0016) up to 3 times
            for attempt in range(3):
                model = try_read_register(ser, slave, REG_MODEL)
                if model is not None:
                    print(f"✓ Model=0x{model:04X}")
                    ser.close()
                    return baud
                time.sleep(0.1)
            ser.close()
            print("✗ no response")
        except Exception as e:
            print(f"✗ error: {e}")
    return None


def main():
    print("=" * 60)
    print("  XY6020 Baud Rate Reset Tool")
    print("  Per GY21208.docx: code 6 = 115200 (default)")
    print("=" * 60)
    print()

    # Parse arguments
    port = None
    target_baud = 115200

    if len(sys.argv) >= 2:
        port = sys.argv[1]
    if len(sys.argv) >= 3:
        target_baud = int(sys.argv[2])

    target_code = BAUD_RATE_TO_CODE.get(target_baud)
    if target_code is None:
        print(f"  ERROR: {target_baud} is not a valid baud rate.")
        print(f"  Valid rates: {list(BAUD_RATE_TO_CODE.keys())}")
        sys.exit(1)

    print(f"  Target baud rate: {target_baud} (code {target_code})")
    print()

    # List ports
    print("  Available serial ports:")
    ports = list_ports()
    if not ports:
        sys.exit(1)
    print()

    # Auto-select port if not specified
    if port is None:
        if len(ports) == 1:
            port = ports[0].device
            print(f"  Auto-selected port: {port}")
        else:
            print("  Multiple ports found. Please specify port as argument:")
            print(f"    python set_baudrate.py <PORT> [target_baud]")
            sys.exit(1)
    print()

    # Step 1: Auto-detect current baud rate
    print(f"[Step 1] Auto-detecting current baud rate on {port}...")
    current_baud = auto_detect_baud(port)

    if current_baud is None:
        print()
        print("  FAILED: Could not communicate with XY6020 at any baud rate.")
        print("  Check:")
        print("    1. Is the XY6020 powered ON?")
        print("    2. Wiring: TX->RX, RX->TX, GND->GND")
        print("    3. Correct COM port?")
        sys.exit(1)

    print(f"\n  ✓ Device found at {current_baud} baud")
    print()

    # Step 2: Read current baud code from register
    print(f"[Step 2] Reading current baud code register (0x{REG_BAUDRATE:04X})...")
    ser = open_serial(port, current_baud)
    baud_code = try_read_register(ser, DEFAULT_SLAVE, REG_BAUDRATE)

    if baud_code is not None:
        mapped_rate = BAUD_CODE_TO_RATE.get(baud_code, "unknown")
        print(f"  Current baud code: {baud_code} (mapped to {mapped_rate})")
    else:
        print(f"  WARNING: Could not read baud code register, proceeding anyway...")

    # Check if already at target
    if current_baud == target_baud and baud_code == target_code:
        print(f"\n  ✓ Device is already at {target_baud} baud (code {target_code}). No change needed.")
        ser.close()
        sys.exit(0)

    ser.close()
    print()

    # Step 3: Write new baud code
    print(f"[Step 3] Writing baud code {target_code} (= {target_baud}) to register 0x{REG_BAUDRATE:04X}...")
    ser = open_serial(port, current_baud)
    ok = write_register(ser, DEFAULT_SLAVE, REG_BAUDRATE, target_code)
    ser.close()

    if ok:
        print(f"  ✓ Write successful!")
    else:
        print(f"  ✗ Write may have failed, attempting verification anyway...")

    time.sleep(0.5)
    print()

    # Step 4: Verify by reconnecting at new baud rate
    print(f"[Step 4] Verifying: reconnecting at {target_baud} baud...")
    try:
        ser = open_serial(port, target_baud)
        time.sleep(0.3)

        # Read MODEL
        model = try_read_register(ser, DEFAULT_SLAVE, REG_MODEL)
        if model is not None:
            print(f"  ✓ MODEL = 0x{model:04X}")
        else:
            print(f"  ✗ Could not read MODEL at {target_baud}")

        # Read baud code to confirm
        new_code = try_read_register(ser, DEFAULT_SLAVE, REG_BAUDRATE)
        if new_code is not None:
            new_rate = BAUD_CODE_TO_RATE.get(new_code, "unknown")
            print(f"  ✓ Baud code now: {new_code} (= {new_rate})")
        else:
            print(f"  ✗ Could not read baud code at {target_baud}")

        ser.close()

        if model is not None and new_code == target_code:
            print()
            print("=" * 60)
            print(f"  ✅ SUCCESS! XY6020 baud rate changed to {target_baud}")
            print(f"  The device will use this rate on next power cycle too.")
            print("=" * 60)
        else:
            print()
            print("=" * 60)
            print(f"  ⚠ Verification incomplete. Try power-cycling the XY6020")
            print(f"  and re-running this script to confirm.")
            print("=" * 60)

    except Exception as e:
        print(f"  ✗ Verification failed: {e}")
        print(f"  Try power-cycling the XY6020 and re-running this script.")


if __name__ == '__main__':
    main()
