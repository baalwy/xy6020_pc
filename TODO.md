# XY6020 Connection Fix - TODO

## Root Cause (FIXED)
- BAUD_CODE_TO_RATE mapping was wrong (had code 7=115200, but GY21208.docx says code 6=115200)
- XY6020 baud rate was changed from default — needs reset via `set_baudrate.py`

## Completed
- [x] Fix BAUD_CODE_TO_RATE mapping (0=1200..6=115200, per GY21208.docx)
- [x] Add BAUD_RATE_TO_CODE reverse mapping  
- [x] Create `set_baudrate.py` to auto-detect and reset baud rate
- [x] Auto-baud detection in connect()
- [x] DTR/RTS control
- [x] Arduino delay conditional
- [x] "Auto" option in baudrate selector UI

## Remaining
- [ ] Run `set_baudrate.py` to reset module to 115200
- [ ] Verify web UI connects smoothly at 115200
