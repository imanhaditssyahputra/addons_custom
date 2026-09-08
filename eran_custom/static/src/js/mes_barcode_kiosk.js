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
window._mesSetModal = function(html, show) {
    _mesEnsureModal();
    var inner = document.getElementById('mes-modal-inner');
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

window._mesCloseModal = function(reload) {
    var closeBtn = document.querySelector('.o_dialog .btn-close, .o_dialog .o_dialog_close, .modal .btn-close');
    if (closeBtn) closeBtn.click();
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

window.mesStop = function(lineId) {
    window._mesJson('/mes/stop/' + lineId + '/losses').then(function(res) {
        if (!res.success) {
            window._mesSetModal('<p style="color:#dc3545;">' + res.message + '</p>'
                + '<button data-mes-close="no" style="padding:8px 20px;margin-top:12px;'
                + 'background:#6c757d;color:white;border:none;border-radius:6px;cursor:pointer;">Tutup</button>', true);
            return;
        }
        var optionsHtml = '<option value="" disabled selected>-- Pilih Alasan --</option>';
        res.losses.forEach(function(l) {
            optionsHtml += '<option value="' + l.id + '">' + l.name + '</option>';
        });
        window._mesSetModal(
            '<h3 style="margin:0 0 8px;">Aksi untuk Work Order</h3>'
            + '<p style="color:#777;font-size:13px;margin-bottom:20px;">' + res.wo_name + ' — ' + res.mo_name + '</p>'
            + '<button data-line-id="' + res.line_id + '" data-qty-target="' + res.qty_target + '" id="mes-btn-selesai" '
            + 'style="display:block;width:100%;padding:12px;margin-bottom:10px;background:#28a745;'
            + 'color:white;border:none;border-radius:6px;font-weight:bold;font-size:14px;cursor:pointer;">'
            + '✅ Pekerjaan Telah Selesai</button>'
            + '<select id="mes-loss-select" style="width:100%;padding:10px;border-radius:6px;'
            + 'border:1px solid #ccc;font-size:14px;box-sizing:border-box;margin-bottom:10px;">'
            + optionsHtml + '</select>'
            + '<button data-line-id="' + res.line_id + '" id="mes-btn-stopline" '
            + 'style="display:block;width:100%;padding:12px;background:#dc3545;'
            + 'color:white;border:none;border-radius:6px;font-weight:bold;font-size:14px;cursor:pointer;">'
            + '⏹️ Stop Line</button>'
            + '<button data-mes-close="no" style="display:block;width:100%;padding:10px;'
            + 'margin-top:10px;background:#6c757d;color:white;border:none;border-radius:6px;'
            + 'font-size:13px;cursor:pointer;">Batal</button>',
            true
        );
        // Bind tombol selesai dan stopline via addEventListener
        document.getElementById('mes-btn-selesai').addEventListener('click', function(e) {
            e.stopPropagation();
            var lid = parseInt(this.getAttribute('data-line-id'));
            var target = parseFloat(this.getAttribute('data-qty-target'));
            window.mesStopSelesai(lid, target);
        });
        document.getElementById('mes-btn-stopline').addEventListener('click', function(e) {
            e.stopPropagation();
            var lid = parseInt(this.getAttribute('data-line-id'));
            window.mesStopLine(lid);
        });
    });
};

window.mesStopSelesai = function(lineId, target) {
    window._mesQty = '0';
    window._mesStopLineId = lineId;
    var keys = [1,2,3,4,5,6,7,8,9,'.',0,'⌫'];
    var keyHtml = keys.map(function(v) {
        return '<button data-keyval="' + v + '" style="padding:14px;font-size:18px;font-weight:bold;'
            + 'border:1px solid #ddd;border-radius:6px;background:' + (v === '⌫' ? '#fff5f5' : 'white') + ';'
            + 'color:' + (v === '⌫' ? '#dc3545' : '#333') + ';cursor:pointer;">' + v + '</button>';
    }).join('');
    window._mesSetModal(
        '<h3 style="margin:0 0 6px;">Pekerjaan Telah Selesai</h3>'
        + '<p style="color:#777;font-size:13px;margin-bottom:6px;">Target: ' + target + ' pcs</p>'
        + '<div id="mes-qty-display" style="font-size:28px;font-weight:bold;color:#333;'
        + 'border:2px solid #ccc;border-radius:6px;padding:12px;margin-bottom:12px;text-align:right;">0</div>'
        + '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-bottom:12px;">'
        + keyHtml + '</div>'
        + '<button id="mes-qty-ok" style="display:block;width:100%;padding:12px;background:#28a745;'
        + 'color:white;border:none;border-radius:6px;font-weight:bold;font-size:15px;cursor:pointer;">OK</button>'
        + '<button id="mes-qty-back" style="display:block;width:100%;padding:10px;margin-top:8px;'
        + 'background:#6c757d;color:white;border:none;border-radius:6px;font-size:13px;cursor:pointer;">← Kembali</button>',
        true
    );
    document.querySelectorAll('[data-keyval]').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            var val = this.getAttribute('data-keyval');
            var q = window._mesQty || '0';
            if (val === '⌫') { q = q.length > 1 ? q.slice(0, -1) : '0'; }
            else if (val === '.') { if (q.indexOf('.') === -1) q += '.'; }
            else { q = (q === '0') ? String(val) : q + String(val); }
            window._mesQty = q;
            document.getElementById('mes-qty-display').innerText = q;
        });
    });
    document.getElementById('mes-qty-ok').addEventListener('click', function(e) {
        e.stopPropagation();
        var qty = parseFloat(window._mesQty || '0');
        if (!qty || qty <= 0) { alert('Jumlah harus lebih dari 0.'); return; }
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
        document.getElementById('mes-confirm-ya').addEventListener('click', function(e) {
            e.stopPropagation();
            window.mesStopSubmit(window._mesStopLineId, 'done', qty, null);
        });
        document.getElementById('mes-confirm-tidak').addEventListener('click', function(e) {
            e.stopPropagation();
            window.mesStopSelesai(window._mesStopLineId, 0);
        });
    });
    document.getElementById('mes-qty-back').addEventListener('click', function(e) {
        e.stopPropagation();
        window.mesStop(window._mesStopLineId);
    });
};

window.mesStopLine = function(lineId) {
    var sel = document.getElementById('mes-loss-select');
    if (!sel || !sel.value) { alert('Pilih alasan stop terlebih dahulu.'); return; }
    window.mesStopSubmit(lineId, 'stop', null, sel.value);
};

window.mesStopSubmit = function(lineId, reason, qty, lossId) {
    window._mesSetModal('<div style="font-size:36px;margin-bottom:10px;">⏳</div><p>Memproses...</p>', true);
    window._mesJson('/mes/stop/' + lineId + '/confirm-json', {
        reason: reason, qty: qty, loss_id: lossId
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