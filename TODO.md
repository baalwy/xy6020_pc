# XY6020 PC/RPi Serial Controller - TODO

## خطوات التنفيذ:

- [x] 1. إنشاء `requirements.txt` مع المتطلبات
- [x] 2. إنشاء `xy6020_driver.py` - درايفر Modbus RTU للتواصل مع XY6020
- [x] 3. إنشاء `app.py` - سيرفر Flask الرئيسي مع API endpoints
- [x] 4. إنشاء `static/segment-display.js` - نسخة من ملف العرض الأصلي
- [x] 5. إنشاء `static/style.css` - التصميم مع إضافات لوحة الاتصال
- [x] 6. إنشاء `static/logic.js` - المنطق المعدل للعمل مع Flask API
- [x] 7. إنشاء `static/index.html` - واجهة الويب مع لوحة الاتصال التسلسلي
- [x] 8. إنشاء `run.py` - سكربت التشغيل المتوافق مع Windows و Raspberry Pi 5
- [ ] 9. إنشاء `README.md` - توثيق المشروع
- [ ] 10. اختبار التشغيل

## ملاحظات التوافق:
- Windows: منافذ COM (COM1, COM2, ...)
- Raspberry Pi 5: منافذ /dev/ttyUSB0, /dev/ttyAMA0, /dev/serial0, ...
- استخدام serial.tools.list_ports للكشف التلقائي عن المنافذ
