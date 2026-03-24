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

def read_registers(ser, slave, start_reg, count):
    """Read multiple registers and return list of values or None."""
    request = build_read_request(slave, start_reg, count)
    ser.reset_input_buffer()
    ser.write(request)
    ser.flush()
    time.sleep(0.3)
    
    n = ser.in_waiting
    if n < 5:
        return None
    
    response = ser.read(n)
    # Validate: slave, function code 0x03, byte count
    if len(response) < 3 + count * 2 + 2:
        return None
    if response[0] != slave or response[1] != 0x03:
        return None
    
    byte_count = response[2]
    if byte_count != count * 2:
        return None
    
    # Extract register values
    values = []
    for i in range(count):
        val = struct.unpack('>H', response[3 + i*2 : 5 + i*2])[0]
        values.append(val)
    
    # Verify CRC
    payload_len = 3 + byte_count
    if len(response) >= payload_len + 2:
        rx_crc = struct.unpack('<H', response[payload_len:payload_len+2])[0]
        calc = calc_crc16(response[:payload_len])
        if rx_crc != calc:
            print(f"  WARNING: CRC mismatch (rx=0x{rx_crc:04X}, calc=0x{calc:04X})")
    
    return values

PORT = "COM7"
SLAVE = 1

# Test both baud rates
for BAUD in [38400, 115200]:
    print(f"\n{'='*60}")
    print(f"  Testing COM7 at {BAUD} baud")
    print(f"{'='*60}")
    
    try:
        ser = serial.Serial(
            port=PORT,
            baudrate=BAUD,
            bytesize=8,
            parity=serial.PARITY_NONE,
            stopbits=1,
            timeout=1.0,
            dsrdtr=False,
            rtscts=False,
        )
        ser.dtr = False
        ser.rts = False
        time.sleep(0.3)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        time.sleep(0.1)
    except Exception as e:
        print(f"  Cannot open port: {e}")
        continue

    # Read registers 0x0000 to 0x0005 (V-SET, I-SET, VOUT, IOUT, POWER, UIN)
    print(f"\n  --- Reading main registers (0x0000-0x0005) ---")
    vals = read_registers(ser, SLAVE, 0x0000, 6)
    if vals:
        print(f"  Target Voltage (V-SET):  {vals[0]/100.0:.2f} V")
        print(f"  Target Current (I-SET):  {vals[1]/100.0:.2f} A")
        print(f"  Actual Voltage (VOUT):   {vals[2]/100.0:.2f} V")
        print(f"  Actual Current (IOUT):   {vals[3]/100.0:.2f} A")
        print(f"  Actual Power (POWER):    {vals[4]/10.0:.1f} W")
        print(f"  Input Voltage (UIN):     {vals[5]/100.0:.2f} V")
        print(f"  Raw values: {[hex(v) for v in vals]}")
    else:
        print(f"  No valid response for main registers")

    # Read registers 0x000D to 0x0012 (TEMP, LOCK, PROTECT, CVCC, OUTPUT)
    print(f"\n  --- Reading status registers (0x000D-0x0012) ---")
    vals2 = read_registers(ser, SLAVE, 0x000D, 6)
    if vals2:
        print(f"  Internal Temp:    {vals2[0]} C")
        print(f"  External Temp:    {vals2[1]} C")
        print(f"  Key Lock:         {vals2[2]}")
        print(f"  Protection:       {vals2[3]}")
        print(f"  CV/CC:            {'CC' if vals2[4] else 'CV'}")
        print(f"  Output ON/OFF:    {'ON' if vals2[5] else 'OFF'}")
        print(f"  Raw values: {[hex(v) for v in vals2]}")
    else:
        print(f"  No valid response for status registers")

    # Read MODEL and VERSION
    print(f"\n  --- Reading device info (0x0016-0x0019) ---")
    vals3 = read_registers(ser, SLAVE, 0x0016, 4)
    if vals3:
        print(f"  Model:            0x{vals3[0]:04X} ({vals3[0]})")
        print(f"  Firmware Version: {vals3[1]}")
        print(f"  Slave Address:    {vals3[2]}")
        print(f"  Baud Code:        {vals3[3]}")
        baud_map = {0:1200, 1:2400, 2:4800, 3:9600, 4:19200, 5:57600, 6:115200}
        actual_baud = baud_map.get(vals3[3], 'unknown')
        print(f"  Actual Baud Rate: {actual_baud}")
    else:
        print(f"  No valid response for device info")

    success = vals is not None or vals2 is not None or vals3 is not None
    if success:
        print(f"\n  >>> BAUD {BAUD} WORKS! <<<")
    else:
        print(f"\n  >>> BAUD {BAUD} - NO RESPONSE <<<")

    ser.close()
    time.sleep(0.5)

print(f"\n{'='*60}")
print(f"  Done.")
print(f"{'='*60}")
