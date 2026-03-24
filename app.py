"""
XY6020 PC/Raspberry Pi Serial Controller - Flask Web Server
Compatible with Windows and Raspberry Pi 5.

Usage:
    python app.py
    Then open http://localhost:5000 in your browser.
"""

import os
import sys
import platform
from flask import Flask, jsonify, request, send_from_directory
from xy6020_driver import XY6020Driver

# Get the absolute path of the directory where this script lives
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')

# Initialize Flask app
app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='/static')

# Initialize XY6020 driver
xy = XY6020Driver()


# ─────────────────────────────────────────────
# Static file routes
# ─────────────────────────────────────────────

@app.route('/')
def index():
    """Serve the main page."""
    return send_from_directory(STATIC_DIR, 'index.html')


@app.route('/style.css')
def style_css():
    """Serve CSS."""
    return send_from_directory(STATIC_DIR, 'style.css')


@app.route('/logic.js')
def logic_js():
    """Serve main logic JS."""
    return send_from_directory(STATIC_DIR, 'logic.js')


@app.route('/segment-display.js')
def segment_display_js():
    """Serve segment display JS."""
    return send_from_directory(STATIC_DIR, 'segment-display.js')


# ─────────────────────────────────────────────
# Serial Port API
# ─────────────────────────────────────────────

@app.route('/api/ports', methods=['GET'])
def get_ports():
    """List available serial ports."""
    ports = XY6020Driver.list_serial_ports()
    return jsonify({
        'ports': ports,
        'platform': platform.system(),
        'machine': platform.machine()
    })


@app.route('/api/connect', methods=['POST'])
def connect():
    """
    Connect to XY6020 via serial port.
    JSON body: { "port": "COM3", "slave_address": 1, "baudrate": 115200 }
    """
    data = request.get_json(silent=True)
    if not data or 'port' not in data:
        return jsonify({'success': False, 'message': 'Missing "port" parameter'}), 400

    port = data['port']
    slave_address = data.get('slave_address', 1)
    baudrate = data.get('baudrate', 0)  # Default to auto-detect

    # Support 'auto' string or 0 for auto-detection
    if isinstance(baudrate, str) and baudrate.lower() == 'auto':
        baudrate = 0
    else:
        try:
            baudrate = int(baudrate)
        except (ValueError, TypeError):
            baudrate = 0

    result = xy.connect(port, slave_address, baudrate)
    status_code = 200 if result['success'] else 500
    return jsonify(result), status_code


@app.route('/api/disconnect', methods=['POST'])
def disconnect():
    """Disconnect from XY6020."""
    result = xy.disconnect()
    return jsonify(result)


@app.route('/api/status', methods=['GET'])
def connection_status():
    """Get current connection status."""
    info = xy.get_connection_info()
    return jsonify(info)


@app.route('/api/model-info', methods=['GET'])
def model_info():
    """Return built-in model capability info for XY6020/XY6020L UI."""
    info = {
        'name': 'XY6020 / XY6020L',
        'protocol': 'Modbus RTU',
        'notes_en': [
            'ON/OFF controls output switch (register 0x0012).',
            'You can fully enable/disable output current from the UI.',
            'Read values can have transient frame errors on SoftwareSerial at 115200.',
            'This app uses retries and cached values to keep UI stable.',
        ],
        'notes_ar': [
            'زر ON/OFF يتحكم بمفتاح الخرج (السجل 0x0012).',
            'يمكنك تشغيل/إيقاف تيار الخرج بالكامل من الواجهة.',
            'قد تظهر أخطاء إطارات لحظية مع SoftwareSerial على 115200.',
            'التطبيق يستخدم إعادة المحاولة وقيم مخزنة لثبات الواجهة.',
        ],
        'registers': {
            'read_main': ['0x0000..0x0012'],
            'settings': ['0x0013..0x001D'],
        }
    }
    return jsonify(info)


@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Read current configurable settings from XY6020."""
    if not xy.is_connected():
        return jsonify({'success': False, 'message': 'Not connected'}), 400

    data = xy.read_device_settings()
    if data is None:
        return jsonify({'success': False, 'message': 'Failed to read settings'}), 500

    return jsonify({'success': True, 'settings': data})


@app.route('/api/settings', methods=['POST'])
def set_settings():
    """Set one or more configurable settings."""
    if not xy.is_connected():
        return jsonify({'success': False, 'message': 'Not connected'}), 400

    payload = request.get_json(silent=True) or {}
    allowed = {
        'temp_unit', 'key_lock', 'backlight', 'sleep_time', 'slave_address',
        'baud_code', 'buzzer', 'extract_memory',
        'internal_temp_offset', 'external_temp_offset'
    }
    updates = {k: v for k, v in payload.items() if k in allowed}
    if not updates:
        return jsonify({'success': False, 'message': 'No valid setting keys'}), 400

    results = {}
    all_ok = True
    for key, value in updates.items():
        ok = xy.set_setting_value(key, value)
        results[key] = bool(ok)
        all_ok = all_ok and ok

    code = 200 if all_ok else 500
    return jsonify({'success': all_ok, 'results': results}), code


# ─────────────────────────────────────────────
# XY6020 Control API (compatible with original firmware API)
# ─────────────────────────────────────────────

@app.route('/control', methods=['GET'])
def control_get():
    """
    Read all values from XY6020.
    Returns JSON with voltage, current, power, output state, etc.
    """
    if not xy.is_connected():
        return jsonify({
            'voltage': 0.0,
            'current': 0.0,
            'power': 0.0,
            'output': 0,
            'tvoltage': 0.0,
            'tcurrent': 0.0,
            'tpower': 0.0,
            'ivoltage': 0.0,
            'connected': False
        })

    data = xy.read_all()
    if data is None:
        # If serial read failed momentarily but driver still considers the
        # link alive, return last cached values to prevent UI false disconnect.
        if xy.is_connected():
            response = jsonify(xy.get_cached_data())
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response

        return jsonify({
            'voltage': 0.0,
            'current': 0.0,
            'power': 0.0,
            'output': 0,
            'tvoltage': 0.0,
            'tcurrent': 0.0,
            'tpower': 0.0,
            'ivoltage': 0.0,
            'connected': False
        })

    # Add CORS header for compatibility
    response = jsonify(data)
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@app.route('/control', methods=['POST'])
def control_post():
    """
    Set XY6020 parameters via query parameters.
    Supported params: voltage, current, max-power, output
    Example: POST /control?voltage=12.5
    Example: POST /control?output=1
    """
    if not xy.is_connected():
        response = jsonify({'status': 'FAIL', 'message': 'Not connected'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response, 400

    success = True

    # Handle voltage setting
    voltage = request.args.get('voltage')
    if voltage is not None:
        try:
            success = xy.set_target_voltage(float(voltage))
        except ValueError:
            success = False

    # Handle current setting
    current = request.args.get('current')
    if current is not None:
        try:
            success = xy.set_max_current(float(current))
        except ValueError:
            success = False

    # Handle max-power setting
    max_power = request.args.get('max-power')
    if max_power is not None:
        try:
            success = xy.set_max_power(float(max_power))
        except ValueError:
            success = False

    # Handle output on/off
    output = request.args.get('output')
    if output is not None:
        try:
            val = float(output)
            requested = 1 if val > 0.01 else 0
            success = xy.set_output_enabled(requested == 1)

            # Verify by readback of register 0x0012.
            if success:
                actual = xy.get_output_state()
                if actual is None:
                    success = False
                elif actual != requested:
                    success = False
        except ValueError:
            success = False

    response_text = 'OK' if success else 'FAIL'
    response = app.response_class(
        response=response_text,
        status=200,
        mimetype='text/html'
    )
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


# ─────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────

if __name__ == '__main__':
    print("=" * 60)
    print("  XY6020 Serial Controller")
    print(f"  Platform: {platform.system()} ({platform.machine()})")
    print(f"  Python: {sys.version}")
    print("=" * 60)
    print()
    print("  Open http://localhost:5000 in your browser")
    print("  Press Ctrl+C to stop the server")
    print()
    print("=" * 60)

    # Use 0.0.0.0 to allow access from other devices on the network
    # (useful for Raspberry Pi headless access)
    app.run(host='0.0.0.0', port=5000, debug=False)
