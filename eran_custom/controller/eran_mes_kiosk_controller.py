import logging
import pytz
from datetime import timedelta
from odoo import http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)


class EranAttendanceKioskController(http.Controller):

    def _greeting(self, hour):
        if 4 <= hour < 11:
            return "Selamat Pagi"
        elif 11 <= hour < 15:
            return "Selamat Siang"
        elif 15 <= hour < 18:
            return "Selamat Sore"
        else:
            return "Selamat Malam"

    def _page(self, title, body_html):
        """Wrapper halaman HTML kiosk attendance."""
        return request.make_response(f"""
        <html>
        <head>
            <meta charset="utf-8"/>
            <meta name="viewport" content="width=device-width, initial-scale=1"/>
            <title>{title}</title>
            <style>
                * {{ box-sizing: border-box; margin: 0; padding: 0; }}
                body {{
                    font-family: -apple-system, Arial, sans-serif;
                    background: #01666b;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    min-height: 100vh;
                }}
                .card {{
                    background: white;
                    border-radius: 16px;
                    padding: 50px 40px;
                    text-align: center;
                    width: 420px;
                    box-shadow: 0 8px 30px rgba(0,0,0,0.25);
                }}
                .btn {{
                    display: block;
                    width: 100%;
                    padding: 15px;
                    border-radius: 8px;
                    text-decoration: none;
                    font-weight: bold;
                    font-size: 16px;
                    margin-top: 12px;
                    cursor: pointer;
                    border: none;
                }}
                .btn-primary {{ background: #01666b; color: white; }}
                .btn-danger  {{ background: #dc3545; color: white; }}
                .btn-secondary {{ background: #6c757d; color: white; }}
            </style>
        </head>
        <body>
            <div class="card">
                {body_html}
            </div>
        </body>
        </html>
        """)

    # =========================================================
    # HALAMAN UTAMA KIOSK — tampil form scan barcode
    # =========================================================

    @http.route(
        "/attendance/kiosk",
        type="http",
        auth="user",
        website=False,
        csrf=False,
    )
    def attendance_kiosk(self, error=None, **kwargs):

        error_html = ""
        if error:
            error_html = f"""
            <div style="
                background: #fff3cd;
                border: 1px solid #ffc107;
                border-radius: 8px;
                padding: 12px;
                margin-bottom: 20px;
                color: #856404;
                font-size: 14px;
            ">
                ⚠️ {error}
            </div>
            """

        body = f"""
        <div style="font-size:56px; margin-bottom:16px;">🏭</div>
        <h2 style="color:#01666b; margin-bottom:4px;">PT Eran Teknikatama</h2>
        <p style="color:#777; font-size:14px; margin-bottom:28px;">
            Scan barcode untuk absensi masuk
        </p>

        {error_html}

        <form method="POST" action="/attendance/kiosk/scan">
            <input
                type="text"
                name="barcode"
                <input type="text" name="barcode" placeholder="Scan barcode di sini..." autofocus autocomplete="off" style="width:100%;padding:14px;border:2px solid #01666b;border-radius:8px;font-size:16px;text-align:center;margin-bottom:12px;outline:none;" />
                autofocus
                autocomplete="off"
                style="
                    width: 100%;
                    padding: 14px;
                    border: 2px solid #01666b;
                    border-radius: 8px;
                    font-size: 16px;
                    text-align: center;
                    margin-bottom: 12px;
                    outline: none;
                "
            />
            <button type="submit" class="btn btn-primary">
                ✅ Absen Masuk
            </button>
        </form>
        """

        return self._page("Kiosk Absensi", body)

    # =========================================================
    # PROSES SCAN BARCODE — catat hr.attendance
    # =========================================================

    @http.route(
        "/attendance/kiosk/scan",
        type="http",
        auth="user",
        methods=["POST"],
        website=False,
        csrf=False,
    )
    def attendance_kiosk_scan(self, barcode=None, **kwargs):

        if not barcode or not barcode.strip():
            return request.redirect("/attendance/kiosk?error=Barcode+tidak+boleh+kosong")

        barcode = barcode.strip()

        # Cari employee
        employee = request.env["hr.employee"].sudo().search([
            ("barcode", "=", barcode)
        ], limit=1)

        if not employee:
            return request.redirect(
                "/attendance/kiosk?error=Barcode+tidak+dikenali.+Hubungi+HRD."
            )

        # =====================================================
        # WAKTU SEKARANG (LOKAL JAKARTA)
        # =====================================================

        now_utc = fields.Datetime.now()
        tz = pytz.timezone("Asia/Jakarta")
        now_local = pytz.utc.localize(now_utc).astimezone(tz)

        today_utc = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_utc = today_utc + timedelta(days=1)

        # =====================================================
        # CEK APAKAH SUDAH ABSEN HARI INI
        # =====================================================

        existing_attendance = request.env["hr.attendance"].sudo().search([
            ("employee_id", "=", employee.id),
            ("check_in", ">=", today_utc),
            ("check_in", "<", tomorrow_utc),
        ], order="check_in desc", limit=1)

        if existing_attendance:
            # Sudah absen — tampil info, arahkan ke MES kiosk
            check_in_local = pytz.utc.localize(
                existing_attendance.check_in
            ).astimezone(tz)

            body = f"""
            <div style="font-size:48px; margin-bottom:12px;">ℹ️</div>
            <h3 style="color:#0b72b9; margin-bottom:6px;">
                Sudah Absen Hari Ini
            </h3>
            <h2 style="margin-bottom:20px; color:#333;">
                {employee.name}
            </h2>
            <p style="color:#555; font-size:14px; margin-bottom:6px;">
                Check-in tercatat pukul:
            </p>
            <p style="
                font-size:22px;
                font-weight:bold;
                color:#01666b;
                margin-bottom:28px;
            ">
                {check_in_local.strftime("%H:%M")} WIB
            </p>
            <p style="color:#777; font-size:13px; margin-bottom:28px;">
                Silakan langsung menuju mesin MO Scan untuk mulai bekerja.
            </p>
            <a href="/attendance/kiosk" class="btn btn-secondary">
                Kembali ke Kiosk
            </a>
            """
            return self._page("Sudah Absen", body)

        # =====================================================
        # BELUM ABSEN — BUAT HR.ATTENDANCE BARU
        # =====================================================

        # Tutup attendance terbuka sebelumnya (constraint Odoo)
        open_att = request.env["hr.attendance"].sudo().search([
            ("employee_id", "=", employee.id),
            ("check_out", "=", False),
        ], limit=1)

        if open_att:
            open_att.write({"check_out": now_utc})

        # Ambil shift dari employee atau WO hari ini
        shift = getattr(employee, "shift_id", None) or False

        attendance_vals = {
            "employee_id": employee.id,
            "check_in": now_utc,
        }

        if shift:
            attendance_vals["shift_id"] = shift.id

        request.env["hr.attendance"].sudo().create(attendance_vals)

        _logger.info(
            "ATTENDANCE KIOSK: check-in berhasil employee=%s pukul=%s",
            employee.name,
            now_local.strftime("%H:%M"),
        )

        # =====================================================
        # REDIRECT KE HALAMAN SAMBUTAN
        # =====================================================

        return request.redirect(f"/attendance/kiosk/welcome/{employee.id}")

    # =========================================================
    # HALAMAN SAMBUTAN SETELAH ABSEN BERHASIL
    # =========================================================

    @http.route(
        "/attendance/kiosk/welcome/<int:employee_id>",
        type="http",
        auth="user",
        website=False,
        csrf=False,
    )
    def attendance_welcome(self, employee_id, already=None, **kwargs):

        employee = request.env["hr.employee"].sudo().browse(employee_id)
        if not employee.exists():
            return request.redirect("/web#cids=1&menu_id=502&action=760")

        tz = pytz.timezone("Asia/Jakarta")
        now_utc = fields.Datetime.now()
        now_local = pytz.utc.localize(now_utc).astimezone(tz)

        # Ambil waktu check-in ASLI dari hr.attendance, bukan now
        today_utc = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_utc = today_utc + timedelta(days=1)

        existing = request.env["hr.attendance"].sudo().search([
            ("employee_id", "=", employee.id),
            ("check_in", ">=", today_utc),
            ("check_in", "<", tomorrow_utc),
        ], order="check_in asc", limit=1)  # asc → ambil yang pertama hari ini

        if existing:
            checkin_local = pytz.utc.localize(existing.check_in).astimezone(tz)
            time_str = checkin_local.strftime("%H:%M")  # ← jam check-in asli
        else:
            time_str = now_local.strftime("%H:%M")

        date_str = now_local.strftime("%d/%m/%Y")
        hour = now_local.hour

        if 4 <= hour < 11:
            greeting, emoji = "Selamat Pagi", "🌅"
        elif 11 <= hour < 15:
            greeting, emoji = "Selamat Siang", "☀️"
        elif 15 <= hour < 18:
            greeting, emoji = "Selamat Sore", "🌤️"
        else:
            greeting, emoji = "Selamat Malam", "🌙"

        shift = getattr(employee, "shift_id", None)
        shift_html = ""
        if shift:
            shift_html = (
                "<div style='background:#e8f5f5;border-radius:8px;padding:10px 16px;"
                "margin:16px 0;font-size:14px;color:#01666b;'>"
                "&#128336; Shift: <strong>" + (shift.name or "-") + "</strong></div>"
            )

        # ← Bedain pesan berdasarkan already
        if already:
            status_html = (
                "<div style='background:#fff3cd;border-left:4px solid #ffc107;"
                "padding:12px 16px;border-radius:0 8px 8px 0;margin:20px 0;text-align:left;'>"
                "<p style='color:#856404;font-size:14px;margin:0;'>"
                "&#9432; Anda sudah absen masuk hari ini pukul <strong>"
                + time_str + " WIB</strong>.<br/>"
                "Data absensi tidak diubah.</p></div>"
            )
        else:
            status_html = (
                "<div style='background:#f0fff0;border-left:4px solid #28a745;"
                "padding:12px 16px;border-radius:0 8px 8px 0;margin:20px 0;text-align:left;'>"
                "<p style='color:#155724;font-size:14px;margin:0;'>"
                "&#10003; Absensi masuk berhasil dicatat pukul <strong>"
                + time_str + " WIB</strong>.<br/>Semangat bekerja hari ini! &#128170;</p></div>"
            )

        html = (
            "<html><head><meta charset='utf-8'/>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'/>"
            "<title>Selamat Datang</title>"
            "<style>"
            "*{box-sizing:border-box;margin:0;padding:0;}"
            "body{font-family:-apple-system,Arial,sans-serif;background:#01666b;"
            "display:flex;align-items:center;justify-content:center;min-height:100vh;}"
            ".card{background:white;border-radius:16px;padding:50px 40px;"
            "text-align:center;width:420px;box-shadow:0 8px 30px rgba(0,0,0,0.25);}"
            ".btn{display:block;width:100%;padding:15px;border-radius:8px;"
            "font-weight:bold;font-size:16px;margin-top:12px;cursor:pointer;"
            "border:none;color:white;text-decoration:none;}"
            "</style></head><body><div class='card'>"
            "<div style='font-size:56px;margin-bottom:12px;'>" + emoji + " 👋</div>"
            "<h2 style='color:#01666b;margin-bottom:4px;'>" + greeting + ",</h2>"
            "<h2 style='color:#333;margin-bottom:20px;'>" + employee.name + "!</h2>"
            "<p style='color:#777;font-size:13px;margin-bottom:4px;'>" + date_str + "</p>"
            "<p style='font-size:28px;font-weight:bold;color:#01666b;margin-bottom:8px;'>"
            + time_str + " WIB</p>"
            + shift_html
            + status_html
            + "<p style='color:#777;font-size:13px;margin-bottom:24px;'>"
            "Silakan menuju mesin MO Scan untuk memulai pekerjaan.</p>"
            "<button onclick=\"window.location.href='/web#cids=1&menu_id=502&action=760'\" "
            "class='btn' style='background:#01666b;'>"
            "OK &mdash; Kembali ke Kiosk</button>"
            "</div></body></html>"
        )
        return request.make_response(html)



        