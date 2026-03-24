import serial
import serial.tools.list_ports
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

def test_port(port, baudrate, slave, dtr, rts):
    try:
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
        ser.dtr = dtr
        ser.rts = rts
        time.sleep(0.2)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        time.sleep(0.05)

        # Read MODEL register (0x0016)
        request = build_read_request(slave, 0x0016, 1)
        ser.write(request)
        ser.flush()
        time.sleep(0.4)

        n = ser.in_waiting
        result = None
        if n > 0:
            response = ser.read(n)
            if len(response) >= 7 and response[1] == 0x03:
                value = struct.unpack('>H', response[3:5])[0]
                result = f"MODEL=0x{value:04X} SUCCESS!"
            else:
                result = f"RX[{n}]: {response.hex(' ')} (unexpected)"
        
        ser.close()
        return result
    except serial.SerialException as e:
        return f"PORT ERROR: {e}"
    except Exception as e:
        return f"ERROR: {e}"

print("=" * 70)
print("  XY6020 Full Port Scan Diagnostic")
print("=" * 70)

# Test all FTDI ports + Arduino Leonardo
test_ports = ['COM4', 'COM7', 'COM9', 'COM3']
baudrates = [115200, 9600, 57600, 38400]
slaves = [1, 2]

for port in test_ports:
    print(f"\n{'='*50}")
    print(f"  Testing {port}")
    print(f"{'='*50}")
    
    found = False
    for baud in baudrates:
        for slave in slaves:
            # Test with DTR=False, RTS=False first (most common for FTDI)
            result = test_port(port, baud, slave, False, False)
            if result and "SUCCESS" in result:
                print(f"  >>> FOUND! baud={baud}, slave={slave}, DTR=F, RTS=F: {result}")
                found = True
                break
            
            # Also try DTR=True, RTS=True
            result2 = test_port(port, baud, slave, True, True)
            if result2 and "SUCCESS" in result2:
                print(f"  >>> FOUND! baud={baud}, slave={slave}, DTR=T, RTS=T: {result2}")
                found = True
                break
            
            # Print non-None results
            if result and "PORT ERROR" in str(result):
                print(f"  baud={baud}, slave={slave}: {result}")
                break
            elif result:
                print(f"  baud={baud}, slave={slave}, DTR=F: {result}")
            if result2:
                print(f"  baud={baud}, slave={slave}, DTR=T: {result2}")
        
        if found:
            break
    
    if not found:
        print(f"  No response on any config for {port}")

print(f"\n{'='*70}")
print("  Scan complete.")
print(f"{'='*70}")
