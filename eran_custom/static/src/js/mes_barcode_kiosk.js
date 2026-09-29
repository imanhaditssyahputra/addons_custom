/** @odoo-module **/

function _mesEnsureModal() {
    if (document.getElementById('mes-global-modal')) return;
    var overlay = document.createElement('div');
    overlay.id = 'mes-global-modal';
    overlay.style.cssText = (
        'display:none;position:fixed;top:0;left:0;width:100%;height:100%;'
        + 'background:rgba(0,0,0,0.5);z-index:99999;'
        + 'align-items:center;justify-content:center;'
    );
    overlay.innerHTML = '<div id="mes-modal-inner" style="background:white;border-radius:12px;'
        + 'padding:30px;width:340px;max-height:90vh;overflow-y:auto;'
        + 'text-align:center;box-shadow:0 4px 20px rgba(0,0,0,0.3);"></div>';
    document.body.appendChild(overlay);
    overlay.addEventListener('click', function(e) { e.stopPropagation(); });
    document.getElementById('mes-modal-inner').addEventListener('click', function(e) { e.stopPropagation(); });
}

// Expose ke window supaya bisa dipanggil dari onclick di computed field
window._mesSetModal = function(html, show, wide) {
    _mesEnsureModal();
    var inner = document.getElementById('mes-modal-inner');
    inner.style.width = wide ? '380px' : '340px';
    inner.innerHTML = html;
    var overlay = document.getElementById('mes-global-modal');
    overlay.style.display = show ? 'flex' : 'none';
    inner.querySelectorAll('[data-mes-close]').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            window._mesCloseModal(btn.getAttribute('data-mes-close') === 'reload');
        });
    });
};

window._mesStopCamera = function() {
    if (window._mesScanTimer) {
        clearInterval(window._mesScanTimer);
        window._mesScanTimer = null;
    }
    if (window._mesCameraStream) {
        window._mesCameraStream.getTracks().forEach(function(track) { track.stop(); });
        window._mesCameraStream = null;
    }
};

window._mesCloseModal = function(reload) {
    window._mesStopCamera();
    var overlay = document.getElementById('mes-global-modal');
    if (overlay) overlay.style.display = 'none';
    if (reload) setTimeout(function() { window.location.reload(); }, 150);
};

window._mesJson = function(url, params) {
    return fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify({ jsonrpc: '2.0', method: 'call', id: 1, params: params || {} })
    }).then(function(r) { return r.json(); }).then(function(d) { return d.result || {}; });
};

window.mesStart = function(lineId, btn) {
    if (btn) { btn.disabled = true; btn.innerText = '⏳'; }
    window._mesJson('/mes/start/' + lineId).then(function(res) {
        if (res.success) {
            window._mesSetModal(
                '<div style="font-size:40px;margin-bottom:10px;">✅</div>'
                + '<h3 style="color:#28a745;margin:0 0 8px;">Berhasil</h3>'
                + '<p style="color:#555;font-size:14px;margin-bottom:16px;">' + res.message + '</p>'
                + '<button data-mes-close="reload" style="padding:10px 30px;background:#01666b;'
                + 'color:white;border:none;border-radius:6px;font-weight:bold;cursor:pointer;">OK</button>',
                true
            );
        } else {
            window._mesSetModal(
                '<div style="font-size:40px;margin-bottom:10px;">⚠️</div>'
                + '<h3 style="color:#dc3545;margin:0 0 8px;">Gagal</h3>'
                + '<p style="color:#555;font-size:14px;margin-bottom:16px;">' + (res.message || 'Terjadi kesalahan.') + '</p>'
                + '<button data-mes-close="no" style="padding:10px 30px;background:#6c757d;'
                + 'color:white;border:none;border-radius:6px;font-weight:bold;cursor:pointer;">Tutup</button>',
                true
            );
            if (btn) { btn.disabled = false; btn.innerText = '▶️ START'; }
        }
    }).catch(function() {
        window._mesSetModal('<p style="color:#dc3545;">Tidak bisa terhubung ke server.</p>'
            + '<button data-mes-close="no" style="padding:8px 20px;margin-top:12px;'
            + 'background:#6c757d;color:white;border:none;border-radius:6px;cursor:pointer;">Tutup</button>', true);
        if (btn) { btn.disabled = false; btn.innerText = '▶️ START'; }
    });
};

window.mesStop = async function(lineId) {
    window._mesStopCamera();
    var info = await window._mesJson('/mes/stop/' + lineId + '/losses');
    if (!info.success) {
        window._mesSetModal('<p style="color:#dc3545;">' + (info.message || 'Gagal memuat data.') + '</p>'
            + '<button data-mes-close="no" style="padding:8px 20px;margin-top:12px;'
            + 'background:#6c757d;color:white;border:none;border-radius:6px;cursor:pointer;">Tutup</button>', true);
        return;
    }
    window._mesSetModal(
        '<h3 style="margin:0 0 8px;">Scan QR MO</h3>'
        + '<p style="color:#555;font-size:13px;margin-bottom:10px;">Arahkan kamera ke QR MO di printout. '
        + 'Kalau dari layar HP sulit terbaca, ketik nomor MO di bawah.</p>'
        + '<video id="mes-mo-video" autoplay muted playsinline '
        + 'style="width:100%;height:170px;background:#111;border-radius:8px;object-fit:contain;"></video>'
        + '<p id="mes-scan-status" style="color:#888;font-size:12px;margin:8px 0;">Menyalakan kamera...</p>'
        + '<input id="mes-mo-manual" type="text" placeholder="Ketik atau scan nomor MO" value="" '
        + 'style="width:100%;box-sizing:border-box;padding:10px;border:1px solid #ccc;border-radius:6px;font-size:16px;margin-bottom:10px;"/>'
        + '<button id="mes-mo-manual-ok" style="display:block;width:100%;padding:12px;margin-bottom:8px;background:#28a745;'
        + 'color:white;border:none;border-radius:6px;font-weight:bold;cursor:pointer;">Lanjut</button>'
        + '<button data-mes-close="no" style="display:block;width:100%;padding:10px;background:#6c757d;'
        + 'color:white;border:none;border-radius:6px;cursor:pointer;">Batal</button>',
        true,
        true
    );
    var statusEl = document.getElementById('mes-scan-status');
    var input = document.getElementById('mes-mo-manual');
    var submitMo = async function(code) {
        var verify = await window._mesJson('/mes/stop/' + lineId + '/verify-mo', { barcode: code });
        if (!verify.success) {
            if (statusEl) statusEl.style.color = '#dc3545';
            if (statusEl) statusEl.innerText = verify.message || 'QR MO tidak sesuai.';
            return false;
        }
        window._mesStopCamera();
        window.mesShowStopActions(info);
        return true;
    };
    document.getElementById('mes-mo-manual-ok').addEventListener('click', function(e) {
        e.stopPropagation();
        submitMo((input && input.value) || '');
    });
    if (input) {
        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                submitMo(input.value);
            }
        });
        input.focus();
    }
    window._mesStartMoCamera(submitMo, statusEl);
};

window._mesLoadZXing = function() {
    if (window.ZXing) {
        return Promise.resolve(window.ZXing);
    }
    return new Promise(function(resolve, reject) {
        var script = document.createElement('script');
        script.src = '/web/static/lib/zxing-library/zxing-library.js';
        script.onload = function() { resolve(window.ZXing); };
        script.onerror = reject;
        document.head.appendChild(script);
    });
};

window._mesDecodeCanvas = function(ZXing, canvas) {
    if (!ZXing || !canvas || !canvas.width) {
        return '';
    }
    var formats = [
        ZXing.BarcodeFormat.QR_CODE,
    ];
    var tryHints = function(pure) {
        var hints = new Map();
        hints.set(ZXing.DecodeHintType.POSSIBLE_FORMATS, formats);
        hints.set(ZXing.DecodeHintType.TRY_HARDER, true);
        if (ZXing.DecodeHintType.ALSO_INVERTED !== undefined) {
            hints.set(ZXing.DecodeHintType.ALSO_INVERTED, true);
        }
        if (pure && ZXing.DecodeHintType.PURE_BARCODE !== undefined) {
            hints.set(ZXing.DecodeHintType.PURE_BARCODE, true);
        }
        var reader = new ZXing.MultiFormatReader();
        reader.setHints(hints);
        var source = new ZXing.HTMLCanvasElementLuminanceSource(canvas);
        var sources = [source];
        if (source.invert) {
            try { sources.push(source.invert()); } catch (e) {}
        }
        var bins = [ZXing.HybridBinarizer];
        if (ZXing.GlobalHistogramBinarizer) {
            bins.push(ZXing.GlobalHistogramBinarizer);
        }
        for (var s = 0; s < sources.length; s++) {
            for (var b = 0; b < bins.length; b++) {
                try {
                    reader.reset && reader.reset();
                    var bitmap = new ZXing.BinaryBitmap(new bins[b](sources[s]));
                    var text = reader.decode(bitmap).getText();
                    if (text) {
                        return text;
                    }
                } catch (e) {}
            }
        }
        return '';
    };
    return tryHints(false) || tryHints(true);
};

window._mesBoostCanvas = function(canvas, contrast, invert) {
    var ctx = canvas.getContext('2d', { willReadFrequently: true });
    var img = ctx.getImageData(0, 0, canvas.width, canvas.height);
    var d = img.data;
    var c = contrast || 1.7;
    for (var i = 0; i < d.length; i += 4) {
        var g = d[i] * 0.299 + d[i + 1] * 0.587 + d[i + 2] * 0.114;
        g = (g - 128) * c + 128;
        if (invert) {
            g = 255 - g;
        }
        if (g < 0) { g = 0; } else if (g > 255) { g = 255; }
        d[i] = d[i + 1] = d[i + 2] = g;
    }
    ctx.putImageData(img, 0, 0);
    return canvas;
};

window._mesGrabVideo = function(video, sx, sy, sw, sh, outW, rotDeg, flip) {
    var scale = outW / Math.max(sw, 1);
    var outH = Math.max(2, Math.round(sh * scale));
    var pad = Math.round(Math.max(outW, outH) * 0.08);
    var canvas = document.createElement('canvas');
    canvas.width = outW + pad * 2;
    canvas.height = outH + pad * 2;
    var ctx = canvas.getContext('2d', { willReadFrequently: true });
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.save();
    ctx.translate(canvas.width / 2, canvas.height / 2);
    if (flip) {
        ctx.scale(-1, 1);
    }
    if (rotDeg) {
        ctx.rotate(rotDeg * Math.PI / 180);
    }
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(video, sx, sy, sw, sh, -outW / 2, -outH / 2, outW, outH);
    ctx.restore();
    return canvas;
};

window._mesVideoCanvases = function(video) {
    var canvases = [];
    var w = video.videoWidth;
    var h = video.videoHeight;
    if (!w || !h) {
        return canvases;
    }
    var bandY = Math.round(h * 0.12);
    var bandH = Math.round(h * 0.76);
    var specs = [
        { sx: 0, sy: 0, sw: w, sh: h, out: 900, rot: 0, flip: false, c: 1.6, inv: false },
        { sx: 0, sy: 0, sw: w, sh: h, out: 900, rot: 0, flip: true, c: 1.6, inv: false },
        { sx: 0, sy: bandY, sw: w, sh: bandH, out: 1100, rot: 0, flip: false, c: 1.9, inv: false },
        { sx: 0, sy: bandY, sw: w, sh: bandH, out: 1100, rot: 0, flip: true, c: 1.9, inv: false },
        { sx: 0, sy: 0, sw: w, sh: h, out: 900, rot: -12, flip: false, c: 1.7, inv: false },
        { sx: 0, sy: 0, sw: w, sh: h, out: 900, rot: 12, flip: false, c: 1.7, inv: false },
        { sx: 0, sy: bandY, sw: w, sh: bandH, out: 1000, rot: 0, flip: false, c: 2.1, inv: true },
        { sx: 0, sy: 0, sw: w, sh: h, out: 800, rot: 90, flip: false, c: 1.6, inv: false },
    ];
    for (var i = 0; i < specs.length; i++) {
        var s = specs[i];
        var canvas = window._mesGrabVideo(video, s.sx, s.sy, s.sw, s.sh, s.out, s.rot, s.flip);
        window._mesBoostCanvas(canvas, s.c, s.inv);
        canvases.push(canvas);
    }
    return canvases;
};

window._mesStartMoCamera = async function(onFound, statusEl) {
    var video = document.getElementById('mes-mo-video');
    if (!video) {
        return;
    }
    try {
        var stream = await navigator.mediaDevices.getUserMedia({
            audio: false,
            video: {
                facingMode: 'user',
                width: { ideal: 640 },
                height: { ideal: 480 },
            },
        });
        window._mesCameraStream = stream;
        video.srcObject = stream;
        await video.play();
        if (statusEl) statusEl.innerText = 'Mencari QR MO...';
    } catch (err) {
        if (statusEl) {
            statusEl.style.color = '#dc3545';
            statusEl.innerText = 'Kamera tidak bisa dibuka. Ketik nomor MO di bawah.';
        }
        return;
    }
    var detector = null;
    if (typeof window.BarcodeDetector === 'function') {
        try {
            detector = new window.BarcodeDetector({ formats: ['qr_code'] });
        } catch (e) {
            detector = null;
        }
    }
    if (detector) {
        var busyNative = false;
        window._mesScanTimer = setInterval(async function() {
            if (busyNative || !video.videoWidth) {
                return;
            }
            busyNative = true;
            try {
                var codes = await detector.detect(video);
                if (codes && codes[0] && codes[0].rawValue) {
                    var text = codes[0].rawValue;
                    if (statusEl) {
                        statusEl.style.color = '#28a745';
                        statusEl.innerText = 'Terdeteksi: ' + text;
                    }
                    var ok = await onFound(text);
                    if (ok) {
                        window._mesStopCamera();
                    }
                }
            } catch (e) {
            } finally {
                busyNative = false;
            }
        }, 150);
        return;
    }
    var ZXing;
    try {
        ZXing = await window._mesLoadZXing();
    } catch (err) {
        if (statusEl) statusEl.innerText = 'Library scan gagal dimuat. Ketik nomor MO.';
        return;
    }
    var busy = false;
    window._mesScanTimer = setInterval(async function() {
        if (busy || !video.videoWidth) {
            return;
        }
        busy = true;
        try {
            var canvases = window._mesVideoCanvases(video);
            for (var i = 0; i < canvases.length; i++) {
                var text = window._mesDecodeCanvas(ZXing, canvases[i]);
                if (text) {
                    if (statusEl) {
                        statusEl.style.color = '#28a745';
                        statusEl.innerText = 'Terdeteksi: ' + text;
                    }
                    var ok = await onFound(text);
                    if (ok) {
                        window._mesStopCamera();
                        return;
                    }
                }
            }
        } finally {
            busy = false;
        }
    }, 250);
};

window.mesShowStopActions = function(res) {
    window._mesLosses = res.losses || [];
    window._mesSetModal(
        '<h3 style="margin:0 0 8px;">Aksi untuk Work Order</h3>'
        + '<p style="color:#0b72b9;font-size:22px;font-weight:bold;margin:0 0 6px;line-height:1.3;">'
        + (res.mo_name || '-') + '</p>'
        + '<p style="color:#777;font-size:13px;margin-bottom:20px;">' + (res.wo_name || '-') + '</p>'
        + '<button data-line-id="' + res.line_id + '" data-qty-target="' + res.qty_target + '" id="mes-btn-selesai" '
        + 'style="display:block;width:100%;padding:12px;margin-bottom:10px;background:#28a745;'
        + 'color:white;border:none;border-radius:6px;font-weight:bold;font-size:14px;cursor:pointer;">'
        + '✅ Pekerjaan Telah Selesai</button>'
        + '<button data-line-id="' + res.line_id + '" id="mes-btn-stopline" '
        + 'style="display:block;width:100%;padding:12px;background:#dc3545;'
        + 'color:white;border:none;border-radius:6px;font-weight:bold;font-size:14px;cursor:pointer;">'
        + '⏹️ Stop Line</button>'
        + '<div id="mes-stopline-wrap" style="display:none;margin-top:10px;">'
        + '<select id="mes-loss-select" style="width:100%;padding:10px;border-radius:6px;'
        + 'border:1px solid #ccc;font-size:14px;box-sizing:border-box;margin-bottom:10px;">'
        + window.mesLossOptionsHtml() + '</select>'
        + '<button data-line-id="' + res.line_id + '" id="mes-btn-stopline-ok" '
        + 'style="display:block;width:100%;padding:12px;background:#dc3545;color:white;border:none;'
        + 'border-radius:6px;font-weight:bold;font-size:14px;cursor:pointer;">OK</button>'
        + '</div>'
        + '<button data-mes-close="no" style="display:block;width:100%;padding:10px;'
        + 'margin-top:10px;background:#6c757d;color:white;border:none;border-radius:6px;'
        + 'font-size:13px;cursor:pointer;">Batal</button>',
        true
    );
    document.getElementById('mes-btn-selesai').addEventListener('click', function(e) {
        e.stopPropagation();
        window.mesStopSelesai(parseInt(this.getAttribute('data-line-id')), parseFloat(this.getAttribute('data-qty-target')));
    });
    document.getElementById('mes-btn-stopline').addEventListener('click', function(e) {
        e.stopPropagation();
        document.getElementById('mes-stopline-wrap').style.display = 'block';
        this.style.display = 'none';
        var selesai = document.getElementById('mes-btn-selesai');
        if (selesai) selesai.style.display = 'none';
    });
    document.getElementById('mes-btn-stopline-ok').addEventListener('click', function(e) {
        e.stopPropagation();
        var sel = document.getElementById('mes-loss-select');
        if (!sel || !sel.value) { alert('Pilih alasan stop terlebih dahulu.'); return; }
        window._mesStopExtra = {};
        window.mesStopSubmit(parseInt(this.getAttribute('data-line-id')), 'stop', null, sel.value, 0, false);
    });
};

window.mesKeypadHtml = function(title, subtitle, extraWarn) {
    var keys = [1,2,3,4,5,6,7,8,9,'.',0,'⌫'];
    var keyHtml = keys.map(function(v) {
        return '<button data-keyval="' + v + '" style="padding:14px;font-size:18px;font-weight:bold;'
            + 'border:1px solid #ddd;border-radius:6px;background:' + (v === '⌫' ? '#fff5f5' : 'white') + ';'
            + 'color:' + (v === '⌫' ? '#dc3545' : '#333') + ';cursor:pointer;">' + v + '</button>';
    }).join('');
    return (extraWarn || '')
        + '<h3 style="margin:0 0 6px;">' + title + '</h3>'
        + '<p style="color:#777;font-size:13px;margin-bottom:6px;">' + subtitle + '</p>'
        + '<div id="mes-qty-display" style="font-size:28px;font-weight:bold;color:#333;'
        + 'border:2px solid #ccc;border-radius:6px;padding:12px;margin-bottom:8px;text-align:right;">0</div>'
        + '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-bottom:12px;">'
        + keyHtml + '</div>'
        + '<button id="mes-qty-ok" style="display:block;width:100%;padding:12px;background:#28a745;'
        + 'color:white;border:none;border-radius:6px;font-weight:bold;font-size:15px;cursor:pointer;">OK</button>'
        + '<button id="mes-qty-back" style="display:block;width:100%;padding:10px;margin-top:8px;'
        + 'background:#6c757d;color:white;border:none;border-radius:6px;font-size:13px;cursor:pointer;">← Kembali</button>';
};

window.mesBindKeypad = function(storeKey, onChange) {
    window[storeKey] = '0';
    document.querySelectorAll('[data-keyval]').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            var val = this.getAttribute('data-keyval');
            var q = window[storeKey] || '0';
            if (val === '⌫') { q = q.length > 1 ? q.slice(0, -1) : '0'; }
            else if (val === '.') { if (q.indexOf('.') === -1) q += '.'; }
            else { q = (q === '0') ? String(val) : q + String(val); }
            window[storeKey] = q;
            document.getElementById('mes-qty-display').innerText = q;
            if (onChange) onChange(parseFloat(q) || 0);
        });
    });
};

window.mesStopSelesai = function(lineId, target) {
    window._mesStopLineId = lineId;
    window._mesQtyTarget = parseFloat(target) || 0;
    window._mesSetModal(
        window.mesKeypadHtml(
            'Pekerjaan Telah Selesai',
            'Target: ' + window._mesQtyTarget + ' pcs',
            '<div id="mes-qty-over-target" style="display:none;color:#dc3545;font-size:11px;font-weight:normal;margin:0 0 8px;">Hasil Produksi Melebihi Target</div>'
        ),
        true
    );
    function refreshOver(qty) {
        var over = window._mesQtyTarget > 0 && qty > window._mesQtyTarget;
        var warn = document.getElementById('mes-qty-over-target');
        var okBtn = document.getElementById('mes-qty-ok');
        if (warn) warn.style.display = over ? 'block' : 'none';
        if (okBtn) {
            okBtn.disabled = over;
            okBtn.style.opacity = over ? '0.45' : '1';
            okBtn.style.cursor = over ? 'not-allowed' : 'pointer';
        }
    }
    window.mesBindKeypad('_mesQty', refreshOver);
    document.getElementById('mes-qty-ok').addEventListener('click', function(e) {
        e.stopPropagation();
        var qty = parseFloat(window._mesQty || '0');
        if (!qty || qty <= 0) { alert('Jumlah harus lebih dari 0.'); return; }
        if (window._mesQtyTarget > 0 && qty > window._mesQtyTarget) { return; }
        window._mesSetModal(
            '<div style="font-size:36px;margin-bottom:8px;">⚠️</div>'
            + '<h3 style="margin:0 0 8px;">Konfirmasi Output</h3>'
            + '<div style="font-size:32px;font-weight:bold;color:#0b72b9;margin:16px 0;">' + qty + ' PCS</div>'
            + '<p style="color:#555;font-size:14px;margin-bottom:20px;">Apakah output sudah sesuai?</p>'
            + '<button id="mes-confirm-ya" style="display:inline-block;width:45%;padding:12px;background:#28a745;'
            + 'color:white;border:none;border-radius:6px;font-weight:bold;cursor:pointer;margin:4px;">YA</button>'
            + '<button id="mes-confirm-tidak" style="display:inline-block;width:45%;padding:12px;background:#dc3545;'
            + 'color:white;border:none;border-radius:6px;font-weight:bold;cursor:pointer;margin:4px;">TIDAK</button>',
            true
        );
        document.getElementById('mes-confirm-ya').addEventListener('click', function(ev) {
            ev.stopPropagation();
            window.mesInputNg(lineId, qty, window._mesQtyTarget);
        });
        document.getElementById('mes-confirm-tidak').addEventListener('click', function(ev) {
            ev.stopPropagation();
            window.mesStopSelesai(lineId, window._mesQtyTarget);
        });
    });
    document.getElementById('mes-qty-back').addEventListener('click', function(e) {
        e.stopPropagation();
        window._mesJson('/mes/stop/' + lineId + '/losses').then(function(info) {
            if (info.success) window.mesShowStopActions(info);
        });
    });
};

window.mesInputNg = function(lineId, qty, target) {
    window._mesSetModal(
        window.mesKeypadHtml('Input NG', 'Masukkan jumlah NG (boleh 0)'),
        true
    );
    window.mesBindKeypad('_mesNgQty');
    document.getElementById('mes-qty-ok').addEventListener('click', function(e) {
        e.stopPropagation();
        var ngQty = parseFloat(window._mesNgQty || '0') || 0;
        if (ngQty < 0) { alert('Jumlah NG tidak valid.'); return; }
        window.mesStopReasonTime(lineId, qty, ngQty, target);
    });
    document.getElementById('mes-qty-back').addEventListener('click', function(e) {
        e.stopPropagation();
        window.mesStopSelesai(lineId, target);
    });
};

window.mesLossOptionsHtml = function() {
    var optionsHtml = '<option value="" disabled selected>-- Pilih Alasan --</option>';
    (window._mesLosses || []).forEach(function(l) {
        optionsHtml += '<option value="' + l.id + '">' + l.name + '</option>';
    });
    return optionsHtml;
};

window.mesAskProblemThenHours = function(opts) {
    var title = opts.title || 'Stop Line';
    var subtitle = opts.subtitle || '';
    window._mesSetModal(
        '<h3 style="margin:0 0 8px;">' + title + '</h3>'
        + (subtitle ? '<p style="color:#777;font-size:13px;margin-bottom:10px;">' + subtitle + '</p>' : '')
        + '<select id="mes-loss-select" style="width:100%;padding:10px;border-radius:6px;'
        + 'border:1px solid #ccc;font-size:14px;box-sizing:border-box;margin-bottom:10px;">'
        + window.mesLossOptionsHtml() + '</select>'
        + '<button id="mes-problem-ok" style="display:block;width:100%;padding:12px;background:#dc3545;'
        + 'color:white;border:none;border-radius:6px;font-weight:bold;cursor:pointer;">OK</button>'
        + '<button id="mes-problem-back" style="display:block;width:100%;padding:10px;margin-top:8px;'
        + 'background:#6c757d;color:white;border:none;border-radius:6px;cursor:pointer;">← Kembali</button>',
        true
    );
    document.getElementById('mes-problem-ok').addEventListener('click', function(e) {
        e.stopPropagation();
        var sel = document.getElementById('mes-loss-select');
        if (!sel || !sel.value) { alert('Pilih alasan stop terlebih dahulu.'); return; }
        var lossId = sel.value;
        var lossName = sel.options[sel.selectedIndex].text;
        window._mesSetModal(
            '<h3 style="margin:0 0 6px;">' + title + '</h3>'
            + '<p style="color:#777;font-size:13px;margin-bottom:8px;">Problem: <b>' + lossName + '</b>'
            + (subtitle ? '<br/>' + subtitle : '') + '</p>'
            + window.mesPeriodHtml()
            + '<button id="mes-period-ok" style="display:block;width:100%;padding:12px;background:#dc3545;'
            + 'color:white;border:none;border-radius:6px;font-weight:bold;font-size:15px;cursor:pointer;">OK</button>'
            + '<button id="mes-period-back" style="display:block;width:100%;padding:10px;margin-top:8px;'
            + 'background:#6c757d;color:white;border:none;border-radius:6px;font-size:13px;cursor:pointer;">← Kembali</button>',
            true
        );
        document.getElementById('mes-period-ok').addEventListener('click', function(ev) {
            ev.stopPropagation();
            var period = window.mesReadPeriod();
            if (!period) return;
            window._mesStopExtra = period;
            if (opts.onDone) opts.onDone(lossId, period);
        });
        document.getElementById('mes-period-back').addEventListener('click', function(ev) {
            ev.stopPropagation();
            window.mesAskProblemThenHours(opts);
        });
    });
    document.getElementById('mes-problem-back').addEventListener('click', function(e) {
        e.stopPropagation();
        if (opts.onBack) opts.onBack();
    });
};

window.mesEnsureLosses = function(lineId, thenFn) {
    if (window._mesLosses && window._mesLosses.length) {
        thenFn();
        return;
    }
    window._mesJson('/mes/stop/' + lineId + '/losses').then(function(info) {
        if (info && info.losses) {
            window._mesLosses = info.losses;
        }
        thenFn();
    });
};

window.mesHmOptions = function(max, selected) {
    var html = '';
    for (var i = 0; i <= max; i++) {
        var pad = i < 10 ? '0' + i : String(i);
        html += '<option value="' + i + '"' + (i === selected ? ' selected' : '') + '>' + pad + '</option>';
    }
    return html;
};

window.mesReadPeriod = function() {
    var note = (document.getElementById('mes-stop-note') || {}).value || '';
    note = note.trim();
    if (!note) {
        alert('Isi alasan terlebih dahulu.');
        return null;
    }
    var sh = parseInt(document.getElementById('mes-start-h').value, 10);
    var sm = parseInt(document.getElementById('mes-start-m').value, 10);
    var eh = parseInt(document.getElementById('mes-end-h').value, 10);
    var em = parseInt(document.getElementById('mes-end-m').value, 10);
    if ([sh, sm, eh, em].some(function(v) { return isNaN(v); })) {
        alert('Isi jam dan menit dengan lengkap.');
        return null;
    }
    return {
        note: note,
        start_hour: sh,
        start_minute: sm,
        end_hour: eh,
        end_minute: em,
    };
};

window.mesPeriodHtml = function() {
    var now = new Date();
    var sel = 'width:48%;padding:10px;border:1px solid #ccc;border-radius:6px;font-size:16px;box-sizing:border-box;';
    return '<label style="display:block;text-align:left;font-size:13px;color:#555;margin:8px 0 4px;">Reason</label>'
        + '<textarea id="mes-stop-note" rows="3" placeholder="Ketik alasan..." '
        + 'style="width:100%;padding:10px;border:1px solid #ccc;border-radius:6px;font-size:14px;'
        + 'box-sizing:border-box;margin-bottom:10px;"></textarea>'
        + '<div style="display:flex;gap:8px;text-align:left;margin-bottom:12px;">'
        + '<div style="flex:1;">'
        + '<div style="font-size:12px;color:#555;margin-bottom:4px;">Dari jam</div>'
        + '<select id="mes-start-h" style="' + sel + '">' + window.mesHmOptions(23, now.getHours()) + '</select> '
        + '<select id="mes-start-m" style="' + sel + '">' + window.mesHmOptions(59, 0) + '</select>'
        + '</div>'
        + '<div style="flex:1;">'
        + '<div style="font-size:12px;color:#555;margin-bottom:4px;">Sampai jam</div>'
        + '<select id="mes-end-h" style="' + sel + '">' + window.mesHmOptions(23, now.getHours()) + '</select> '
        + '<select id="mes-end-m" style="' + sel + '">' + window.mesHmOptions(59, now.getMinutes()) + '</select>'
        + '</div></div>';
};

window.mesStopReasonTime = function(lineId, qty, ngQty, target) {
    window.mesEnsureLosses(lineId, function() {
        window.mesAskProblemThenHours({
            title: 'Stop Line',
            subtitle: 'NG: <b>' + ngQty + '</b> pcs',
            onDone: function(lossId) {
                if (target > 0 && qty < target) {
                    window.mesBackorderChoice(lineId, qty, ngQty, lossId);
                } else {
                    window.mesStopSubmit(lineId, 'done', qty, lossId, ngQty, false);
                }
            },
            onBack: function() {
                window.mesInputNg(lineId, qty, target);
            },
        });
    });
};

window.mesBackorderChoice = function(lineId, qty, ngQty, lossId) {
    window._mesSetModal(
        '<div style="font-size:36px;margin-bottom:8px;">⚠️</div>'
        + '<h3 style="margin:0 0 8px;">Output Belum Sesuai Target</h3>'
        + '<p style="color:#555;font-size:14px;margin-bottom:8px;">Target: <b>' + (window._mesQtyTarget || 0) + '</b> pcs<br/>'
        + 'Output: <b>' + qty + '</b> pcs</p>'
        + '<p style="color:#555;font-size:14px;margin-bottom:20px;">Sisa kekurangan mau dibuatkan Backorder?</p>'
        + '<button id="mes-bo-ya" style="display:block;width:100%;padding:12px;margin-bottom:8px;background:#0b72b9;'
        + 'color:white;border:none;border-radius:6px;font-weight:bold;cursor:pointer;">Ya, Buat Backorder</button>'
        + '<button id="mes-bo-tidak" style="display:block;width:100%;padding:12px;background:#6c757d;'
        + 'color:white;border:none;border-radius:6px;font-weight:bold;cursor:pointer;">Tidak, Selesaikan Saja</button>',
        true
    );
    document.getElementById('mes-bo-ya').addEventListener('click', function(e) {
        e.stopPropagation();
        window.mesStopSubmit(lineId, 'done', qty, lossId, ngQty, true);
    });
    document.getElementById('mes-bo-tidak').addEventListener('click', function(e) {
        e.stopPropagation();
        window.mesStopSubmit(lineId, 'done', qty, lossId, ngQty, false);
    });
};

window.mesStopLine = function(lineId) {
    var sel = document.getElementById('mes-loss-select');
    if (!sel || !sel.value) { alert('Pilih alasan stop terlebih dahulu.'); return; }
    var lossId = sel.value;
    var lossName = sel.options[sel.selectedIndex].text;
    window._mesSetModal(
        '<h3 style="margin:0 0 6px;">Stop Line</h3>'
        + '<p style="color:#777;font-size:13px;margin-bottom:8px;">Problem: <b>' + lossName + '</b></p>'
        + window.mesPeriodHtml()
        + '<button id="mes-period-ok" style="display:block;width:100%;padding:12px;background:#dc3545;'
        + 'color:white;border:none;border-radius:6px;font-weight:bold;font-size:15px;cursor:pointer;">OK</button>'
        + '<button id="mes-period-back" style="display:block;width:100%;padding:10px;margin-top:8px;'
        + 'background:#6c757d;color:white;border:none;border-radius:6px;font-size:13px;cursor:pointer;">← Kembali</button>',
        true
    );
    document.getElementById('mes-period-ok').addEventListener('click', function(e) {
        e.stopPropagation();
        var period = window.mesReadPeriod();
        if (!period) return;
        window._mesStopExtra = period;
        window.mesStopSubmit(lineId, 'stop', null, lossId, 0, false);
    });
    document.getElementById('mes-period-back').addEventListener('click', function(e) {
        e.stopPropagation();
        window._mesJson('/mes/stop/' + lineId + '/losses').then(function(info) {
            if (info.success) window.mesShowStopActions(info);
        });
    });
};

window.mesStopSubmit = function(lineId, reason, qty, lossId, ngQty, createBackorder) {
    window._mesSetModal('<div style="font-size:36px;margin-bottom:10px;">⏳</div><p>Memproses...</p>', true);
    var extra = window._mesStopExtra || {};
    window._mesJson('/mes/stop/' + lineId + '/confirm-json', {
        reason: reason,
        qty: qty,
        loss_id: lossId,
        ng_qty: ngQty || 0,
        create_backorder: !!createBackorder,
        note: extra.note || '',
        start_hour: extra.start_hour,
        start_minute: extra.start_minute,
        end_hour: extra.end_hour,
        end_minute: extra.end_minute,
    }).then(function(res) {
        if (res.success) {
            window._mesSetModal(
                '<div style="font-size:40px;margin-bottom:10px;">✅</div>'
                + '<h3 style="color:#28a745;margin:0 0 8px;">Berhasil</h3>'
                + '<p style="color:#555;font-size:14px;margin-bottom:16px;">' + res.message + '</p>'
                + '<button data-mes-close="reload" style="padding:10px 30px;background:#01666b;'
                + 'color:white;border:none;border-radius:6px;font-weight:bold;cursor:pointer;">OK</button>',
                true
            );
        } else {
            window._mesSetModal(
                '<div style="font-size:40px;margin-bottom:10px;">⚠️</div>'
                + '<h3 style="color:#dc3545;margin:0 0 8px;">Gagal</h3>'
                + '<p style="color:#555;font-size:14px;margin-bottom:16px;">' + (res.message || 'Terjadi kesalahan.') + '</p>'
                + '<button data-mes-close="no" style="padding:10px 30px;background:#6c757d;'
                + 'color:white;border:none;border-radius:6px;font-weight:bold;cursor:pointer;">Tutup</button>',
                true
            );
        }
    }).catch(function() {
        window._mesSetModal('<p style="color:#dc3545;">Tidak bisa terhubung ke server.</p>'
            + '<button data-mes-close="no" style="padding:8px 20px;margin-top:12px;background:#6c757d;'
            + 'color:white;border:none;border-radius:6px;cursor:pointer;">Tutup</button>', true);
    });
};
