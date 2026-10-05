odoo.define('eran_custom.mes_kiosk_mode', function (require) {
"use strict";

var KioskMode = require('hr_attendance.kiosk_mode');
var AbstractAction = require('web.AbstractAction');
var core = require('web.core');

var MesKioskMode = KioskMode.extend({

    _onBarcodeScanned: function (barcode) {
        var self = this;
        core.bus.off('barcode_scanned', this, this._onBarcodeScanned);
        this._rpc({
                model: 'hr.employee',
                method: 'mes_kiosk_scan',
                args: [barcode],
            })
            .then(function (result) {
                if (result.action) {
                    self.do_action(result.action);
                } else if (result.warning) {
                    self.displayNotification({ title: result.warning, type: 'danger' });
                    core.bus.on('barcode_scanned', self, self._onBarcodeScanned);
                }
            }, function () {
                core.bus.on('barcode_scanned', self, self._onBarcodeScanned);
            });
    },

});

core.action_registry.add('mes_kiosk_mode', MesKioskMode);

var MesMoBarcodeKioskMode = AbstractAction.extend({
    scanType: 'code128',
    start: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            self.$el.css({
                height: '100%',
                overflow: 'auto',
                background: '#01666b',
            });
            self._renderMoScanner();
            core.bus.on('barcode_scanned', self, self._onBarcodeScanned);
        });
    },
    destroy: function () {
        this._stopMoCamera();
        core.bus.off('barcode_scanned', this, this._onBarcodeScanned);
        this._super.apply(this, arguments);
    },
    _scanLog: function (line) {
        var el = this.el && this.el.querySelector('.mes-mo-kiosk-log');
        if (!el) {
            return;
        }
        el.textContent = line || '';
    },
    _stopMoCamera: function () {
        if (this._moScanTimer) {
            clearInterval(this._moScanTimer);
            this._moScanTimer = null;
        }
        if (this._zxingReader) {
            try {
                this._zxingReader.reset();
            } catch (e) {}
            this._zxingReader = null;
        }
        if (this._moStream) {
            this._moStream.getTracks().forEach(function (track) {
                track.stop();
            });
            this._moStream = null;
        }
    },
    _isQrScan: function () {
        return this.scanType === 'qr';
    },
    _renderMoScanner: function () {
        var self = this;
        var title = this._isQrScan() ? 'QR MO Scan' : 'Scan MO';
        this.$el.html(
            '<div style="display:flex;align-items:center;justify-content:center;min-height:100%;padding:24px;">'
            + '<div style="background:white;border-radius:16px;padding:28px 24px;width:420px;max-width:100%;text-align:center;box-shadow:0 8px 30px rgba(0,0,0,0.25);">'
            + '<h2 style="margin:0 0 8px;color:#01666b;">' + title + '</h2>'
            + '<p class="mes-mo-kiosk-log" style="color:#555;font-size:13px;margin:0 0 12px;min-height:18px;">Menyalakan kamera...</p>'
            + '<video class="mes-mo-kiosk-video" autoplay muted playsinline '
            + 'style="width:100%;height:280px;background:#111;border-radius:8px;object-fit:contain;cursor:pointer;display:block;"></video>'
            + '<input class="mes-mo-kiosk-input" type="text" placeholder="Ketik nomor MO, contoh 32665/MOR/PPC/09/26" '
            + 'style="width:100%;box-sizing:border-box;padding:10px;border:1px solid #ccc;border-radius:6px;font-size:15px;margin:12px 0 10px;"/>'
            + '<button type="button" class="mes-mo-kiosk-ok" style="width:100%;padding:12px;background:#28a745;color:white;'
            + 'border:none;border-radius:6px;font-weight:bold;cursor:pointer;">Lanjut</button>'
            + '</div></div>'
        );
        var statusEl = this.el.querySelector('.mes-mo-kiosk-log');
        var input = this.el.querySelector('.mes-mo-kiosk-input');
        var video = this.el.querySelector('.mes-mo-kiosk-video');
        var submit = function (code) {
            return self._submitMoBarcode(code, statusEl);
        };
        this.$('.mes-mo-kiosk-ok').on('click', function (e) {
            e.preventDefault();
            submit((input && input.value) || '');
        });
        this.$('.mes-mo-kiosk-video').on('click', function () {
            self._startMoKioskCamera(video, submit, statusEl);
        });
        if (input) {
            input.addEventListener('keydown', function (e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    submit(input.value);
                }
            });
        }
        setTimeout(function () {
            self._startMoKioskCamera(video, submit, statusEl);
        }, 300);
    },
    _startMoKioskCamera: function (video, onFound, statusEl) {
        var self = this;
        if (!video) {
            return;
        }
        this._stopMoCamera();
        this._scanLog('request kamera...');
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            this._scanLog('GAGAL: browser tidak support kamera');
            return;
        }
        if (this._isQrScan()) {
            this._startQrCamera(video, onFound);
            return;
        }
        window._mesLoadZXing().then(function (ZXing) {
            if (!ZXing.BrowserMultiFormatReader) {
                self._scanLog('GAGAL: BrowserMultiFormatReader tidak ada');
                return;
            }
            var hints = new Map();
            hints.set(ZXing.DecodeHintType.POSSIBLE_FORMATS, [
                ZXing.BarcodeFormat.CODE_128,
                ZXing.BarcodeFormat.CODE_39,
                ZXing.BarcodeFormat.ITF,
                ZXing.BarcodeFormat.CODABAR,
                ZXing.BarcodeFormat.EAN_13,
                ZXing.BarcodeFormat.QR_CODE,
            ]);
            hints.set(ZXing.DecodeHintType.TRY_HARDER, true);
            if (ZXing.DecodeHintType.ALSO_INVERTED !== undefined) {
                hints.set(ZXing.DecodeHintType.ALSO_INVERTED, true);
            }
            var reader = new ZXing.BrowserMultiFormatReader(hints, 100);
            reader._timeBetweenDecodingAttempts = 80;
            self._zxingReader = reader;
            var mode = 0;
            var frames = 0;
            var lastLog = 0;
            reader.drawFrameOnCanvas = function (srcElement) {
                var vw = srcElement.videoWidth || 1;
                var vh = srcElement.videoHeight || 1;
                var pad = 56;
                var canvas = this.captureCanvas;
                var ctx = this.captureCanvasContext;
                var outW = Math.min(vw, 1000);
                var outH = Math.round(vh * (outW / vw));
                if (canvas.width !== outW + pad * 2 || canvas.height !== outH + pad * 2) {
                    canvas.width = outW + pad * 2;
                    canvas.height = outH + pad * 2;
                    this.captureCanvasContext = canvas.getContext('2d', { willReadFrequently: true });
                    ctx = this.captureCanvasContext;
                }
                ctx.fillStyle = '#ffffff';
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                var m = mode % 8;
                mode += 1;
                ctx.save();
                ctx.translate(canvas.width / 2, canvas.height / 2);
                if (m === 1 || m === 3) {
                    ctx.scale(-1, 1);
                }
                if (m === 4) {
                    ctx.rotate(-12 * Math.PI / 180);
                }
                if (m === 5) {
                    ctx.rotate(12 * Math.PI / 180);
                }
                if (m === 6) {
                    ctx.rotate(-6 * Math.PI / 180);
                }
                if (m === 7) {
                    ctx.rotate(6 * Math.PI / 180);
                }
                var sy = (m === 2 || m === 3) ? vh * 0.18 : 0;
                var sh = (m === 2 || m === 3) ? vh * 0.64 : vh;
                var dh = (m === 2 || m === 3) ? outH * 0.64 : outH;
                ctx.drawImage(srcElement, 0, sy, vw, sh, -outW / 2, -dh / 2, outW, dh);
                ctx.restore();
                try {
                    var img = ctx.getImageData(0, 0, canvas.width, canvas.height);
                    var d = img.data;
                    for (var i = 0; i < d.length; i += 4) {
                        var g = d[i] * 0.299 + d[i + 1] * 0.587 + d[i + 2] * 0.114;
                        g = (g - 128) * 1.85 + 128;
                        if (g < 0) { g = 0; } else if (g > 255) { g = 255; }
                        d[i] = d[i + 1] = d[i + 2] = g;
                    }
                    ctx.putImageData(img, 0, 0);
                } catch (e) {}
            };
            self._scanLog('decoder kamera jalan...');
            return reader.decodeFromConstraints({
                video: {
                    width: { ideal: 1280 },
                    height: { ideal: 720 },
                },
            }, video, function (result, err) {
                frames += 1;
                if (result) {
                    var text = result.getText ? result.getText() : (result.text || '');
                    if (text) {
                        self._scanLog('KEBACA kamera: "' + text + '" — cek data MO...');
                        Promise.resolve(onFound(text)).then(function (ok) {
                            if (ok) {
                                self._stopMoCamera();
                            }
                        });
                    }
                    return;
                }
                if (frames === 1 || frames - lastLog >= 20) {
                    lastLog = frames;
                    self._scanLog('belum kebaca (' + frames + ' frame). Tahan barcode di tengah kamera.');
                }
            });
        }).then(function () {
            self._scanLog('kamera aktif, mencari barcode...');
        }).catch(function (err) {
            self._scanLog('GAGAL kamera: ' + ((err && (err.name + ' ' + err.message)) || err));
        });
    },
    _startQrCamera: function (video, onFound) {
        var self = this;
        navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: { ideal: 'environment' },
                width: { ideal: 1280 },
                height: { ideal: 720 },
            },
        }).then(function (stream) {
            self._moStream = stream;
            video.srcObject = stream;
            var play = video.play();
            if (play && play.catch) {
                play.catch(function () {});
            }
            self._scanLog('kamera aktif, mencari QR...');
            if (self._startNativeQrLoop(video, onFound)) {
                return;
            }
            return self._startZxingQr(video, onFound);
        }).catch(function (err) {
            self._scanLog('GAGAL kamera: ' + ((err && (err.name + ' ' + err.message)) || err));
        });
    },
    _startNativeQrLoop: function (video, onFound) {
        var self = this;
        if (typeof window.BarcodeDetector !== 'function') {
            return false;
        }
        var detector;
        try {
            detector = new window.BarcodeDetector({ formats: ['qr_code'] });
        } catch (e) {
            return false;
        }
        var frames = 0;
        var lastLog = 0;
        this._moScanTimer = setInterval(function () {
            if (!video.videoWidth) {
                return;
            }
            frames += 1;
            detector.detect(video).then(function (codes) {
                if (codes && codes[0] && codes[0].rawValue) {
                    var text = codes[0].rawValue;
                    self._scanLog('KEBACA QR: "' + text + '" — cek data MO...');
                    Promise.resolve(onFound(text)).then(function (ok) {
                        if (ok) {
                            self._stopMoCamera();
                        }
                    });
                    return;
                }
                if (frames === 1 || frames - lastLog >= 20) {
                    lastLog = frames;
                    self._scanLog('belum kebaca QR (' + frames + ' frame). Arahkan ke QR printout.');
                }
            }).catch(function () {});
        }, 150);
        return true;
    },
    _startZxingQr: function (video, onFound) {
        var self = this;
        return window._mesLoadZXing().then(function (ZXing) {
            var hints = new Map();
            hints.set(ZXing.DecodeHintType.POSSIBLE_FORMATS, [ZXing.BarcodeFormat.QR_CODE]);
            hints.set(ZXing.DecodeHintType.TRY_HARDER, true);
            var reader = new ZXing.BrowserMultiFormatReader(hints, 80);
            self._zxingReader = reader;
            var frames = 0;
            var lastLog = 0;
            return reader.decodeFromStream(self._moStream, video, function (result) {
                frames += 1;
                if (result) {
                    var text = result.getText ? result.getText() : (result.text || '');
                    if (text) {
                        self._scanLog('KEBACA QR: "' + text + '" — cek data MO...');
                        Promise.resolve(onFound(text)).then(function (ok) {
                            if (ok) {
                                self._stopMoCamera();
                            }
                        });
                    }
                    return;
                }
                if (frames === 1 || frames - lastLog >= 20) {
                    lastLog = frames;
                    self._scanLog('belum kebaca QR (' + frames + ' frame). Arahkan ke QR printout.');
                }
            });
        });
    },
    _submitMoBarcode: function (barcode, statusEl) {
        var self = this;
        var code = (barcode || '').trim();
        if (!code) {
            if (statusEl) {
                statusEl.style.color = '#dc3545';
                statusEl.innerText = 'Isi atau scan nomor MO.';
            }
            this._scanLog('input kosong');
            return Promise.resolve(false);
        }
        this._scanLog('kirim ke server: "' + code + '"');
        core.bus.off('barcode_scanned', this, this._onBarcodeScanned);
        return this._rpc({
                model: 'hr.employee',
                method: 'mes_mo_kiosk_scan',
                args: [code],
            })
            .then(function (result) {
                if (result.action) {
                    self._scanLog('DATA ADA, buka MO');
                    self._stopMoCamera();
                    self.do_action(result.action);
                    return true;
                }
                var msg = (result && result.warning) || 'Barcode MO tidak dikenali.';
                self._scanLog('KEBACA tapi DATA TIDAK ADA: ' + msg);
                if (statusEl) {
                    statusEl.style.color = '#dc3545';
                    statusEl.innerText = msg;
                }
                self.displayNotification({ title: msg, type: 'danger' });
                core.bus.on('barcode_scanned', self, self._onBarcodeScanned);
                return false;
            }, function () {
                self._scanLog('GAGAL server');
                if (statusEl) {
                    statusEl.style.color = '#dc3545';
                    statusEl.innerText = 'Gagal terhubung ke server.';
                }
                core.bus.on('barcode_scanned', self, self._onBarcodeScanned);
                return false;
            });
    },
    _onBarcodeScanned: function (barcode) {
        var statusEl = this.el && this.el.querySelector('.mes-mo-kiosk-log');
        this._submitMoBarcode(barcode, statusEl);
    },
});

var MesMoQrKioskMode = MesMoBarcodeKioskMode.extend({
    scanType: 'qr',
});
core.action_registry.add('mes_mo_qr_kiosk_mode', MesMoQrKioskMode);

return MesKioskMode;

});
