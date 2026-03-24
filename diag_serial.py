"""
XY6020 FTDI Direct Diagnostic
Tests FTDI USB-TTL adapter on COM9 with different DTR/RTS settings.
"""

import serial
import time
import struct

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

def build_read_request(slave_addr, register, count=1):
    frame = struct.pack('>BBHH', slave_addr, 0x03, register, count)
    crc = calc_crc16(frame)
    frame += struct.pack('<H', crc)
    return frame

def test_config(port, baudrate, slave_addr, dtr, rts, label):
    print(f"\n--- Test: {label} ---")
    print(f"    Port={port}, Baud={baudrate}, Slave={slave_addr}, DTR={dtr}, RTS={rts}")
    
    try:
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=8,
            parity=serial.PARITY_NONE,
            stopbits=1,
            timeout=1.5,
            dsrdtr=False,
            rtscts=False,
        )
        # Explicit DTR/RTS control
        ser.dtr = dtr
        ser.rts = rts
        time.sleep(0.3)
        
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        time.sleep(0.1)
        
    except Exception as e:
        print(f"    [ERROR] Cannot open: {e}")
        return False

    # Read MODEL register
    request = build_read_request(slave_addr, 0x0016, 1)
    print(f"    TX: {request.hex(' ')}")
    
    ser.write(request)
    ser.flush()
    time.sleep(0.5)
    
    n = ser.in_waiting
    if n > 0:
        response = ser.read(n)
        print(f"    RX [{len(response)}]: {response.hex(' ')}")
        
        if len(response) >= 7 and response[1] == 0x03:
            value = struct.unpack('>H', response[3:5])[0]
            rx_crc = struct.unpack('<H', response[5:7])[0]
            calc = calc_crc16(response[:5])
            if rx_crc == calc:
                print(f"    >> SUCCESS! Model=0x{value:04X}")
                ser.close()
                return True
            else:
                print(f"    >> CRC mismatch")
        else:
            print(f"    >> Unexpected data")
    else:
        # Try second attempt
        ser.reset_input_buffer()
        time.sleep(0.1)
        request2 = build_read_request(slave_addr, 0x0000, 1)
        ser.write(request2)
        ser.flush()
        time.sleep(0.5)
        n2 = ser.in_waiting
        if n2 > 0:
            response2 = ser.read(n2)
            print(f"    RX attempt2 [{len(response2)}]: {response2.hex(' ')}")
        else:
            print(f"    >> No response")
    
    ser.close()
    return False

def main():
    port = "COM9"
    print("="*60)
    print("  XY6020 FTDI Direct Connection Diagnostic")
    print("="*60)
    print(f"  COM9 is FTDI (VID:PID=0403:6001)")
    print(f"  This is a direct USB-TTL adapter, NOT Arduino Nano")
    print()
    
    # Test matrix: baudrate x slave_addr x DTR/RTS combos
    configs = []
    for baud in [115200, 57600, 38400, 19200, 9600, 4800]:
        for slave in [1]:
            for (dtr, rts) in [(False, False), (True, True)]:
                label = f"baud={baud}, slave={slave}, DTR={dtr}, RTS={rts}"
                configs.append((baud, slave, dtr, rts, label))
    
    found = False
    for baud, slave, dtr, rts, label in configs:
        ok = test_config(port, baud, slave, dtr, rts, label)
        if ok:
            found = True
            print(f"\n{'='*60}")
            print(f"  FOUND WORKING CONFIG: {label}")
            print(f"{'='*60}")
            break
    
    if not found:
        print(f"\n{'='*60}")
        print(f"  NO RESPONSE from XY6020 on COM9")
        print(f"")
        print(f"  CRITICAL: Please check:")
        print(f"    1. Is XY6020 powered ON?")
        print(f"    2. Wiring: FTDI TX -> XY6020 RX, FTDI RX -> XY6020 TX")
        print(f"    3. FTDI GND connected to XY6020 GND?")
        print(f"    4. FTDI voltage level: must be TTL 5V or 3.3V matching XY6020")
        print(f"    5. Try swapping TX/RX wires")
        print(f"{'='*60}")

if __name__ == '__main__':
    main()
