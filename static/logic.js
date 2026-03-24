/**
 * XY6020 PC/RPi Serial Controller - Frontend Logic
 * Handles serial connection management and device control.
 */

// ─── Global Variables ───
var server_ip = "";
var isConnected = false;
var dataInterval = null;
var currentLang = "en";

// Segment display objects
var displayActVoltage, displayActCurrent, displayActPower, displayInputVoltage;
var displayTargetVoltage, displayTargetCurrent, displayTargetPower;

// Protection status names
var protectionNames = [
    "OK", "OVP", "OCP", "OPP", "LVP", "OAH",
    "OHP", "OTP", "OEP", "OWH", "ICP"
];


// ─── Initialization ───

function init() {
    createSegments();
    loadModelInfo();
    refreshPorts();
    // Check if already connected (e.g., page refresh)
    checkConnectionStatus();
}

function bi(en, ar) {
    return currentLang === "ar" ? ar : en;
}

function setLang(lang) {
    currentLang = (lang === "ar") ? "ar" : "en";
    document.body.dir = currentLang === "ar" ? "rtl" : "ltr";
}


// ─── Serial Port Management ───

function refreshPorts() {
    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function () {
        if (this.readyState == 4 && this.status == 200) {
            var data = JSON.parse(this.responseText);
            var select = document.getElementById("port-select");
            select.innerHTML = "";

            if (data.ports.length === 0) {
                var opt = document.createElement("option");
                opt.value = "";
                opt.textContent = "-- No ports found --";
                select.appendChild(opt);
                document.getElementById("port-description").textContent = "No serial ports detected";
            } else {
                data.ports.forEach(function (p) {
                    var opt = document.createElement("option");
                    opt.value = p.port;
                    opt.textContent = p.port + " - " + p.description;
                    select.appendChild(opt);
                });
                updatePortDescription();
            }

            // Show platform info
            document.getElementById("platform-info").textContent =
                data.platform + " (" + data.machine + ")";
        }
    };
    xhttp.open("GET", server_ip + "/api/ports", true);
    xhttp.send();
}

function updatePortDescription() {
    var select = document.getElementById("port-select");
    var selectedOption = select.options[select.selectedIndex];
    if (selectedOption) {
        document.getElementById("port-description").textContent = selectedOption.textContent;
    }
}

function checkConnectionStatus() {
    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function () {
        if (this.readyState == 4 && this.status == 200) {
            var data = JSON.parse(this.responseText);
            if (data.connected) {
                isConnected = true;
                updateConnectionUI(true, data.port);
                startDataPolling();
            } else {
                isConnected = false;
                updateConnectionUI(false);
            }
        }
    };
    xhttp.open("GET", server_ip + "/api/status", true);
    xhttp.send();
}

function toggleConnection() {
    if (isConnected) {
        disconnectDevice();
    } else {
        connectDevice();
    }
}

function connectDevice() {
    var port = document.getElementById("port-select").value;
    var slaveAddr = parseInt(document.getElementById("slave-address").value) || 1;
    var baudrateVal = document.getElementById("baudrate").value;

    // Support "auto" or numeric baud rate
    var baudrate;
    if (baudrateVal === "auto") {
        baudrate = "auto";
    } else {
        baudrate = parseInt(baudrateVal) || 0;
    }

    if (!port) {
        setStatusMessage(bi("Please select a serial port", "يرجى اختيار منفذ تسلسلي"), "error");
        return;
    }

    var connectMsg = bi("Connecting (auto-detecting baud rate)...", "جارٍ الاتصال (كشف تلقائي للسرعة)...");
    if (baudrate !== "auto" && baudrate > 0) {
        connectMsg = bi("Connecting at " + baudrate + "...", "جارٍ الاتصال على " + baudrate + "...");
    }
    setStatusMessage(connectMsg, "connecting");

    var xhttp = new XMLHttpRequest();
    xhttp.timeout = 30000; // 30s timeout for auto-detect
    xhttp.onreadystatechange = function () {
        if (this.readyState == 4) {
            var data = JSON.parse(this.responseText);
            if (data.success) {
                isConnected = true;
                updateConnectionUI(true, port);
                setStatusMessage(data.message, "success");
                startDataPolling();
                loadSettings();
            } else {
                isConnected = false;
                updateConnectionUI(false);
                setStatusMessage(data.message, "error");
            }
        }
    };
    xhttp.ontimeout = function () {
        setStatusMessage(bi("Connection timed out", "انتهت مهلة الاتصال"), "error");
    };
    xhttp.open("POST", server_ip + "/api/connect", true);
    xhttp.setRequestHeader("Content-Type", "application/json");
    xhttp.send(JSON.stringify({
        port: port,
        slave_address: slaveAddr,
        baudrate: baudrate
    }));
}

function disconnectDevice() {
    stopDataPolling();

    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function () {
        if (this.readyState == 4) {
            isConnected = false;
            updateConnectionUI(false);
            setStatusMessage(bi("Disconnected", "تم قطع الاتصال"), "info");
            resetDisplays();
        }
    };
    xhttp.open("POST", server_ip + "/api/disconnect", true);
    xhttp.send();
}


// ─── UI Updates ───

function updateConnectionUI(connected, portName) {
    var btn = document.getElementById("connect-button");
    var controls = document.getElementById("controls-section");
    var connIndicator = document.getElementById("connection-state");
    var portSelect = document.getElementById("port-select");
    var slaveInput = document.getElementById("slave-address");
    var baudrateInput = document.getElementById("baudrate");
    var refreshBtn = document.getElementById("refresh-ports-btn");

    if (connected) {
        btn.textContent = "⏏ Disconnect | قطع الاتصال";
        btn.classList.add("connected");
        controls.classList.remove("controls-disabled");
        connIndicator.style.display = "inline";
        // Disable connection inputs while connected
        portSelect.disabled = true;
        slaveInput.disabled = true;
        baudrateInput.disabled = true;
        refreshBtn.disabled = true;
    } else {
        btn.textContent = "⚡ Connect | اتصال";
        btn.classList.remove("connected");
        controls.classList.add("controls-disabled");
        connIndicator.style.display = "none";
        // Enable connection inputs
        portSelect.disabled = false;
        slaveInput.disabled = false;
        baudrateInput.disabled = false;
        refreshBtn.disabled = false;
    }
}

function setStatusMessage(message, type) {
    var el = document.getElementById("connection-status");
    el.textContent = message;
    el.className = "connection-status";
    if (type === "success" || type === "info") {
        el.classList.add("status-connected");
    } else if (type === "error") {
        el.classList.add("status-disconnected");
    } else if (type === "connecting") {
        el.classList.add("status-connecting");
    }
}

function resetDisplays() {
    setDisplayValue(displayActVoltage, 0);
    setDisplayValue(displayActCurrent, 0);
    setDisplayValue(displayActPower, 0);
    setDisplayValue(displayInputVoltage, 0);
    setDisplayValue(displayTargetVoltage, 0);
    setDisplayValue(displayTargetCurrent, 0);
    setDisplayValue(displayTargetPower, 0);

    document.getElementById("on-button").classList.remove("my-active-button");
    document.getElementById("off-button").classList.add("my-active-button");

    var infoBar = document.getElementById("info-bar");
    if (infoBar) {
        infoBar.innerHTML = '<span>Protection: --</span><span>Mode: --</span><span>Temp: --</span>';
    }
}


// ─── Data Polling ───

function startDataPolling() {
    stopDataPolling();
    getData(); // Immediate first read
    dataInterval = setInterval(function () {
        getData();
    }, 1500);
}

function stopDataPolling() {
    if (dataInterval) {
        clearInterval(dataInterval);
        dataInterval = null;
    }
}

function getData() {
    var xhttp = new XMLHttpRequest();
    xhttp.timeout = 2000;
    xhttp.onreadystatechange = function () {
        if (this.readyState == 4 && this.status == 200) {
            var data = JSON.parse(this.responseText);

            if (!data.connected) {
                // Connection lost
                isConnected = false;
                updateConnectionUI(false);
                setStatusMessage(bi("Connection lost", "فُقد الاتصال"), "error");
                stopDataPolling();
                resetDisplays();
                return;
            }

            setDisplayValue(displayActVoltage, data.voltage);
            setDisplayValue(displayActCurrent, data.current);
            setDisplayValue(displayActPower, data.power);
            setDisplayValue(displayInputVoltage, data.ivoltage);
            setDisplayValue(displayTargetVoltage, data.tvoltage);
            setDisplayValue(displayTargetCurrent, data.tcurrent);
            setDisplayValue(displayTargetPower, data.tpower);

            // Update ON/OFF buttons
            document.getElementById("on-button").classList.remove("my-active-button");
            document.getElementById("off-button").classList.remove("my-active-button");
            if (data.output) {
                document.getElementById("on-button").classList.add("my-active-button");
            } else {
                document.getElementById("off-button").classList.add("my-active-button");
            }

            // Update connection indicator
            document.getElementById("connection-state").style.display = "inline";

            // Update info bar
            updateInfoBar(data);
        }
    };
    xhttp.ontimeout = function () {
        console.log("Data request timed out");
    };
    xhttp.open("GET", server_ip + "/control", true);
    xhttp.send();
}

function updateInfoBar(data) {
    var infoBar = document.getElementById("info-bar");
    if (!infoBar) return;

    var protStatus = "OK";
    var protClass = "";
    if (data.protection !== undefined && data.protection > 0 && data.protection < protectionNames.length) {
        protStatus = protectionNames[data.protection];
        protClass = ' class="protection-warning"';
    }

    var cvccMode = "CV";
    if (data.cvcc !== undefined && data.cvcc === 1) {
        cvccMode = "CC";
    }

    var tempStr = "--";
    if (data.internal_temp_c !== undefined && data.internal_temp_c !== null) {
        tempStr = data.internal_temp_c.toFixed(1) + "°C";
    } else if (data.internal_temp !== undefined) {
        tempStr = data.internal_temp + "";
    }
    if (data.external_temp_c !== undefined && data.external_temp_c !== null && data.external_temp_c < 500) {
        tempStr += " / " + data.external_temp_c.toFixed(1) + "°C";
    }

    infoBar.innerHTML =
        '<span' + protClass + '>Protection | الحماية: ' + protStatus + '</span>' +
        '<span>Mode | النمط: ' + cvccMode + '</span>' +
        '<span>Temp | الحرارة: ' + tempStr + '</span>';
}


// ─── Control Functions ───

function setOutput(state) {
    if (!isConnected) return;

    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function () {
        if (this.readyState == 4 && this.status == 200) {
            if (this.responseText != "OK") {
                var msg = bi(
                    "Set output failed. Check KEY LOCK and Protection status.",
                    "فشل ضبط حالة الخرج. تحقق من قفل الأزرار KEY LOCK وحالة الحماية."
                );
                alert(msg);
            }
            setTimeout(function () {
                getData();
                loadSettings();
            }, 200);
        } else if (this.readyState == 4) {
            alert(bi("Set output failed", "فشل ضبط الخرج"));
            setTimeout(function () {
                getData();
                loadSettings();
            }, 200);
        }
    };
    xhttp.open("POST", server_ip + "/control?output=" + state, true);
    xhttp.send();
}

function setTargetValue(id) {
    if (!isConnected) return;

    var label = "";
    var param = "";
    if (id == "set-voltage-button") {
        label = bi("target voltage (V)", "جهد الهدف (فولت)");
        param = "voltage";
    } else if (id == "set-current-button") {
        label = bi("max current (A)", "أقصى تيار (أمبير)");
        param = "current";
    } else if (id == "set-power-button") {
        label = bi("max power (W)", "أقصى قدرة (واط)");
        param = "max-power";
    }

    var value = prompt(bi("Please enter ", "أدخل ") + label + ":");
    if (value != null && !isNaN(parseFloat(value))) {
        var xhttp = new XMLHttpRequest();
        xhttp.onreadystatechange = function () {
            if (this.readyState == 4 && this.status == 200) {
                if (this.responseText != "OK") {
                    alert(bi("Set parameter failed!", "فشل ضبط المعلمة"));
                }
            }
            if (this.readyState == 4) {
                setTimeout(function () {
                    getData();
                    loadSettings();
                }, 200);
            }
        };
        value = parseFloat(value);
        xhttp.open("POST", server_ip + "/control?" + param + "=" + value, true);
        xhttp.send();
    }
}

// ─── Segment Display Setup ───

function createSegment(display) {
    display.pattern = "###.##";
    display.displayAngle = 1.5;
    display.digitHeight = 21;
    display.digitWidth = 14;
    display.digitDistance = 3.1;
    display.segmentWidth = 2.9;
    display.segmentDistance = 0.9;
    display.segmentCount = 7;
    display.cornerType = 3;
    display.colorOn = "#f0f0f0";
    display.colorOff = "#3b3b3b";
    display.draw();
    display.setValue('  0.00');
}

function createSegments() {
    // Actual values
    displayActVoltage = new SegmentDisplay("actVoltage");
    createSegment(displayActVoltage);
    displayActVoltage.colorOn = "#a0a0ff";

    displayActCurrent = new SegmentDisplay("actCurrent");
    createSegment(displayActCurrent);
    displayActCurrent.colorOn = "#ffa0a0";
    displayActCurrent.pattern = "##.###";
    displayActCurrent.setValue(" 0.000");

    displayActPower = new SegmentDisplay("actPower");
    createSegment(displayActPower);
    displayActPower.colorOn = "#a0ffa0";
    displayActPower.pattern = "####.###";
    displayActPower.setValue("   0.000");

    displayInputVoltage = new SegmentDisplay("inputVoltage");
    createSegment(displayInputVoltage);
    displayInputVoltage.colorOn = "#ffffa0";
    setDisplayValue(displayInputVoltage, 0);

    // Target values
    displayTargetVoltage = new SegmentDisplay("targetVoltage");
    createSegment(displayTargetVoltage);
    displayTargetCurrent = new SegmentDisplay("targetCurrent");
    createSegment(displayTargetCurrent);
    displayTargetCurrent.pattern = "##.###";
    displayTargetCurrent.setValue(" 0.000");
    displayTargetPower = new SegmentDisplay("targetPower");
    createSegment(displayTargetPower);
    displayTargetPower.pattern = "####.###";
    displayTargetPower.setValue("   0.000");
}

function setDisplayValue(display, value) {
    var pattern_words = display.pattern.split('.');
    var total_len = display.pattern.length;
    var post_len = pattern_words[1].length;
    var value_words = String(value).split('.');
    var post_word = '';
    if (value_words.length == 2) {
        post_word = value_words[1];
    }
    post_word = post_word.padEnd(post_len, '0');
    display.setValue(value_words[0].padStart(total_len - post_len - 1) + '.' + post_word);
}

function loadModelInfo() {
    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function () {
        if (this.readyState == 4 && this.status == 200) {
            var data = JSON.parse(this.responseText);
            var notes = document.getElementById("model-notes");
            if (!notes) return;
            var html = "";
            var list = currentLang === "ar" ? data.notes_ar : data.notes_en;
            for (var i = 0; i < list.length; i++) {
                html += "<div>- " + list[i] + "</div>";
            }
            notes.innerHTML = html;
        }
    };
    xhttp.open("GET", server_ip + "/api/model-info", true);
    xhttp.send();
}

function loadSettings() {
    if (!isConnected) return;
    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function () {
        if (this.readyState == 4 && this.status == 200) {
            var data = JSON.parse(this.responseText);
            if (!data.success) return;
            var s = data.settings;
            if (document.getElementById("set-key-lock")) document.getElementById("set-key-lock").value = String(s.key_lock || 0);
            if (document.getElementById("set-temp-unit")) document.getElementById("set-temp-unit").value = String(s.temp_unit || 0);
            if (document.getElementById("set-backlight")) document.getElementById("set-backlight").value = String(s.backlight || 0);
            if (document.getElementById("set-sleep")) document.getElementById("set-sleep").value = String(s.sleep_time || 0);
            if (document.getElementById("set-buzzer")) document.getElementById("set-buzzer").value = String(s.buzzer || 0);
            if (document.getElementById("set-memory")) document.getElementById("set-memory").value = String(s.extract_memory || 0);
            var status = document.getElementById("settings-status");
            if (status) {
                status.textContent = "Model: 0x" + Number(s.model || 0).toString(16).toUpperCase() +
                    " | FW: " + String(s.firmware_version || 0) +
                    " | BaudCode: " + String(s.baud_code || 0);
            }
        }
    };
    xhttp.open("GET", server_ip + "/api/settings", true);
    xhttp.send();
}

function saveSettings() {
    if (!isConnected) return;
    var payload = {
        key_lock: parseInt(document.getElementById("set-key-lock").value) || 0,
        temp_unit: parseInt(document.getElementById("set-temp-unit").value) || 0,
        backlight: parseInt(document.getElementById("set-backlight").value) || 0,
        sleep_time: parseInt(document.getElementById("set-sleep").value) || 0,
        buzzer: parseInt(document.getElementById("set-buzzer").value) || 0
    };

    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function () {
        if (this.readyState == 4) {
            var status = document.getElementById("settings-status");
            if (this.status == 200) {
                if (status) status.textContent = bi("Settings saved successfully", "تم حفظ الإعدادات بنجاح");
                loadSettings();
            } else {
                if (status) status.textContent = bi("Failed to save settings", "فشل حفظ الإعدادات");
            }
        }
    };
    xhttp.open("POST", server_ip + "/api/settings", true);
    xhttp.setRequestHeader("Content-Type", "application/json");
    xhttp.send(JSON.stringify(payload));
}

function recallMemory() {
    if (!isConnected) return;
    var mem = parseInt(document.getElementById("set-memory").value) || 0;
    var payload = { extract_memory: mem };
    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function () {
        if (this.readyState == 4) {
            var status = document.getElementById("settings-status");
            if (this.status == 200) {
                if (status) status.textContent = bi("Memory recalled", "تم استدعاء الذاكرة");
                setTimeout(function () { getData(); }, 250);
            } else {
                if (status) status.textContent = bi("Memory recall failed", "فشل استدعاء الذاكرة");
            }
        }
    };
    xhttp.open("POST", server_ip + "/api/settings", true);
    xhttp.setRequestHeader("Content-Type", "application/json");
    xhttp.send(JSON.stringify(payload));
}
