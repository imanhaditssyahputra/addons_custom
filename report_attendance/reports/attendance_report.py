# Copyright 2026 Iman Haditssyahputra
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import pytz
from datetime import datetime

from odoo import api, fields, models, tools


class ReportAttendanceView(models.Model):
    """Model khusus untuk membuat PostgreSQL VIEW di database"""
    _name = "report.attendance.view"
    _description = "SQL View Rekap Absensi Bulanan"
    _auto = False
    _order = "date DESC, department_id, employee_id"

    id = fields.Integer(string="ID", readonly=True)
    employee_id = fields.Many2one(comodel_name="hr.employee", string="Karyawan", readonly=True)
    department_id = fields.Many2one(comodel_name="hr.department", string="Departemen", readonly=True)
    date = fields.Date(string="Bulan Periode", readonly=True)
    
    terlambat_jam = fields.Float(string="Terlambat (Jam)", readonly=True)
    frekuensi_terlambat = fields.Integer(string="Frekuensi Terlambat", readonly=True)

    alfa_hkb = fields.Integer(string="Alfa HKB", readonly=True)
    alfa_hks = fields.Integer(string="Alfa HKS", readonly=True)
    
    izin_hkb = fields.Integer(string="Izin HKB", readonly=True)
    izin_hks = fields.Integer(string="Izin HKS", readonly=True)
    
    sakit_hkb = fields.Integer(string="Sakit HKB", readonly=True)
    sakit_hks = fields.Integer(string="Sakit HKS", readonly=True)
    
    cuti_hkb = fields.Integer(string="Cuti HKB", readonly=True)
    cuti_hks = fields.Integer(string="Cuti HKS", readonly=True)

    non_aktif_hkb = fields.Integer(string="Non Aktif HKB", readonly=True)
    non_aktif_hks = fields.Integer(string="Non Aktif HKS", readonly=True)

    absen_hkb = fields.Integer(string="Absen HKB", readonly=True)
    absen_hks = fields.Integer(string="Absen HKS", readonly=True)
    totalan_absen = fields.Integer(string="Totalan Absen", readonly=True)

    lembur_hkb = fields.Float(string="Lembur HKB", readonly=True)
    lembur_hkm = fields.Float(string="Lembur HKM", readonly=True)

    def init(self):
            tools.drop_view_if_exists(self.env.cr, self._table)
            self.env.cr.execute(f"""
                CREATE OR REPLACE VIEW {self._table} AS (
                    WITH data_raw AS (
                        -- 1. AMBIL DATA DARI TRANSAKSI ABSENSI REGULER / LEMBUR
                        SELECT 
                            att.employee_id,
                            (att.check_in + interval '7 hours')::date AS tanggal,
                            att.check_in,
                            att.shift_id,
                            att.total_lembur,
                            'hadir'::varchar AS status_absen 
                        FROM hr_attendance att
    
                        UNION ALL
    
                        -- 2. AMBIL DATA DARI TIME OFF (HR.LEAVE) & BREAKDOWN PER HARI
                        SELECT 
                            l.employee_id,
                            dt.tanggal::date AS tanggal,
                            NULL::timestamp AS check_in,
                            NULL::integer AS shift_id,
                            0::numeric AS total_lembur,
                            CASE 
                                WHEN lt.work_entry_type_id IN (SELECT id FROM hr_work_entry_type WHERE code = 'LEAVE110') THEN 'sakit'::varchar
                                WHEN lt.work_entry_type_id IN (SELECT id FROM hr_work_entry_type WHERE code = 'LEAVE120') THEN 'izin'::varchar
                                ELSE 'cuti'::varchar
                            END AS status_absen
                        FROM hr_leave l
                        JOIN hr_leave_type lt ON l.holiday_status_id = lt.id
                        JOIN LATERAL generate_series(l.date_from::date, l.date_to::date, '1 day'::interval) AS dt(tanggal) ON TRUE
                        WHERE l.state = 'validate'
                    ),
                    
                    -- CTE BARU: INTEGRASI KONTRAK UNTUK MENENTUKAN STATUS NON AKTIF HARIAN
                    data_dengan_kontrak AS (
                        SELECT 
                            dr.*,
                            CASE 
                                WHEN con.date_end IS NOT NULL AND dr.tanggal > con.date_end THEN 'non_aktif'::varchar
                                ELSE dr.status_absen
                            END AS status_absen_aktual
                        FROM data_raw dr
                        LEFT JOIN hr_contract con ON con.employee_id = dr.employee_id AND con.state = 'open'
                    ),
                    
                    kalkulasi_harian AS (
                        SELECT 
                            dk.employee_id,
                            dk.tanggal,
                            DATE_TRUNC('month', dk.tanggal)::date AS bulan_periode,
                            dk.status_absen_aktual,
                            dk.total_lembur,
                            CASE 
                                WHEN dk.check_in IS NOT NULL AND ms.start_time IS NOT NULL THEN
                                    EXTRACT(EPOCH FROM ((dk.check_in::time + interval '7 hours') - (CAST('00:00:00' AS time) + (ms.start_time * interval '1 hour'))))
                                ELSE 0 
                            END AS selisih_detik
                        FROM data_dengan_kontrak dk
                        LEFT JOIN eran_master_shift ms ON dk.shift_id = ms.id
                    )
                    
                    -- PROSES GROUP BY BERDASARKAN BULAN PERIODE DAN KARYAWAN
                    SELECT 
                        ROW_NUMBER() OVER (ORDER BY kh.bulan_periode DESC, e.department_id, kh.employee_id) AS id,
                        kh.employee_id AS employee_id,
                        e.department_id AS department_id,
                        kh.bulan_periode AS date,
                        
                        -- Menggunakan TRUNC pada hasil akhir SUM agar jam terlambat bersih tanpa detik desimal panjang
                        TRUNC(SUM(CASE WHEN kh.selisih_detik >= 60 THEN kh.selisih_detik / 3600.0 ELSE 0 END)::numeric, 2)::float AS terlambat_jam,
                        SUM(CASE WHEN kh.selisih_detik >= 60 THEN 1 ELSE 0 END) AS frekuensi_terlambat,
    
                        -- HITUNG TOTAL HARI KETIDAKHADIRAN DALAM 1 BULAN
                        SUM(CASE WHEN kh.status_absen_aktual = 'alfa' AND EXTRACT(ISODOW FROM kh.tanggal) BETWEEN 1 AND 5 THEN 1 ELSE 0 END) AS alfa_hkb,
                        SUM(CASE WHEN kh.status_absen_aktual = 'alfa' AND EXTRACT(ISODOW FROM kh.tanggal) = 6 THEN 1 ELSE 0 END) AS alfa_hks,
                        
                        SUM(CASE WHEN kh.status_absen_aktual = 'izin' AND EXTRACT(ISODOW FROM kh.tanggal) BETWEEN 1 AND 5 THEN 1 ELSE 0 END) AS izin_hkb,
                        SUM(CASE WHEN kh.status_absen_aktual = 'izin' AND EXTRACT(ISODOW FROM kh.tanggal) = 6 THEN 1 ELSE 0 END) AS izin_hks,
                        
                        SUM(CASE WHEN kh.status_absen_aktual = 'sakit' AND EXTRACT(ISODOW FROM kh.tanggal) BETWEEN 1 AND 5 THEN 1 ELSE 0 END) AS sakit_hkb,
                        SUM(CASE WHEN kh.status_absen_aktual = 'sakit' AND EXTRACT(ISODOW FROM kh.tanggal) = 6 THEN 1 ELSE 0 END) AS sakit_hks,
                        
                        SUM(CASE WHEN kh.status_absen_aktual = 'cuti' AND EXTRACT(ISODOW FROM kh.tanggal) BETWEEN 1 AND 5 THEN 1 ELSE 0 END) AS cuti_hkb,
                        SUM(CASE WHEN kh.status_absen_aktual = 'cuti' AND EXTRACT(ISODOW FROM kh.tanggal) = 6 THEN 1 ELSE 0 END) AS cuti_hks,
    
                        -- FIELD BARU SQL: HITUNG NON AKTIF BERDASARKAN KONTRAK
                        SUM(CASE WHEN kh.status_absen_aktual = 'non_aktif' AND EXTRACT(ISODOW FROM kh.tanggal) BETWEEN 1 AND 5 THEN 1 ELSE 0 END) AS non_aktif_hkb,
                        SUM(CASE WHEN kh.status_absen_aktual = 'non_aktif' AND EXTRACT(ISODOW FROM kh.tanggal) = 6 THEN 1 ELSE 0 END) AS non_aktif_hks,
    
                        -- FIELD BARU SQL: ABSEN HKB & HKS (Gabungan alfa, izin, sakit, cuti, non_aktif)
                        SUM(CASE WHEN kh.status_absen_aktual IN ('alfa', 'izin', 'sakit', 'cuti', 'non_aktif') AND EXTRACT(ISODOW FROM kh.tanggal) BETWEEN 1 AND 5 THEN 1 ELSE 0 END) AS absen_hkb,
                        SUM(CASE WHEN kh.status_absen_aktual IN ('alfa', 'izin', 'sakit', 'cuti', 'non_aktif') AND EXTRACT(ISODOW FROM kh.tanggal) = 6 THEN 1 ELSE 0 END) AS absen_hks,
    
                        -- FIELD BARU SQL: TOTALAN ABSEN (Akumulasi Absen Hari 1-6)
                        SUM(CASE WHEN kh.status_absen_aktual IN ('alfa', 'izin', 'sakit', 'cuti', 'non_aktif') AND EXTRACT(ISODOW FROM kh.tanggal) BETWEEN 1 AND 6 THEN 1 ELSE 0 END) AS totalan_absen,
    
                        -- HITUNG TOTAL JAM LEMBUR DALAM 1 BULAN
                        SUM(CASE WHEN EXTRACT(ISODOW FROM kh.tanggal) BETWEEN 1 AND 5 THEN COALESCE(kh.total_lembur, 0) ELSE 0 END) AS lembur_hkb,
                        SUM(CASE WHEN EXTRACT(ISODOW FROM kh.tanggal) = 7 THEN COALESCE(kh.total_lembur, 0) ELSE 0 END) AS lembur_hkm
    
                    FROM kalkulasi_harian kh
                    JOIN hr_employee e ON e.id = kh.employee_id
                    GROUP BY kh.bulan_periode, e.department_id, kh.employee_id
                )
            """)
    

class AttendanceView(models.TransientModel):
    """Model penampung data sementara untuk ditarik ke XML/Excel"""
    _name = "attendance.view"
    _description = "Attendance Summary Lines"
    _order = "employee_name ASC"

    employed_id = fields.Many2one(comodel_name="hr.employee", string="Karyawan")
    employee_name = fields.Char(string="Nama Karyawan")
    departement_id = fields.Many2one(comodel_name="hr.department", string="Departemen")
    departement_name = fields.Char(string="Nama Departemen")
    
    terlambat_hours = fields.Float(string="Terlambat (Jam)")
    frekuensi_si = fields.Integer(string="Frekuensi Terlambat")
    
    alfa_hkb = fields.Integer(string="Alfa HKB")
    alfa_hks = fields.Integer(string="Alfa HKS")
    izin_hkb = fields.Integer(string="Ijin HKB")
    izin_hks = fields.Integer(string="Ijin HKS")
    sakit_hkb = fields.Integer(string="Sakit HKB")
    sakit_hks = fields.Integer(string="Sakit HKS")
    cuti_hkb = fields.Integer(string="Cuti HKB")
    cuti_hks = fields.Integer(string="Cuti HKS")
    non_aktif_hkb = fields.Integer(string="Non Aktif HKB")
    non_aktif_hks = fields.Integer(string="Non Aktif HKS")
    absen_hkb = fields.Integer(string="Absen HKB")
    absen_hks = fields.Integer(string="Absen HKS")
    total_absen = fields.Integer(string="Total Absen")
    lembur_hkb = fields.Float(string="Lembur HKB")
    lembur_hkm = fields.Float(string="Lembur HKM")

class AttendanceReport(models.TransientModel):
    _name = "report.attendance.report"
    _description = "Attendance Report Wizard"

    date_from = fields.Date(string="Tanggal Mulai", required=True)
    date_to = fields.Date(string="Tanggal Selesai", required=True)
    employed_id = fields.Many2one(comodel_name="hr.employee", string="Karyawan")
    departement_id = fields.Many2one(comodel_name="hr.department", string="Departemen")
    results = fields.Many2many(comodel_name="attendance.view", compute="_compute_results", help="Data rekap yang akan ditarik ke laporan",)

    def _compute_results(self):
        self.ensure_one()
        ReportLine = self.env["attendance.view"]

        # Atur filter pencarian berdasarkan inputan user di wizard
        domain = []
        if self.date_from:
            domain.append(('date', '>=', self.date_from))
        if self.date_to:
            domain.append(('date', '<=', self.date_to))
        if self.employed_id:
            domain.append(('employee_id', '=', self.employed_id.id))
        if self.departement_id:
            domain.append(('department_id', '=', self.departement_id.id))

        # Gunakan .sudo() untuk menjamin data terbaca tanpa terhalang aturan hak akses security
        view_data = self.env['report.attendance.view'].sudo().search(domain)
        
        new_results = []
        for line in view_data:
            line_data = {
                'employed_id': line.employee_id.id,
                'employee_name': line.employee_id.name,
                'departement_id': line.department_id.id,
                'departement_name': line.department_id.name or '-',
                'terlambat_hours': line.terlambat_jam,
                'frekuensi_si': line.frekuensi_terlambat,
                'alfa_hkb': line.alfa_hkb,
                'alfa_hks': line.alfa_hks,
                'izin_hkb': line.izin_hkb,
                'izin_hks': line.izin_hks,
                # Tambahkan pemetaan kolom sakit_hkb dan sakit_hks agar data SD muncul di tabel
                'sakit_hkb': line.sakit_hkb,
                'sakit_hks': line.sakit_hks,
                'cuti_hkb': line.cuti_hkb,
                'cuti_hks': line.cuti_hks,
                'non_aktif_hkb': line.non_aktif_hkb,
                'non_aktif_hks': line.non_aktif_hks,
                'absen_hkb': line.absen_hkb,
                'absen_hks': line.absen_hks,
                'total_absen': line.totalan_absen,
                'lembur_hkb': line.lembur_hkb,
                'lembur_hkm': line.lembur_hkm,
            }
            # 🌟 PERBAIKAN UTAMA: Ganti .new() menjadi .sudo().create()
            # Ini akan menyimpan baris data sementara ke database secara nyata
            created_line = ReportLine.sudo().create(line_data)
            new_results.append(created_line.id)
            
        # 🌟 PERBAIKAN KEDUA: Masukkan data menggunakan format perintah relasi Odoo (6, 0, [ID])
        self.sudo().results = [(6, 0, new_results)]

    
    def print_report(self, report_type="qweb"):
        self.ensure_one()
        # Jika dipanggil dari JavaScript, pastikan kita mengambil ID data yang tepat
        active_id = self._context.get('active_id') or self.id
        report = self.browse(active_id)
        
        action = (
            report_type == "xlsx"
            and self.env.ref("report_attendance.action_attendance_report_xlsx")
            or self.env.ref("report_attendance.action_attendance_report_pdf")
        )
        # Melempar objek 'report' yang sudah terisi tanggal dengan benar ke dalam action cetak
        return action.report_action(report, config=False)


    def _get_html(self):
        result = {}
        rcontext = {}
        report = self.browse(self._context.get("active_id"))
        if report:
            rcontext["o"] = report
            result["html"] = self.env["ir.qweb"]._render("report_attendance.report_attendance_report_html", rcontext)
        return result

    @api.model
    def get_html(self, given_context=None):
        return self.with_context(**(given_context or {}))._get_html()
