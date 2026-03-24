import serial.tools.list_ports

ports = list(serial.tools.list_ports.comports())
print(f"Found {len(ports)} ports:")
for p in ports:
    print(f"  {p.device}: {p.description}")
    print(f"    HWID: {p.hwid}")
    print(f"    VID:PID = {p.vid}:{p.pid}")
    print()

# Quick test: try to open COM7 and send a Modbus read
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

import serial
import time

test_ports = ['COM7']
for port in test_ports:
    print(f"=== Testing {port} at 115200 ===")
    for dtr_val in [False, True]:
        for rts_val in [False, True]:
            label = f"DTR={dtr_val}, RTS={rts_val}"
            try:
                ser = serial.Serial(
                    port=port,
                    baudrate=115200,
                    bytesize=8,
                    parity=serial.PARITY_NONE,
                    stopbits=1,
                    timeout=1.0,
                    dsrdtr=False,
                    rtscts=False,
                )
                ser.dtr = dtr_val
                ser.rts = rts_val
                time.sleep(0.3)
                ser.reset_input_buffer()
                ser.reset_output_buffer()
                time.sleep(0.1)

                # Read MODEL register (0x0016)
                request = build_read_request(1, 0x0016, 1)
                print(f"  [{label}] TX: {request.hex(' ')}")
                ser.write(request)
                ser.flush()
                time.sleep(0.5)

                n = ser.in_waiting
                if n > 0:
                    response = ser.read(n)
                    print(f"  [{label}] RX [{n}]: {response.hex(' ')}")
                    if len(response) >= 7 and response[1] == 0x03:
                        value = struct.unpack('>H', response[3:5])[0]
                        print(f"  [{label}] >>> MODEL = 0x{value:04X} - SUCCESS!")
                else:
                    print(f"  [{label}] No response")

                ser.close()
            except Exception as e:
                print(f"  [{label}] ERROR: {e}")
    print()
