# Copyright 2026 Iman Haditssyahputra
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
from odoo import models

_logger = logging.getLogger(__name__)


class ReportAttendanceReportXlsx(models.AbstractModel):
    _name = "report.report_attendance.report_attendance_report_xlsx"
    _description = "Attendance Report XLSX"
    _inherit = "report.report_xlsx.abstract"

    def generate_xlsx_report(self, workbook, data, objects):
        """Fungsi Utama Pembuatan File Excel"""
        # 1. Definisikan Format Desain Warna & Border (Styles)
        format_title = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_size': 14
        })
        format_period = workbook.add_format({
            'align': 'center', 'valign': 'vcenter', 'font_size': 10, 'italic': True
        })
        format_header_main = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter', 
            'bg_color': '#D9E1F2', 'border': 1, 'font_size': 10
        })
        format_header_sub = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter', 
            'bg_color': '#E2EFDA', 'border': 1, 'font_size': 9
        })
        format_cell_center = workbook.add_format({
            'align': 'center', 'valign': 'vcenter', 'border': 1, 'font_size': 10
        })
        format_cell_left = workbook.add_format({
            'align': 'left', 'valign': 'vcenter', 'border': 1, 'font_size': 10
        })
        format_cell_right_float = workbook.add_format({
            'align': 'right', 'valign': 'vcenter', 'border': 1, 'font_size': 10, 'num_format': '#,##0.00'
        })
        format_cell_total = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter', 'bg_color': '#FFF2CC', 'border': 1, 'font_size': 10
        })

        # 2. Buat Worksheet Baru
        ws_name = "Rekap Absensi"
        ws = workbook.add_worksheet(ws_name)
        ws.set_portrait()
        ws.fit_to_pages(1, 0)

        # 3. Tulis Judul Laporan
        ws.merge_range("A1:T1", "LAPORAN REKAPITULASI ABSENSI KARYAWAN", format_title)
        
        date_from_str = objects.date_from.strftime('%d-%m-%Y') if objects.date_from else 'Awal'
        date_to_str = objects.date_to.strftime('%d-%m-%Y') if objects.date_to else 'Sekarang'
        ws.merge_range("A2:T2", f"Periode: {date_from_str} s/d {date_to_str}", format_period)
        
        # 4. Atur Lebar Kolom agar tidak terpotong
        column_widths = {
            'A': 5,   'B': 25,  'C': 20,  'D': 12,  'E': 10,  'F': 8,   'G': 8,   'H': 8,
            'I': 8,   'J': 8,   'K': 8,   'L': 8,   'M': 8,   'N': 8,   'O': 8,   'P': 8,
            'Q': 8,   'R': 8,   'S': 8,   'T': 10,  'U': 10,  'V': 14
        }
        for col, width in column_widths.items():
            ws.set_column(f"{col}:{col}", width)

        # 5. MEMBUAT HEADER BERTINGKAT (MERGE CELLS)
        # Baris ke-4 (Index 3) & Baris ke-5 (Index 4)
        ws.merge_range(3, 0, 4, 0, "No", format_header_main)
        ws.merge_range(3, 1, 4, 1, "Nama Karyawan", format_header_main)
        ws.merge_range(3, 2, 4, 2, "Departement", format_header_main)
        ws.merge_range(3, 3, 4, 3, "Terlambat", format_header_main)
        ws.merge_range(3, 4, 4, 4, "Frekuensi", format_header_main)
        
        # Header Utama yang Melebar ke Samping (Colspan)
        ws.merge_range(3, 5, 3, 6, "ALFA", format_header_main)
        ws.merge_range(3, 7, 3, 8, "IJIN/NSD", format_header_main)
        ws.merge_range(3, 9, 3, 10, "SD", format_header_main)
        ws.merge_range(3, 11, 3, 12, "CUTI", format_header_main)
        ws.merge_range(3, 13, 3, 14, "NON AKTIF", format_header_main)
        ws.merge_range(3, 15, 3, 16, "ABSEN", format_header_main)
        ws.merge_range(3, 17, 3, 18, "LEMBUR", format_header_main)
        
        ws.merge_range(3, 19, 4, 19, "TOTAL ABSEN", format_header_main)

        # Baris Sub-Header (HKB / HKS / HKM) pada Baris ke-5 (Index 4)
        sub_headers = [
            "HKB", "HKS",  # ALFA
            "HKB", "HKS",  # IJIN/NSD
            "HKB", "HKS",  # SD
            "HKB", "HKS",  # CUTI
            "HKB", "HKS",  # NON AKTIF
            "HKB", "HKS",  # ABSEN
            "HKB", "HKM"   # LEMBUR (Kolom terakhir HKM sesuai template XML Anda)
        ]
        
        start_col = 5
        for sub in sub_headers:
            ws.write(4, start_col, sub, format_header_sub)
            start_col += 1

        # Kunci baris header agar tidak ikut bergeser saat di-scroll
        ws.freeze_panes(5, 0)

        # 6. MENGISI DATA LINE REKAP ABSENSI
        row_pos = 5
        idx = 1
        
        for line in objects.results:
            ws.write(row_pos, 0, idx, format_cell_center)
            ws.write(row_pos, 1, line.employee_name or "", format_cell_left)
            ws.write(row_pos, 2, line.departement_name or "", format_cell_left)
            ws.write(row_pos, 3, line.terlambat_hours or 0.0, format_cell_right_float)
            ws.write(row_pos, 4, line.frekuensi_si or 0, format_cell_center)
            
            # Isi Data HKB & HKS
            ws.write(row_pos, 5, line.alfa_hkb or 0, format_cell_center)
            ws.write(row_pos, 6, line.alfa_hks or 0, format_cell_center)
            
            ws.write(row_pos, 7, line.izin_hkb or 0, format_cell_center)
            ws.write(row_pos, 8, line.izin_hks or 0, format_cell_center)
            
            ws.write(row_pos, 9, line.sakit_hkb or 0, format_cell_center)
            ws.write(row_pos, 10, line.sakit_hks or 0, format_cell_center)
            
            ws.write(row_pos, 11, line.cuti_hkb or 0, format_cell_center)
            ws.write(row_pos, 12, line.cuti_hks or 0, format_cell_center)
            
            ws.write(row_pos, 13, line.non_aktif_hkb or 0, format_cell_center)
            ws.write(row_pos, 14, line.non_aktif_hks or 0, format_cell_center)
            
            ws.write(row_pos, 15, line.absen_hkb or 0, format_cell_center)
            ws.write(row_pos, 16, line.absen_hks or 0, format_cell_center)
            
            # Isi Data Lembur (Float desimal)
            ws.write(row_pos, 17, line.lembur_hkb or 0.0, format_cell_right_float)
            ws.write(row_pos, 18, line.lembur_hkm or 0.0, format_cell_right_float)
            
            # Total Absen Kumulatif (Diberi format warna khusus penanda total)
            ws.write(row_pos, 19, line.total_absen or 0, format_cell_total)
            
            row_pos += 1
            idx += 1
