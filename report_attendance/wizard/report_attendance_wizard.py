# Copyright 2019 Ecosoft Co., Ltd. (http://ecosoft.co.th)
# Copyright 2026 Iman Haditssyahputra
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval


class AttendanceReportWizard(models.TransientModel):
    _name = "attendance.report.wizard"
    _description = "Attendance Report Wizard"

    date_from = fields.Date(string="Start Date")
    date_to = fields.Date(string="End Date")
    employed_id = fields.Many2one(
        comodel_name="hr.employee", string="Employees"
    )
    # Catatan: Di file report.attendance.report, departement_id bertipe Many2one.
    # Kita ubah di sini menjadi Many2one agar pencarian data SQL sinkron dan tidak eror.
    departement_id = fields.Many2one(
        comodel_name="hr.department", string="Department"
    )

    def button_export_html(self):
        self.ensure_one()
        action = self.env.ref("report_attendance.action_report_attendance_report_html")
        vals = action.sudo().read()[0]
        context = vals.get("context", {})
        if context:
            context = safe_eval(context)
        
        model = self.env["report.attendance.report"]
        report = model.create(self._prepare_attendance_report())
        
        context["active_id"] = report.id
        context["active_ids"] = report.ids
        vals["context"] = context
        return vals

    def button_export_pdf(self):
        self.ensure_one()
        return self._export("qweb")

    def button_export_xlsx(self):
        self.ensure_one()
        return self._export("xlsx")

    def _prepare_attendance_report(self):
        """Menyiapkan data filter baru untuk model report.attendance.report"""
        self.ensure_one()
        return {
            "date_from": self.date_from,
            "date_to": self.date_to or fields.Datetime.now(),
            "employed_id": self.employed_id.id if self.employed_id else False,
            "departement_id": self.departement_id.id if self.departement_id else False,
        }

    def _export(self, report_type):
        """Mengarahkan pembuatan laporan ke model report absensi yang baru"""
        model = self.env["report.attendance.report"]
        report = model.create(self._prepare_attendance_report())
        return report.print_report(report_type)
