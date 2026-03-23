# XY6020 Serial Controller (PC / Raspberry Pi 5)

A web-based control interface for the **XY6020 Programmable Power Supply** via **Serial TTL (Modbus RTU)**.

This is a PC/Raspberry Pi version of the original ESP8266-based WiFi controller. Instead of running on a Wemos D1 Pro, it runs on your computer or Raspberry Pi 5 and communicates with the XY6020 through a USB-to-TTL serial adapter.

![XY6020](../doc/main.png)

## Features

- 🔌 **Serial Connection Panel** — Select COM port (Windows) or /dev/ttyUSB* (Linux/RPi), configure baud rate and slave address
- 📊 **Real-time Monitoring** — Actual voltage, current, power, and input voltage with 7-segment display
- 🎛️ **Control** — Set target voltage, max current, max power, and toggle output ON/OFF
- 🛡️ **Protection Status** — Shows OVP, OCP, OPP, LVP, OTP and other protection states
- 🌡️ **Temperature** — Internal and external temperature display
- 🌐 **Bilingual UI** — English + Arabic interface with language switch
- ⚙️ **Advanced Settings** — Key Lock, Temperature Unit, Backlight, Sleep, Buzzer, Memory Recall
- ✅ **Output Readback Validation** — ON/OFF writes are verified by reading register `0x0012`
- 💻 **Cross-platform** — Works on Windows (x86/x64) and Raspberry Pi 5 (ARM64)

## Output Control (Important)

The output switch is controlled by Modbus register **`0x0012 (ONOFF)`**:

- Value **`1`**: output enabled
- Value **`0`**: output disabled

If ON/OFF does not change output, check:

- **Key Lock (`0x000F`)** is unlocked (`0`)
- Protection state is not active (OVP/OCP/OTP/etc.)
- Serial link quality (TTL wiring, shared GND, baud settings)

## Requirements

- Python 3.8+
- USB-to-TTL Serial adapter (e.g., CH340, CP2102, FT232)
- XY6020 power supply module

## Quick Start

### Option 1: Using the launcher script (recommended)

```bash
cd pc_controller
python run.py
```

The launcher will automatically:
1. Create a Python virtual environment
2. Install all dependencies
3. Start the web server

### Option 2: Manual setup

```bash
cd pc_controller

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/RPi:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the server
python app.py
```

Then open **http://localhost:5000** in your browser.

## Wiring

### Option A: Direct USB-to-TTL adapter

Connect the USB-to-TTL adapter to the XY6020 TTL interface:

| USB-TTL Adapter | XY6020 TTL Port |
|-----------------|-----------------|
| TX              | RX              |
| RX              | TX              |
| GND             | GND             |
| 5V (optional)   | VCC             |

### Option B: Arduino Nano as USB↔TTL bridge (D10/D11)

You can use an **Arduino Nano (old bootloader)** as a transparent USB↔TTL bridge for XY6020.

1. Upload this sketch:
   - `pc_controller/arduino_nano_ttl_bridge/arduino_nano_ttl_bridge.ino`
2. Wiring after upload:

| Arduino Nano | XY6020 TTL Port | Notes |
|-------------|------------------|-------|
| D11 (TX)    | RX               | Nano TX -> XY RX |
| D10 (RX)    | TX               | Nano RX <- XY TX |
| GND         | GND              | Common ground required |
| 5V (optional) | VCC            | Optional power line |

3. On PC app, choose Nano serial port (example: `COM9` on Windows).

> **Important:** Keep TX/RX crossed (TX->RX, RX->TX).  
> **Note:** XY6020 TTL usually works with 3.3V or 5V levels.

## Arduino Nano Bridge Upload Notes

- Arduino IDE board: **Arduino Nano**
- Processor (for old Nano): **ATmega328P (Old Bootloader)** if needed
- Baud in bridge sketch: **115200**
- The sketch is binary passthrough (safe for Modbus RTU frames)

## Configuration

Default settings:
- **Baud Rate:** 115200
- **Data Format:** 8N1 (8 data bits, no parity, 1 stop bit)
- **Slave Address:** 1
- **Web Server Port:** 5000

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Main web interface |
| GET | `/api/ports` | List available serial ports |
| POST | `/api/connect` | Connect to XY6020 |
| POST | `/api/disconnect` | Disconnect from XY6020 |
| GET | `/api/status` | Connection status |
| GET | `/api/model-info` | UI model notes and capability metadata |
| GET | `/api/settings` | Read configurable device settings |
| POST | `/api/settings` | Write one or more device settings |
| GET | `/control` | Read all device values |
| POST | `/control?voltage=X` | Set target voltage |
| POST | `/control?current=X` | Set max current |
| POST | `/control?max-power=X` | Set max power |
| POST | `/control?output=1` | Enable output |
| POST | `/control?output=0` | Disable output |

## Raspberry Pi 5 Notes

- Use `/dev/ttyUSB0` for USB-to-TTL adapters
- Use `/dev/ttyAMA0` or `/dev/serial0` for GPIO UART
- You may need to add your user to the `dialout` group:
  ```bash
  sudo usermod -a -G dialout $USER
  ```
- For headless access, the server binds to `0.0.0.0:5000` so you can access it from any device on the network

## Project Structure

```
pc_controller/
├── app.py                  # Flask web server
├── xy6020_driver.py        # XY6020 Modbus RTU driver
├── run.py                  # Auto-setup launcher script
├── requirements.txt        # Python dependencies
├── README.md               # This file
└── static/
    ├── index.html          # Main web interface
    ├── style.css           # Styles
    ├── logic.js            # Frontend logic
    └── segment-display.js  # 7-segment display renderer
```

## Dependencies

- `minimalmodbus==2.1.1` — Modbus RTU communication
- `pyserial>=3.5` — Serial port access
- `Flask>=3.0.0` — Web server

## License

Same as the original project.
