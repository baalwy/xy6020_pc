"""
XY6020 Modbus RTU Driver
Compatible with Windows (COM ports) and Raspberry Pi 5 (/dev/ttyUSB*, /dev/ttyAMA*, /dev/serial*)
Uses minimalmodbus for Modbus RTU communication over Serial TTL.
"""

import minimalmodbus
import serial
import serial.tools.list_ports
import threading
import time


class XY6020Register:
    """XY6020 Modbus Holding Register addresses."""
    TARGET_VOLTAGE = 0x0000       # V-SET: Voltage setting (÷100 = V)
    MAX_CURRENT = 0x0001          # I-SET: Current setting (÷100 = A)
    ACTUAL_VOLTAGE = 0x0002       # VOUT: Output voltage (÷100 = V)
    ACTUAL_CURRENT = 0x0003       # IOUT: Output current (÷100 = A)
    ACTUAL_POWER = 0x0004         # POWER: Output power (÷10 = W) -- per original code ÷10
    INPUT_VOLTAGE = 0x0005        # UIN: Input voltage (÷100 = V)
    OUTPUT_CHARGE_LOW = 0x0006    # AH-LOW: Output mAh low 16 bits
    OUTPUT_CHARGE_HIGH = 0x0007   # AH-HIGH: Output mAh high 16 bits
    OUTPUT_ENERGY_LOW = 0x0008    # WH-LOW: Output mWh low 16 bits
    OUTPUT_ENERGY_HIGH = 0x0009   # WH-HIGH: Output mWh high 16 bits
    ON_TIME_HOURS = 0x000A        # OUT_H: Open time hours
    ON_TIME_MINUTES = 0x000B      # OUT_M: Open time minutes
    ON_TIME_SECONDS = 0x000C      # OUT_S: Open time seconds
    INTERNAL_TEMP = 0x000D        # T_IN: Internal temperature (÷1)
    EXTERNAL_TEMP = 0x000E        # T_EX: External temperature (÷1)
    KEY_LOCK = 0x000F             # LOCK: Key lock (0=unlocked, 1=locked)
    PROTECTION_STATUS = 0x0010    # PROTECT: Protection status (0-10)
    CVCC_STATE = 0x0011           # CVCC: 0=CV, 1=CC
    OUTPUT_STATE = 0x0012         # ONOFF: Switch output (0=off, 1=on)
    TEMP_UNIT = 0x0013            # F-C: Temperature unit
    BACKLIGHT = 0x0014            # B-LED: Backlight brightness (0-5)
    SLEEP_TIME = 0x0015           # SLEEP: Off screen time (minutes)
    MODEL = 0x0016                # MODEL: Product number
    FIRMWARE_VERSION = 0x0017     # VERSION: Firmware version
    SLAVE_ADDRESS = 0x0018        # SLAVE-ADD: Slave address
    BAUDRATE = 0x0019             # BAUDRATE: Baud rate code (6=115200)
    INTERNAL_TEMP_OFFSET = 0x001A # T-IN-OFFSET
    EXTERNAL_TEMP_OFFSET = 0x001B # T-EX-OFFSET
    BUZZER = 0x001C               # BUZZER: Buzzer switch
    EXTRACT_MEMORY = 0x001D       # EXTRACT-M: Quick recall data sets (0-9)

    # Total number of main registers to read (0x00 to 0x12 inclusive = 19 registers)
    MAIN_REG_COUNT = 19


class XY6020Driver:
    """
    Driver for XY6020 programmable power supply via Modbus RTU.
    Thread-safe for concurrent read/write from Flask routes.
    """

    def __init__(self):
        self._instrument = None
        self._lock = threading.Lock()
        self._connected = False
        self._port = None
        self._slave_address = 1
        self._max_power = 1200.0  # Default max power in watts
        self._read_error_count = 0
        self._max_read_errors = 5

        # Cached register values
        self._registers = [0] * 32
        self._last_read_ok = False

    BAUD_CODE_TO_RATE = {
        0: 1200,
        1: 2400,
        2: 4800,
        3: 9600,
        4: 19200,
        5: 38400,
        6: 57600,
        7: 115200,
    }

    @staticmethod
    def list_serial_ports():
        """
        List available serial ports.
        Works on both Windows (COM*) and Linux/Raspberry Pi (/dev/tty*).
        Returns list of dicts with 'port', 'description', 'hwid'.
        """
        ports = []
        for port_info in serial.tools.list_ports.comports():
            ports.append({
                'port': port_info.device,
                'description': port_info.description,
                'hwid': port_info.hwid
            })
        return ports

    def connect(self, port, slave_address=1, baudrate=115200):
        """
        Connect to XY6020 via the specified serial port.

        Args:
            port: Serial port name (e.g., 'COM9' on Windows, '/dev/ttyUSB0' on RPi)
            slave_address: Modbus slave address (default: 1)
            baudrate: Baud rate (default: 115200)

        Returns:
            dict with 'success' and 'message' keys
        """
        with self._lock:
            if self._connected:
                self.disconnect_internal()

            try:
                self._instrument = minimalmodbus.Instrument(port, slave_address)
                self._instrument.serial.baudrate = baudrate
                self._instrument.serial.bytesize = 8
                self._instrument.serial.parity = serial.PARITY_NONE
                self._instrument.serial.stopbits = 1
                self._instrument.serial.timeout = 1.0
                self._instrument.mode = minimalmodbus.MODE_RTU
                self._instrument.clear_buffers_before_each_transaction = True

                # Arduino Nano auto-resets on serial open; wait for bridge to boot.
                time.sleep(2.0)

                # Try reading model register multiple times (SoftwareSerial
                # at 115200 may lose a frame or two initially).
                last_error = None
                for _ in range(6):
                    try:
                        model = self._instrument.read_register(XY6020Register.MODEL)
                        self._connected = True
                        self._port = port
                        self._slave_address = slave_address
                        self._read_error_count = 0
                        return {
                            'success': True,
                            'message': f'Connected to XY6020 on {port} (Model: 0x{model:04X})'
                        }
                    except Exception as e:
                        last_error = e
                        time.sleep(0.2)

                self._instrument.serial.close()
                self._instrument = None
                return {
                    'success': False,
                    'message': f'Device not responding on {port}: {str(last_error)}'
                }

            except Exception as e:
                self._instrument = None
                return {
                    'success': False,
                    'message': f'Failed to open port {port}: {str(e)}'
                }

    def disconnect_internal(self):
        """Internal disconnect without lock (called from within locked context)."""
        if self._instrument is not None:
            try:
                self._instrument.serial.close()
            except Exception:
                pass
            self._instrument = None
        self._connected = False
        self._port = None
        self._last_read_ok = False
        self._read_error_count = 0
        self._registers = [0] * 32

    def disconnect(self):
        """Disconnect from XY6020."""
        with self._lock:
            self.disconnect_internal()
            return {'success': True, 'message': 'Disconnected'}

    def is_connected(self):
        """Check if currently connected."""
        return self._connected

    def get_port(self):
        """Get current port name."""
        return self._port

    def _read_regs_retry(self, start, count, retries=3):
        """Read registers with retry for SoftwareSerial reliability."""
        for attempt in range(retries):
            try:
                return self._instrument.read_registers(start, count)
            except Exception:
                time.sleep(0.05)
        return None

    def _read_reg_retry(self, address, retries=3):
        """Read single holding register with retry."""
        for attempt in range(retries):
            try:
                return self._instrument.read_register(address)
            except Exception:
                time.sleep(0.05)
        return None

    def _write_retry(self, register, value, label='', retries=3):
        """Write a single register with retry."""
        for attempt in range(retries):
            try:
                self._instrument.write_register(register, value)
                return True
            except Exception as e:
                if attempt == retries - 1:
                    print(f"[XY6020] Write {label} error after {retries} retries: {e}")
                time.sleep(0.05)
        return False

    @staticmethod
    def _normalize_temperature(raw):
        """Normalize temperature value from device to celsius-like value."""
        if raw is None:
            return None
        val = int(raw)
        # Some firmwares return deci-degrees (e.g., 267 = 26.7 C)
        if abs(val) > 150:
            return val / 10.0
        return float(val)

    def read_all(self):
        """
        Read main registers from XY6020 in small chunks with retry.
        SoftwareSerial at 115200 is unreliable for large frames,
        so we split into smaller reads for much better success rate.
        Returns dict with parsed values or None on failure.
        """
        if not self._connected or self._instrument is None:
            return None

        with self._lock:
            # Read in two small chunks for reliability
            r1 = self._read_regs_retry(0x0000, 6)   # V-SET thru UIN
            r2 = self._read_regs_retry(0x000D, 6)   # T_IN thru OUTPUT_STATE

            if r1 is not None and r2 is not None:
                # Build full register cache
                self._registers[0:6] = r1
                self._registers[0x0D:0x0D+6] = r2
                self._last_read_ok = True
                self._read_error_count = 0

                return {
                    'voltage': r1[XY6020Register.ACTUAL_VOLTAGE] / 100.0,
                    'current': r1[XY6020Register.ACTUAL_CURRENT] / 100.0,
                    'power': r1[XY6020Register.ACTUAL_POWER] / 10.0,
                    'output': int(r2[XY6020Register.OUTPUT_STATE - 0x0D]),
                    'tvoltage': r1[XY6020Register.TARGET_VOLTAGE] / 100.0,
                    'tcurrent': r1[XY6020Register.MAX_CURRENT] / 100.0,
                    'tpower': self._max_power,
                    'ivoltage': r1[XY6020Register.INPUT_VOLTAGE] / 100.0,
                    'connected': True,
                    'protection': int(r2[XY6020Register.PROTECTION_STATUS - 0x0D]),
                    'cvcc': int(r2[XY6020Register.CVCC_STATE - 0x0D]),
                    'internal_temp': int(r2[XY6020Register.INTERNAL_TEMP - 0x0D]),
                    'external_temp': int(r2[XY6020Register.EXTERNAL_TEMP - 0x0D]),
                    'internal_temp_c': self._normalize_temperature(r2[XY6020Register.INTERNAL_TEMP - 0x0D]),
                    'external_temp_c': self._normalize_temperature(r2[XY6020Register.EXTERNAL_TEMP - 0x0D]),
                    'key_lock': int(r2[XY6020Register.KEY_LOCK - 0x0D]),
                }

            # Read failed
            self._last_read_ok = False
            self._read_error_count += 1
            print(f"[XY6020] Read error ({self._read_error_count}/{self._max_read_errors})")

            if self._read_error_count < self._max_read_errors:
                return None

            self._connected = False
            return None

    def get_cached_data(self):
        """Return last cached register values without touching serial port."""
        r = self._registers
        return {
            'voltage': r[XY6020Register.ACTUAL_VOLTAGE] / 100.0,
            'current': r[XY6020Register.ACTUAL_CURRENT] / 100.0,
            'power': r[XY6020Register.ACTUAL_POWER] / 10.0,
            'output': int(r[XY6020Register.OUTPUT_STATE]),
            'tvoltage': r[XY6020Register.TARGET_VOLTAGE] / 100.0,
            'tcurrent': r[XY6020Register.MAX_CURRENT] / 100.0,
            'tpower': self._max_power,
            'ivoltage': r[XY6020Register.INPUT_VOLTAGE] / 100.0,
            'connected': self._connected,
            'protection': int(r[XY6020Register.PROTECTION_STATUS]),
            'cvcc': int(r[XY6020Register.CVCC_STATE]),
            'internal_temp': int(r[XY6020Register.INTERNAL_TEMP]),
            'external_temp': int(r[XY6020Register.EXTERNAL_TEMP]),
            'internal_temp_c': self._normalize_temperature(r[XY6020Register.INTERNAL_TEMP]),
            'external_temp_c': self._normalize_temperature(r[XY6020Register.EXTERNAL_TEMP]),
            'key_lock': int(r[XY6020Register.KEY_LOCK]),
        }

    def read_device_settings(self):
        """Read configurable XY6020 settings registers."""
        if not self._connected or self._instrument is None:
            return None

        with self._lock:
            vals = {}
            keys = [
                ('key_lock', XY6020Register.KEY_LOCK),
                ('temp_unit', XY6020Register.TEMP_UNIT),
                ('backlight', XY6020Register.BACKLIGHT),
                ('sleep_time', XY6020Register.SLEEP_TIME),
                ('model', XY6020Register.MODEL),
                ('firmware_version', XY6020Register.FIRMWARE_VERSION),
                ('slave_address', XY6020Register.SLAVE_ADDRESS),
                ('baud_code', XY6020Register.BAUDRATE),
                ('internal_temp_offset', XY6020Register.INTERNAL_TEMP_OFFSET),
                ('external_temp_offset', XY6020Register.EXTERNAL_TEMP_OFFSET),
                ('buzzer', XY6020Register.BUZZER),
                ('extract_memory', XY6020Register.EXTRACT_MEMORY),
            ]

            for key, reg in keys:
                val = self._read_reg_retry(reg)
                if val is None:
                    return None
                vals[key] = int(val)

            vals['baudrate'] = self.BAUD_CODE_TO_RATE.get(vals['baud_code'])
            vals['output_state'] = int(self._registers[XY6020Register.OUTPUT_STATE])
            return vals

    def set_setting_value(self, key, value):
        """Set one configurable setting by key name."""
        if not self._connected or self._instrument is None:
            return False

        with self._lock:
            try:
                if key == 'temp_unit':
                    v = 1 if int(value) else 0
                    return self._write_retry(XY6020Register.TEMP_UNIT, v, 'temp_unit')
                if key == 'key_lock':
                    v = 1 if int(value) else 0
                    return self._write_retry(XY6020Register.KEY_LOCK, v, 'key_lock')
                if key == 'backlight':
                    v = max(0, min(5, int(value)))
                    return self._write_retry(XY6020Register.BACKLIGHT, v, 'backlight')
                if key == 'sleep_time':
                    v = max(0, min(120, int(value)))
                    return self._write_retry(XY6020Register.SLEEP_TIME, v, 'sleep_time')
                if key == 'slave_address':
                    v = max(1, min(247, int(value)))
                    ok = self._write_retry(XY6020Register.SLAVE_ADDRESS, v, 'slave_address')
                    if ok:
                        self._slave_address = v
                    return ok
                if key == 'baud_code':
                    v = max(0, min(7, int(value)))
                    return self._write_retry(XY6020Register.BAUDRATE, v, 'baud_code')
                if key == 'buzzer':
                    v = 1 if int(value) else 0
                    return self._write_retry(XY6020Register.BUZZER, v, 'buzzer')
                if key == 'extract_memory':
                    v = max(0, min(9, int(value)))
                    return self._write_retry(XY6020Register.EXTRACT_MEMORY, v, 'extract_memory')
                if key == 'internal_temp_offset':
                    v = int(value) & 0xFFFF
                    return self._write_retry(XY6020Register.INTERNAL_TEMP_OFFSET, v, 'internal_temp_offset')
                if key == 'external_temp_offset':
                    v = int(value) & 0xFFFF
                    return self._write_retry(XY6020Register.EXTERNAL_TEMP_OFFSET, v, 'external_temp_offset')
                return False
            except Exception:
                return False

    def set_target_voltage(self, voltage):
        """
        Set target output voltage.
        Args:
            voltage: Voltage in volts (0-60V)
        Returns:
            True on success, False on failure
        """
        if not self._connected or self._instrument is None:
            return False

        voltage = max(0.0, min(60.0, voltage))
        value = int(voltage * 100)

        with self._lock:
            return self._write_retry(XY6020Register.TARGET_VOLTAGE, value, 'voltage')

    def set_max_current(self, current):
        """
        Set maximum output current.
        Args:
            current: Current in amps (0-20A)
        Returns:
            True on success, False on failure
        """
        if not self._connected or self._instrument is None:
            return False

        current = max(0.0, min(20.0, current))
        value = int(current * 100)

        with self._lock:
            return self._write_retry(XY6020Register.MAX_CURRENT, value, 'current')

    def set_output_enabled(self, enabled):
        """
        Enable or disable output.
        Args:
            enabled: True to enable, False to disable
        Returns:
            True on success, False on failure
        """
        if not self._connected or self._instrument is None:
            return False

        value = 1 if enabled else 0

        with self._lock:
            return self._write_retry(XY6020Register.OUTPUT_STATE, value, 'output')

    def get_output_state(self):
        """Read output switch register (0x0012). Returns 0/1 or None on failure."""
        if not self._connected or self._instrument is None:
            return None
        with self._lock:
            val = self._read_reg_retry(XY6020Register.OUTPUT_STATE)
            if val is None:
                return None
            return 1 if int(val) else 0

    def set_max_power(self, power):
        """
        Set maximum power limit (software-side).
        Calculates and sets the appropriate current limit based on target voltage.
        Args:
            power: Power in watts
        Returns:
            True on success, False on failure
        """
        if power < 0:
            return False

        self._max_power = power

        # If power is being reduced, adjust current accordingly
        if self._connected:
            target_v = self._registers[XY6020Register.TARGET_VOLTAGE] / 100.0
            if target_v > 0:
                target_current = min(power / target_v, 20.0)
                return self.set_max_current(target_current)

        return True

    def get_connection_info(self):
        """Get current connection information."""
        return {
            'connected': self._connected,
            'port': self._port,
            'slave_address': self._slave_address,
            'last_read_ok': self._last_read_ok
        }
