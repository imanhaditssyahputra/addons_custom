# Copyright 2026 Iman Haditssyahputra
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Report Attendance",
    "summary": "Add attendance report on Attendance Reporting.",
    "version": "16.0.1.0.2",
    "category": "Attendance",
    "author": "Iman Haditssyahputra",
    "license": "AGPL-3",
    "depends": ["hr", "hr_attendance", "report_xlsx_helper"],
    "data": [
        "security/ir.model.access.csv",
        "data/paper_format.xml",
        "data/report_data.xml",
        "reports/attendance_report.xml",
        "wizard/report_attendance_wizard_view.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "report_attendance/static/src/css/**/*",
            "report_attendance/static/src/js/**/*",
        ]
    },
    "installable": True,
}
