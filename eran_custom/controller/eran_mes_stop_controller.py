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
            greeting, emoji = "Selamat Pagi", "🌅"
        elif 11 <= hour < 15:
            greeting, emoji = "Selamat Siang", "☀️"
        elif 15 <= hour < 18:
            greeting, emoji = "Selamat Sore", "🌤️"
        else:
            greeting, emoji = "Selamat Malam", "🌙"

        employee_name = approval.employee_id.name or "-"

        # Buat list ringkas MO + product
        mo_rows = ""
        for line in approval.line_ids.sorted("sequence"):
            wo = line.workorder_id
            mo_name = wo.production_id.name or "-"
            product = wo.production_id.product_id.display_name or "-"
            mo_rows += f"""
            <tr>
                <td style="padding:6px 8px;color:#333;font-weight:bold;">{mo_name}</td>
                <td style="padding:6px 8px;color:#555;font-size:13px;">{product}</td>
            </tr>
            """

        mo_section = ""
        if mo_rows:
            mo_section = f"""
            <div style="margin:20px 0;text-align:left;">
                <p style="font-size:13px;color:#777;margin-bottom:8px;">
                    MO hari ini untuk kamu:
                </p>
                <table style="width:100%;border-collapse:collapse;">
                    <thead>
                        <tr style="border-bottom:1px solid #e0e0e0;">
                            <th style="padding:6px 8px;text-align:left;font-size:12px;color:#999;">MO</th>
                            <th style="padding:6px 8px;text-align:left;font-size:12px;color:#999;">Product</th>
                        </tr>
                    </thead>
                    <tbody>{mo_rows}</tbody>
                </table>
            </div>
            """
        else:
            mo_section = "<p style='color:#999;font-size:13px;margin:16px 0;'>Belum ada MO untuk hari ini.</p>"

        html = f"""
        <html>
        <head>
            <meta charset="utf-8"/>
            <meta name="viewport" content="width=device-width,initial-scale=1"/>
            <title>MES Kiosk</title>
            <style>
                * {{ box-sizing: border-box; margin: 0; padding: 0; }}
                body {{
                    font-family: -apple-system, Arial, sans-serif;
                    background: #01666b;
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    padding: 20px 16px;
                }}
                .card {{
                    background: white;
                    border-radius: 16px;
                    padding: 36px 32px;
                    width: 100%;
                    max-width: 440px;
                    box-shadow: 0 8px 30px rgba(0,0,0,0.2);
                    text-align: center;
                }}
            </style>
        </head>
        <body>
            <div class="card">
                <div style="font-size:48px;margin-bottom:12px;">{emoji} 👋</div>
                <h2 style="color:#01666b;margin-bottom:4px;">{greeting},</h2>
                <h2 style="color:#333;margin-bottom:8px;">{employee_name}!</h2>
                <p style="color:#777;font-size:14px;">
                    Semangat bekerja hari ini! 💪<br/>
                    Berikan yang terbaik untuk tim.
                </p>

                {mo_section}

                <a href="/web#model=mes.scan.approval&id={approval.id}&view_type=form"
                    style="display:block;width:100%;padding:14px;margin-top:8px;
                    background:#01666b;color:white;border-radius:8px;
                    text-decoration:none;font-weight:bold;font-size:16px;">
                    ✅ OK — Mulai Kerja
                </a>
            </div>
        </body>
        </html>
        """
        return request.make_response(html)

    # ===================================
    # START
    # ===================================

    @http.route("/mes/start/<int:line_id>", type="json", auth="user")
    def mes_start(self, line_id, **kwargs):
        line = request.env["mes.scan.approval.line"].sudo().browse(line_id)

        if not line.exists():
            return {"success": False, "message": f"Line ID {line_id} tidak ditemukan."}

        try:
            line.action_start()
        except UserError as e:
            return {"success": False, "message": str(e)}
        except Exception as e:
            _logger.exception("ERROR saat action_start line_id=%s", line_id)
            return {"success": False, "message": str(e)}

        wo = line.workorder_id
        return {
            "success": True,
            "message": f"{wo.name} — {wo.production_id.name} sudah dimulai."
        }

    # ===================================
    # STOP — GET LOSSES (JSON)
    # ===================================

    @http.route("/mes/stop/<int:line_id>/losses", type="json", auth="user")
    def mes_stop_losses(self, line_id, **kwargs):
        line = request.env["mes.scan.approval.line"].sudo().browse(line_id)
        if not line.exists():
            return {"success": False, "message": "Line tidak ditemukan."}

        losses = request.env["mrp.workcenter.productivity.loss"].sudo().search([
            ("loss_type", "!=", "productive"),
        ])

        wo = line.workorder_id
        return {
            "success": True,
            "line_id": line.id,
            "wo_name": wo.name or "-",
            "mo_name": wo.production_id.name or "-",
            "qty_target": line.qty_target,
            "losses": [{"id": l.id, "name": l.name} for l in losses],
        }

    @http.route("/mes/stop/<int:line_id>/verify-mo", type="json", auth="user")
    def mes_stop_verify_mo(self, line_id, barcode=None, **kwargs):
        line = request.env["mes.scan.approval.line"].sudo().browse(line_id)
        if not line.exists():
            return {"success": False, "message": "Line tidak ditemukan."}
        scanned = (barcode or "").strip()
        if not scanned:
            return {"success": False, "message": "Barcode MO belum terdeteksi."}
        mo_name = (line.workorder_id.production_id.name or "").strip()
        scanned_norm = "".join(scanned.split()).upper()
        mo_norm = "".join(mo_name.split()).upper()
        ok = (
            scanned_norm == mo_norm
            or (len(scanned_norm) >= 6 and scanned_norm in mo_norm)
            or (len(mo_norm) >= 6 and mo_norm in scanned_norm)
        )
        if not ok:
            return {
                "success": False,
                "message": (
                    f"Barcode tidak sesuai. Scan barcode MO {mo_name} "
                    "di pojok kanan atas dokumen."
                ),
            }
        return {"success": True, "mo_name": mo_name}


    # ===================================
    # STOP — CONFIRM (JSON)
    # ===================================

    @http.route("/mes/stop/<int:line_id>/confirm-json", type="json", auth="user")
    def mes_stop_confirm_json(self, line_id, reason=None, qty=None, loss_id=None, ng_qty=None, create_backorder=None,
                              note=None, start_hour=None, start_minute=None, end_hour=None, end_minute=None, **kwargs):
        line = request.env["mes.scan.approval.line"].sudo().browse(line_id)
        if not line.exists():
            return {"success": False, "message": "Line tidak ditemukan."}

        def _int_or_none(val):
            if val in (None, ""):
                return None
            try:
                return int(val)
            except (ValueError, TypeError):
                return None

        start_h = _int_or_none(start_hour)
        start_m = _int_or_none(start_minute)
        end_h = _int_or_none(end_hour)
        end_m = _int_or_none(end_minute)
        note_text = (note or "").strip() or None

        if reason == "done":
            try:
                qty_value = float(qty) if qty else 0.0
            except (ValueError, TypeError):
                return {"success": False, "message": "Jumlah produksi tidak valid."}

            if qty_value <= 0:
                return {"success": False, "message": "Jumlah hasil produksi harus lebih dari 0."}

            if line._is_output_over_target(qty_value):
                return {"success": False, "message": "Output Melebihi Target"}

            try:
                ng_value = float(ng_qty) if ng_qty not in (None, "") else 0.0
            except (ValueError, TypeError):
                return {"success": False, "message": "Jumlah NG tidak valid."}

            backorder_flag = bool(create_backorder)
            try:
                line.action_stop(
                    "done",
                    qty=qty_value,
                    ng_qty=ng_value,
                    create_backorder=backorder_flag,
                    note=note_text,
                    start_hour=start_h,
                    start_minute=start_m,
                    end_hour=end_h,
                    end_minute=end_m,
                )
            except Exception as e:
                request.env.cr.rollback()
                _logger.exception("ERROR action_stop done line_id=%s", line_id)
                return {"success": False, "message": str(e)}

            wo = line.workorder_id
            extra = []
            if ng_value:
                extra.append(f"NG: {ng_value:g} pcs")
            if backorder_flag:
                extra.append("Backorder dibuat")
            suffix = f" ({', '.join(extra)})" if extra else ""
            return {
                "success": True,
                "message": f"{wo.name} selesai. Output: {qty_value:g} pcs.{suffix}",
            }

        elif reason == "stop":
            try:
                loss_id_value = int(loss_id) if loss_id else None
            except (ValueError, TypeError):
                return {"success": False, "message": "Alasan stop tidak valid."}

            if not loss_id_value:
                return {"success": False, "message": "Alasan stop harus dipilih."}

            try:
                line.action_stop(
                    "stop",
                    loss_id=loss_id_value,
                    note=note_text,
                    start_hour=start_h,
                    start_minute=start_m,
                    end_hour=end_h,
                    end_minute=end_m,
                )
            except UserError as e:
                return {"success": False, "message": str(e)}
            except Exception as e:
                _logger.exception("ERROR action_stop stop line_id=%s", line_id)
                return {"success": False, "message": str(e)}

            loss_name = request.env["mrp.workcenter.productivity.loss"].sudo().browse(loss_id_value).name
            wo = line.workorder_id
            return {
                "success": True,
                "message": f"{wo.name} dihentikan — {loss_name}."
            }

        return {"success": False, "message": "Alasan tidak valid."}

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

        if line._is_output_over_target(qty_value):
            return self._info_page(
                "Gagal",
                "Output Melebihi Target",
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

        if line._is_output_over_target(qty_value):
            return self._info_page(
                "Gagal",
                "Output Melebihi Target",
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

            if line._is_output_over_target(qty_value):
                return self._info_page("Gagal", "Output Melebihi Target", color="#dc3545")

            try:
                line.action_stop("done", qty=qty_value)
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
                <div id="overTargetMsg" style="display:none;color:#dc3545;font-size:11px;margin:0 0 8px;">
                    Hasil Produksi Melebihi Target
                </div>
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

                    <button type="submit" id="qtyOkBtn"
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
                var targetQty = {line.qty_target or 0};
                var overMsg = document.getElementById('overTargetMsg');
                var okBtn = document.getElementById('qtyOkBtn');

                function refreshOverTarget() {{
                    var qty = parseFloat(display.value || '0') || 0;
                    var over = targetQty > 0 && qty > targetQty;
                    overMsg.style.display = over ? 'block' : 'none';
                    okBtn.disabled = over;
                    okBtn.style.opacity = over ? '0.45' : '1';
                    okBtn.style.cursor = over ? 'not-allowed' : 'pointer';
                }}

                buttons.forEach(function(btn) {{
                    btn.addEventListener('click', function() {{
                        var val = btn.getAttribute('data-val');
                        if (val === '.' && display.value.includes('.')) {{
                            return;
                        }}
                        display.value += val;
                        refreshOverTarget();
                    }});
                }});

                document.getElementById('clearBtn').addEventListener('click', function() {{
                    display.value = display.value.slice(0, -1);
                    refreshOverTarget();
                }});

                document.getElementById('qtyForm').addEventListener('submit', function(e) {{
                    if (!display.value || parseFloat(display.value) <= 0) {{
                        e.preventDefault();
                        alert('Jumlah hasil produksi harus lebih dari 0.');
                        return;
                    }}
                    if (targetQty > 0 && parseFloat(display.value) > targetQty) {{
                        e.preventDefault();
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



   