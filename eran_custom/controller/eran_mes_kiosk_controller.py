import logging
import pytz
from odoo import http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)


class EranAttendanceKioskController(http.Controller):

    def _native_kiosk_url(self):
        action = request.env.ref(
            "hr_attendance.hr_attendance_action_kiosk_mode",
            raise_if_not_found=False,
        )
        if not action:
            return "/web"
        company_id = request.env.company.id
        return f"/web#action={action.id}&cids={company_id}"

    @http.route(
        "/attendance/kiosk",
        type="http",
        auth="user",
        website=False,
        csrf=False,
    )
    def attendance_kiosk(self, **kwargs):
        return request.redirect(self._native_kiosk_url())

    @http.route(
        [
            "/attendance/kiosk/welcome/<int:employee_id>",
            "/attendance/welcome/<int:employee_id>",
        ],
        type="http",
        auth="user",
        website=False,
        csrf=False,
    )
    def attendance_welcome(self, employee_id, already=None, **kwargs):

        employee = request.env["hr.employee"].sudo().browse(employee_id)
        if not employee.exists():
            return request.redirect(self._native_kiosk_url())

        tz = pytz.timezone("Asia/Jakarta")
        now_utc = fields.Datetime.now()
        now_local = pytz.utc.localize(now_utc).astimezone(tz)

        today_utc, tomorrow_utc = request.env["hr.employee"]._eran_jakarta_day_bounds(now_utc)

        existing = request.env["hr.attendance"].sudo().search([
            ("employee_id", "=", employee.id),
            ("check_in", ">=", today_utc),
            ("check_in", "<", tomorrow_utc),
        ], order="check_in asc", limit=1)

        if existing:
            checkin_local = pytz.utc.localize(existing.check_in).astimezone(tz)
            time_str = checkin_local.strftime("%H:%M")
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

        kiosk_url = self._native_kiosk_url()
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
            "<a href='" + kiosk_url + "' "
            "class='btn' style='background:#01666b;display:block;text-decoration:none;'>"
            "OK &mdash; Kembali ke Kiosk</a>"
            "</div></body></html>"
        )
        return request.make_response(html)
