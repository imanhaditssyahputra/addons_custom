import logging
from odoo import http, fields
from odoo.http import request
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class MesScanController(http.Controller):

    def _info_page(self, title, message, color="#28a745"):
        html = f"""
        <html>
        <head><meta charset="utf-8"/><title>{title}</title></head>
        <body style="
            font-family: -apple-system, Arial, sans-serif;
            background:#f4f4f4;
            display:flex;
            align-items:center;
            justify-content:center;
            height:100vh;
            margin:0;
        ">
            <div style="
                background:white;
                border-radius:12px;
                padding:30px;
                box-shadow:0 4px 20px rgba(0,0,0,0.15);
                width:320px;
                text-align:center;
            ">
                <div style="font-size:40px;margin-bottom:10px;">
                    {"✅" if color == "#28a745" else "⚠️"}
                </div>
                <h3 style="margin:0 0 8px 0;color:{color};">{title}</h3>
                <p style="color:#555;font-size:14px;">{message}</p>
                <p style="color:#999;font-size:12px;margin-top:20px;">
                    Silakan kembali ke tab sebelumnya.
                </p>
            </div>
        </body>
        </html>
        """
        return request.make_response(html)

    # ===================================
    # GREETING PAGE
    # ===================================

    @http.route("/mes/greet/<int:approval_id>", type="http", auth="user")
    def mes_greet(self, approval_id, **kwargs):
        approval = request.env["mes.scan.approval"].sudo().browse(approval_id)

        if not approval.exists():
            return self._info_page("Gagal", f"Approval ID {approval_id} tidak ditemukan.", color="#dc3545")

        tz_record = request.env.user.with_context(tz=request.env.user.tz or "Asia/Jakarta")
        now_local = fields.Datetime.context_timestamp(tz_record, fields.Datetime.now())
        hour = now_local.hour

        if 4 <= hour < 11:
            greeting = "Selamat Pagi"
        elif 11 <= hour < 15:
            greeting = "Selamat Siang"
        elif 15 <= hour < 18:
            greeting = "Selamat Sore"
        else:
            greeting = "Selamat Malam"

        employee_name = approval.employee_id.name or "-"

        html = f"""
        <html>
        <head><meta charset="utf-8"/><title>Selamat Datang</title></head>
        <body style="
            font-family: -apple-system, Arial, sans-serif;
            background:##01666b;
            display:flex;
            align-items:center;
            justify-content:center;
            height:100vh;
            margin:0;
        ">
            <div style="
                background:white;
                border-radius:16px;
                padding:50px 40px;
                text-align:center;
                width:380px;
                box-shadow:0 8px 30px rgba(0,0,0,0.2);
            ">
                <div style="font-size:48px;margin-bottom:10px;">👋</div>
                <h2 style="margin:0 0 6px 0;color:#0b72b9;">{greeting},</h2>
                <h2 style="margin:0 0 20px 0;color:#333;">{employee_name}!</h2>
                <p style="color:#714B67;font-size:14px;margin-bottom:30px;">
                    Siap untuk mulai kerja hari ini?
                </p>

                <div style="
                margin-top:30px;
            ">

                <a href="/web#model=mes.scan.approval&view_type=form&id={approval.id}"
                style="
                        display:block;
                        width:100%;
                        box-sizing:border-box;
                        padding:15px;
                        background:#0b72b9;
                        color:white;
                        text-align:center;
                        border-radius:6px;
                        text-decoration:none;
                        font-weight:bold;
                        font-size:16px;
                ">
                    MULAI
                </a>

            </div>
            </div>
        </body>
        </html>
        """
        return request.make_response(html)

    # ===================================
    # START
    # ===================================

    @http.route("/mes/start/<int:line_id>", type="http", auth="user")
    def mes_start(self, line_id, **kwargs):
        line = request.env["mes.scan.approval.line"].sudo().browse(line_id)

        if not line.exists():
            return self._info_page("Gagal", f"Line ID {line_id} tidak ditemukan.", color="#dc3545")

        try:
            line.action_start()
        except UserError as e:
            return self._info_page("Belum Bisa Dimulai", str(e), color="#dc3545")
        except Exception as e:
            _logger.exception("ERROR saat action_start line_id=%s", line_id)
            return self._info_page("Terjadi Kesalahan", str(e), color="#dc3545")

        wo = line.workorder_id
        return self._info_page(
            "MO Sudah Berjalan",
            f"{wo.name} — {wo.production_id.name} sudah dimulai.",
        )

    # ===================================
    # STOP — pilihan alasan
    # ===================================

    @http.route("/mes/stop/<int:line_id>", type="http", auth="user")
    def mes_stop(self, line_id, **kwargs):
        line = request.env["mes.scan.approval.line"].sudo().browse(line_id)

        if not line.exists():
            return self._info_page("Gagal", f"Line ID {line_id} tidak ditemukan.", color="#dc3545")

        html = f"""
        <html>
        <head><meta charset="utf-8"/><title>Aksi Stop</title></head>
        <body style="font-family:-apple-system,Arial,sans-serif;background:#f4f4f4;
            display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
            <div style="background:white;border-radius:12px;padding:30px;
                box-shadow:0 4px 20px rgba(0,0,0,0.15);width:320px;text-align:center;">
                <h3 style="margin-top:0;">Aksi untuk Work Order</h3>
                <p style="color:#777;font-size:13px;">
                    {line.workorder_id.name} — {line.workorder_id.production_id.name}
                </p>

                <a href="/mes/stop/{line.id}/qty"
                    style="display:block;margin:10px 0;padding:12px;background:#28a745;
                    color:white;border-radius:6px;text-decoration:none;font-weight:bold;">
                    Pekerjaan Telah Selesai
                </a>

                <a href="/mes/stop/{line.id}/reason"
                    style="display:block;margin:10px 0;padding:12px;background:#dc3545;
                    color:white;border-radius:6px;text-decoration:none;font-weight:bold;">
                    Stop Line
                </a>
            </div>
        </body>
        </html>
        """
        return request.make_response(html)
    
    # ===================================
    # STOP — pilih alasan stop
    # ===================================

    @http.route("/mes/stop/<int:line_id>/reason", type="http", auth="user")
    def mes_stop_reason(self, line_id, **kwargs):
        line = request.env["mes.scan.approval.line"].sudo().browse(line_id)

        if not line.exists():
            return self._info_page("Gagal", f"Line ID {line_id} tidak ditemukan.", color="#dc3545")

        # ambil semua alasan loss kecuali "Fully Productive Time"
        losses = request.env["mrp.workcenter.productivity.loss"].sudo().search([
            ("loss_type", "!=", "productive"),
        ])

        options_html = "".join(
            f'<option value="{loss.id}">{loss.name}</option>' for loss in losses
        )

        html = f"""
        <html>
        <head><meta charset="utf-8"/><title>Alasan Stop Line</title></head>
        <body style="font-family:-apple-system,Arial,sans-serif;background:#f4f4f4;
            display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
            <div style="background:white;border-radius:12px;padding:30px;
                box-shadow:0 4px 20px rgba(0,0,0,0.15);width:340px;text-align:center;">
                <h3 style="margin-top:0;">Alasan Stop Line</h3>
                <p style="color:#777;font-size:13px;">
                    {line.workorder_id.name} — {line.workorder_id.production_id.name}
                </p>

                <form action="/mes/stop/{line.id}/confirm" method="get">
                    <input type="hidden" name="reason" value="stop"/>

                    <label style="display:block;text-align:left;font-size:13px;
                        color:#555;margin-bottom:4px;">Pilih Alasan</label>
                    <select name="loss_id" required
                        style="width:100%;padding:10px;border-radius:6px;border:1px solid #ccc;
                        font-size:14px;box-sizing:border-box;margin-bottom:10px;">
                        <option value="" disabled selected>-- Pilih Alasan --</option>
                        {options_html}
                    </select>

                

                    <button type="submit"
                        style="display:block;width:100%;margin-top:14px;padding:12px;
                        background:#0b72b9;color:white;border:none;border-radius:6px;
                        font-weight:bold;font-size:14px;cursor:pointer;">
                        OK
                    </button>
                </form>
            </div>
        </body>
        </html>
        """
        return request.make_response(html)

    # ===================================
    # VERIFY OUTPUT
    # ===================================

    @http.route(
        "/mes/stop/<int:line_id>/verify-output",
        type="http",
        auth="user"
    )
    def mes_verify_output(self, line_id, qty=None, **kwargs):

        line = request.env[
            "mes.scan.approval.line"
        ].sudo().browse(line_id)

        if not line.exists():
            return self._info_page(
                "Gagal",
                f"Line ID {line_id} tidak ditemukan.",
                color="#dc3545",
            )

        # ===================================
        # VALIDASI QTY
        # ===================================

        try:
            qty_value = float(qty) if qty else 0.0
        except (ValueError, TypeError):
            return self._info_page(
                "Gagal",
                "Jumlah produksi tidak valid.",
                color="#dc3545",
            )

        if qty_value <= 0:
            return self._info_page(
                "Gagal",
                "Jumlah hasil produksi harus lebih dari 0.",
                color="#dc3545",
            )

        # ===================================
        # POPUP VERIFIKASI PERTAMA
        # ===================================

        html = f"""
        <html>
        <head>
            <meta charset="utf-8"/>
            <title>Verifikasi Output</title>
        </head>

        <body style="
            font-family:-apple-system,Arial,sans-serif;
            background:#f4f4f4;
            display:flex;
            align-items:center;
            justify-content:center;
            height:100vh;
            margin:0;
        ">

            <div style="
                background:white;
                border-radius:12px;
                padding:30px;
                box-shadow:0 4px 20px rgba(0,0,0,0.15);
                width:340px;
                text-align:center;
            ">

                <div style="
                    font-size:42px;
                    margin-bottom:10px;
                ">
                    ⚠️
                </div>

                <h3 style="
                    margin:0 0 12px 0;
                ">
                    Verifikasi Output
                </h3>

                <p style="
                    color:#777;
                    font-size:13px;
                ">
                    {line.workorder_id.name}
                    —
                    {line.workorder_id.production_id.name}
                </p>

                <div style="
                    margin:20px 0;
                    padding:18px;
                    background:#f8f9fa;
                    border-radius:8px;
                ">

                    <div style="
                        font-size:13px;
                        color:#777;
                        margin-bottom:5px;
                    ">
                        Output yang Anda masukkan
                    </div>

                    <div style="
                        font-size:32px;
                        font-weight:bold;
                        color:#0b72b9;
                    ">
                        {qty_value:g} PCS
                    </div>

                </div>

                <p style="
                    font-size:16px;
                    font-weight:bold;
                    color:#333;
                    margin-bottom:22px;
                ">
                    Apakah Output Sudah Sesuai?
                </p>

                <a href="/mes/stop/{line.id}/qty"
                    style="
                        display:inline-block;
                        width:42%;
                        padding:13px 5px;
                        margin:4px;
                        background:#dc3545;
                        color:white;
                        border-radius:6px;
                        text-decoration:none;
                        font-weight:bold;
                        box-sizing:border-box;
                    ">
                    TIDAK
                </a>

                <a href="/mes/stop/{line.id}/verify-final?qty={qty_value}"
                    style="
                        display:inline-block;
                        width:42%;
                        padding:13px 5px;
                        margin:4px;
                        background:#28a745;
                        color:white;
                        border-radius:6px;
                        text-decoration:none;
                        font-weight:bold;
                        box-sizing:border-box;
                    ">
                    IYA
                </a>

            </div>

        </body>
        </html>
        """

        return request.make_response(html)

    # ===================================
    # VERIFY FINAL
    # ===================================

    @http.route(
        "/mes/stop/<int:line_id>/verify-final",
        type="http",
        auth="user"
    )
    def mes_verify_final(self, line_id, qty=None, **kwargs):

        line = request.env[
            "mes.scan.approval.line"
        ].sudo().browse(line_id)

        if not line.exists():
            return self._info_page(
                "Gagal",
                f"Line ID {line_id} tidak ditemukan.",
                color="#dc3545",
            )

        # ===================================
        # VALIDASI QTY
        # ===================================

        try:
            qty_value = float(qty) if qty else 0.0
        except (ValueError, TypeError):
            return self._info_page(
                "Gagal",
                "Jumlah produksi tidak valid.",
                color="#dc3545",
            )

        if qty_value <= 0:
            return self._info_page(
                "Gagal",
                "Jumlah hasil produksi harus lebih dari 0.",
                color="#dc3545",
            )

        # ===================================
        # VERIFIKASI KEDUA
        # ===================================

        html = f"""
        <html>
        <head>
            <meta charset="utf-8"/>
            <title>Konfirmasi Akhir</title>
        </head>

        <body style="
            font-family:-apple-system,Arial,sans-serif;
            background:#f4f4f4;
            display:flex;
            align-items:center;
            justify-content:center;
            height:100vh;
            margin:0;
        ">

            <div style="
                background:white;
                border-radius:12px;
                padding:30px;
                box-shadow:0 4px 20px rgba(0,0,0,0.15);
                width:340px;
                text-align:center;
            ">

                <div style="
                    font-size:42px;
                    margin-bottom:10px;
                ">
                    🔒
                </div>

                <h3 style="
                    margin:0 0 12px 0;
                ">
                    Konfirmasi Akhir
                </h3>

                <p style="
                    color:#777;
                    font-size:13px;
                ">
                    {line.workorder_id.name}
                    —
                    {line.workorder_id.production_id.name}
                </p>

                <div style="
                    margin:20px 0;
                    padding:18px;
                    background:#f8f9fa;
                    border-radius:8px;
                ">

                    <div style="
                        font-size:13px;
                        color:#777;
                        margin-bottom:5px;
                    ">
                        Output yang akan disimpan
                    </div>

                    <div style="
                        font-size:32px;
                        font-weight:bold;
                        color:#28a745;
                    ">
                        {qty_value:g} PCS
                    </div>

                </div>

                <p style="
                    font-size:16px;
                    font-weight:bold;
                    color:#333;
                    margin-bottom:8px;
                ">
                    Apakah Anda Sudah Yakin?
                </p>

                <p style="
                    color:#777;
                    font-size:13px;
                    margin-bottom:22px;
                ">
                    Setelah memilih YAKIN, output akan dicatat
                    ke hasil produksi.
                </p>

                <a href="/mes/stop/{line.id}/qty"
                    style="
                        display:inline-block;
                        width:42%;
                        padding:13px 5px;
                        margin:4px;
                        background:#6c757d;
                        color:white;
                        border-radius:6px;
                        text-decoration:none;
                        font-weight:bold;
                        box-sizing:border-box;
                    ">
                    BATAL
                </a>

                <a href="/mes/stop/{line.id}/confirm?reason=done&qty={qty_value}&final_confirm=1"
                    style="
                        display:inline-block;
                        width:48%;
                        padding:13px 5px;
                        margin:4px;
                        background:#28a745;
                        color:white;
                        border-radius:6px;
                        text-decoration:none;
                        font-weight:bold;
                        box-sizing:border-box;
                    ">
                    YAKIN & SIMPAN
                </a>

            </div>

        </body>
        </html>
        """

        return request.make_response(html)
    

    # ===================================
    # STOP CONFIRM
    # ===================================

    @http.route("/mes/stop/<int:line_id>/confirm", type="http", auth="user")
    def mes_stop_confirm(self, line_id, reason=None, note=None, qty=None, loss_id=None, final_confirm=None, **kwargs):
        line = request.env["mes.scan.approval.line"].sudo().browse(line_id)

        if not line.exists():
            return self._info_page("Gagal", f"Line ID {line_id} tidak ditemukan.", color="#dc3545")

        if reason not in ("stop", "done"):
            if reason == "done" and final_confirm != "1":
                return self._info_page(
                    "Verifikasi Diperlukan",
                    "Output harus melewati dua tahap verifikasi "
                    "sebelum dapat disimpan.",
                    color="#dc3545",
                )
            return self._info_page("Gagal", "Alasan tidak valid.", color="#dc3545")

        if reason == "done":
            try:
                qty_value = float(qty) if qty else 0.0
            except ValueError:
                return self._info_page("Gagal", "Jumlah produksi tidak valid.", color="#dc3545")

            if qty_value <= 0:
                return self._info_page("Gagal", "Jumlah hasil produksi harus lebih dari 0.", color="#dc3545")

            if line._is_last_active_workorder() and line._check_underproduced(qty_value):
                return self._backorder_choice_page(line, qty_value)

            try:
                line.action_stop("done", qty=qty_value, create_backorder=False)
            except Exception as e:
                request.env.cr.rollback()
                _logger.exception("ERROR saat action_stop line_id=%s reason=done", line_id)
                return self._info_page("Terjadi Kesalahan", str(e), color="#dc3545")

            return self._info_page(
                "Work Order Dihentikan",
                f"{line.workorder_id.name} dihentikan — Pekerjaan Telah Selesai — Output: {qty_value} pcs.",
            )

        # ===== reason == "stop" =====
        try:
            loss_id_value = int(loss_id) if loss_id else None
        except ValueError:
            return self._info_page("Gagal", "Alasan stop tidak valid.", color="#dc3545")

        if not loss_id_value:
            return self._info_page("Gagal", "Alasan stop harus dipilih.", color="#dc3545")

        try:
            line.action_stop("stop", note=note, loss_id=loss_id_value)
        except UserError as e:
            return self._info_page("Gagal", str(e), color="#dc3545")
        except Exception as e:
            _logger.exception("ERROR saat action_stop line_id=%s reason=stop", line_id)
            return self._info_page("Terjadi Kesalahan", str(e), color="#dc3545")

        loss_name = request.env["mrp.workcenter.productivity.loss"].sudo().browse(loss_id_value).name
        return self._info_page(
            "Work Order Dihentikan",
            f"{line.workorder_id.name} dihentikan — {loss_name}.",
        )
    
    # ===================================
    # STOP QTY INPUT
    # ===================================

    @http.route("/mes/stop/<int:line_id>/qty", type="http", auth="user")
    def mes_stop_qty(self, line_id, **kwargs):
        line = request.env["mes.scan.approval.line"].sudo().browse(line_id)

        if not line.exists():
            return self._info_page("Gagal", f"Line ID {line_id} tidak ditemukan.", color="#dc3545")

        html = f"""
        <html>
        <head><meta charset="utf-8"/><title>Hasil Produksi</title></head>
        <body style="
            font-family: -apple-system, Arial, sans-serif;
            background:#f4f4f4;
            display:flex;
            align-items:center;
            justify-content:center;
            height:100vh;
            margin:0;
        ">
            <div style="
                background:white;
                border-radius:12px;
                padding:30px;
                box-shadow:0 4px 20px rgba(0,0,0,0.15);
                width:340px;
                text-align:center;
            ">
                <h3 style="margin-top:0;">Pekerjaan Telah Selesai</h3>
                <p style="color:#777;font-size:13px;">
                    {line.workorder_id.name} — {line.workorder_id.production_id.name}
                </p>
                <p style="color:#555;font-size:13px;">
                    Target: {line.qty_target}
                </p>

                <form id="qtyForm" action="/mes/stop/{line.id}/verify-output" method="get">
                    <input type="hidden" name="reason" value="done"/>

                    <label style="display:block;text-align:left;font-size:13px;
                        color:#555;margin-bottom:4px;">
                        Jumlah Hasil Produksi (pcs)
                    </label>

                    <input id="qtyDisplay" name="qty" type="text" readonly required
                        value=""
                        style="width:100%;padding:14px;border-radius:6px;
                        border:2px solid #ccc;font-size:22px;text-align:right;
                        box-sizing:border-box;background:#fafafa;margin-bottom:14px;
                        font-weight:bold;color:#333;"/>

                    <div id="keypad" style="
                        display:grid;
                        grid-template-columns:repeat(3, 1fr);
                        gap:8px;
                        margin-bottom:14px;
                    ">
                        <button type="button" class="keyBtn" data-val="1">1</button>
                        <button type="button" class="keyBtn" data-val="2">2</button>
                        <button type="button" class="keyBtn" data-val="3">3</button>
                        <button type="button" class="keyBtn" data-val="4">4</button>
                        <button type="button" class="keyBtn" data-val="5">5</button>
                        <button type="button" class="keyBtn" data-val="6">6</button>
                        <button type="button" class="keyBtn" data-val="7">7</button>
                        <button type="button" class="keyBtn" data-val="8">8</button>
                        <button type="button" class="keyBtn" data-val="9">9</button>
                        <button type="button" class="keyBtn" data-val=".">.</button>
                        <button type="button" class="keyBtn" data-val="0">0</button>
                        <button type="button" id="clearBtn" style="
                            padding:16px 0;font-size:18px;font-weight:bold;border-radius:6px;
                            border:1px solid #dc3545;background:#fff5f5;color:#dc3545;cursor:pointer;">
                            ⌫
                        </button>
                    </div>

                    <button type="submit"
                        style="display:block;width:100%;padding:14px;
                        background:#28a745;color:white;border:none;border-radius:6px;
                        font-weight:bold;font-size:16px;cursor:pointer;">
                        OK
                    </button>
                </form>
            </div>

            <style>
                .keyBtn {{
                    padding:16px 0;
                    font-size:20px;
                    font-weight:bold;
                    border-radius:6px;
                    border:1px solid #ccc;
                    background:#fff;
                    color:#333;
                    cursor:pointer;
                }}
                .keyBtn:active {{
                    background:#e9ecef;
                }}
            </style>

            <script>
                var display = document.getElementById('qtyDisplay');
                var buttons = document.querySelectorAll('.keyBtn');

                buttons.forEach(function(btn) {{
                    btn.addEventListener('click', function() {{
                        var val = btn.getAttribute('data-val');
                        if (val === '.' && display.value.includes('.')) {{
                            return;
                        }}
                        display.value += val;
                    }});
                }});

                document.getElementById('clearBtn').addEventListener('click', function() {{
                    display.value = display.value.slice(0, -1);
                }});

                document.getElementById('qtyForm').addEventListener('submit', function(e) {{
                    if (!display.value || parseFloat(display.value) <= 0) {{
                        e.preventDefault();
                        alert('Jumlah hasil produksi harus lebih dari 0.');
                    }}
                }});
            </script>
        </body>
        </html>
        """

        return request.make_response(html)


    def _backorder_choice_page(self, line, qty_value):
        html = f"""
        <html>
        <head><meta charset="utf-8"/><title>Konfirmasi Backorder</title></head>
        <body style="font-family:-apple-system,Arial,sans-serif;background:#f4f4f4;
            display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
            <div style="background:white;border-radius:12px;padding:30px;
                box-shadow:0 4px 20px rgba(0,0,0,0.15);width:360px;text-align:center;">
                <div style="font-size:40px;margin-bottom:10px;">⚠️</div>
                <h3 style="margin:0 0 8px 0;">Output Belum Sesuai Target</h3>
                <p style="color:#777;font-size:13px;">
                    {line.workorder_id.name} — {line.workorder_id.production_id.name}
                </p>
                <p style="color:#555;font-size:14px;margin-bottom:20px;">
                    Target: <b>{line.qty_target}</b> pcs<br/>
                    Output: <b>{qty_value}</b> pcs
                </p>
                <p style="color:#555;font-size:13px;margin-bottom:20px;">
                    Sisa kekurangan mau dibuatkan Backorder (MO baru untuk sisanya)?
                </p>

                <a href="/mes/stop/{line.id}/backorder-confirm?qty={qty_value}&create_backorder=1"
                    style="display:block;margin:10px 0;padding:14px;background:#0b72b9;
                    color:white;border-radius:6px;text-decoration:none;font-weight:bold;">
                    Ya, Buat Backorder
                </a>

                <a href="/mes/stop/{line.id}/backorder-confirm?qty={qty_value}&create_backorder=0"
                    style="display:block;margin:10px 0;padding:14px;background:#6c757d;
                    color:white;border-radius:6px;text-decoration:none;font-weight:bold;">
                    Tidak, Selesaikan Saja
                </a>
            </div>
        </body>
        </html>
        """
        return request.make_response(html)

    @http.route("/mes/stop/<int:line_id>/backorder-confirm", type="http", auth="user")
    def mes_stop_backorder_confirm(self, line_id, qty=None, create_backorder=None, **kwargs):
        line = request.env["mes.scan.approval.line"].sudo().browse(line_id)

        if not line.exists():
            return self._info_page("Gagal", f"Line ID {line_id} tidak ditemukan.", color="#dc3545")

        approval = line.approval_id.sudo()

        try:
            qty_value = float(qty) if qty else 0.0
        except ValueError:
            return self._info_page("Gagal", "Jumlah produksi tidak valid.", color="#dc3545")

        backorder_flag = create_backorder == "1"

        try:
            line.action_stop("done", qty=qty_value, create_backorder=backorder_flag)
        except Exception as e:
            request.env.cr.rollback()
            _logger.exception("ERROR saat action_stop (backorder) line_id=%s", line_id)
            return self._info_page("Terjadi Kesalahan", str(e), color="#dc3545")

        label = "dengan Backorder" if backorder_flag else "tanpa Backorder"
        return self._info_page(
            "Work Order Dihentikan",
            f"{line.workorder_id.name} selesai — Output: {qty_value} pcs ({label}).",
        )

    # =================================
    # ENDPOINT UNTUK BUKA RIWAYAT MO
    # =================================

    @http.route(
        "/mes/my-history",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def mes_my_history(self, **kwargs):

        employee_id = request.session.get("mes_employee_id")

        # =====================================================
        # BELUM SCAN
        # =====================================================

        if not employee_id:
            return self._info_page(
                "Akses Ditolak",
                "Silakan scan barcode operator terlebih dahulu.",
                color="#dc3545",
            )

        employee = request.env["hr.employee"].sudo().browse(employee_id)

        if not employee.exists():
            request.session.pop("mes_employee_id", None)

            return self._info_page(
                "Akses Ditolak",
                "Data operator tidak ditemukan. Silakan scan kembali.",
                color="#dc3545",
            )

        # =====================================================
        # CARI RIWAYAT OPERATOR
        # =====================================================

        approvals = request.env["mes.scan.approval"].sudo().search(
            [
                ("employee_id", "=", employee.id),
            ],
            order="scan_time desc",
        )

        # =====================================================
        # HTML RIWAYAT
        # =====================================================

        rows = ""

        for approval in approvals:

            scan_time = approval.scan_time

            if scan_time:
                scan_time = fields.Datetime.context_timestamp(
                    approval,
                    scan_time,
                )

                scan_time = scan_time.strftime(
                    "%d/%m/%Y %H:%M"
                )
            else:
                scan_time = "-"

            rows += f"""
            <tr>
                <td>{scan_time}</td>
                <td>{approval.shift_id.name or "-"}</td>
                <td>
                    <a href="/mes/greet/{approval.id}"
                    style="
                            display:inline-block;
                            padding:7px 12px;
                            background:#0b72b9;
                            color:white;
                            border-radius:5px;
                            text-decoration:none;
                    ">
                        Lihat
                    </a>
                </td>
            </tr>
            """

        if not rows:
            rows = """
            <tr>
                <td colspan="3"
                    style="text-align:center;padding:20px;">
                    Belum ada riwayat MO.
                </td>
            </tr>
            """

        html = f"""
        <html>
        <head>
            <meta charset="utf-8"/>
            <title>Riwayat MO</title>
        </head>

        <body style="
            font-family:-apple-system,Arial,sans-serif;
            background:#f4f4f4;
            margin:0;
            padding:30px;
        ">

            <div style="
                max-width:900px;
                margin:auto;
                background:white;
                border-radius:12px;
                padding:25px;
                box-shadow:0 4px 20px rgba(0,0,0,0.12);
            ">

                <h2 style="margin-top:0;">
                    Riwayat MO
                </h2>

                <div style="
                    background:#eef7ff;
                    padding:15px;
                    border-radius:8px;
                    margin-bottom:20px;
                ">
                    <b>Operator:</b>
                    {employee.name}
                </div>

                <table style="
                    width:100%;
                    border-collapse:collapse;
                ">

                    <thead>
                        <tr>
                            <th style="
                                text-align:left;
                                padding:10px;
                                border-bottom:1px solid #ddd;
                            ">
                                Tanggal Scan
                            </th>

                            <th style="
                                text-align:left;
                                padding:10px;
                                border-bottom:1px solid #ddd;
                            ">
                                Shift
                            </th>

                            <th style="
                                text-align:left;
                                padding:10px;
                                border-bottom:1px solid #ddd;
                            ">
                                Aksi
                            </th>
                        </tr>
                    </thead>

                    <tbody>
                        {rows}
                    </tbody>

                </table>

                <div style="margin-top:20px;">

                    <a href="/mes/greet/{approvals[:1].id if approvals else 0}"
                    style="
                            display:inline-block;
                            padding:10px 15px;
                            background:#28a745;
                            color:white;
                            border-radius:6px;
                            text-decoration:none;
                            margin-right:8px;
                    ">
                        MO Scan
                    </a>

                </div>

            </div>

        </body>
        </html>
        """

        return request.make_response(html)



   
