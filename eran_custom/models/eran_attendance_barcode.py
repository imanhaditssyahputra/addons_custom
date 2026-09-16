from pyparsing import line

from odoo import models, fields, api
import logging
from datetime import timedelta
from collections import Counter
from odoo.exceptions import UserError
from odoo import http
from odoo.http import request
import pytz

_logger = logging.getLogger(__name__)

class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"
 
    def name_get(self):
        _logger.warning("=== GET WORKORDER ===")

        result = []

        for rec in self:

            mo = rec.production_id.name or "-"
            wo = rec.name or "-"
            product = rec.production_id.product_id.display_name or "-"
            wc = rec.workcenter_id.name or "-"

            name = f"{mo} | {wo} | {product} | {wc}"

            result.append((rec.id, name))

        return result

class BarcodeScanLog(models.Model):
    _name = "barcode.scan.log"
    _description = "Barcode Scan Log"
    _order = "scan_datetime desc"

    employee_id = fields.Many2one(
        "hr.employee",
        required=True
    )

    barcode = fields.Char(
        related="employee_id.barcode",
        store=True
    )

    scan_datetime = fields.Datetime(
        required=True
    )


class MesScanApproval(models.Model):
    _name = "mes.scan.approval"
    _description = "MES Scan Approval"
    _order = "scan_time desc"

    # =========================
    # OPERATOR
    # =========================

    employee_id = fields.Many2one(
        "hr.employee",
        required=True
    )

    barcode = fields.Char(
        related="employee_id.barcode",
        store=True
    )

    shift_id = fields.Many2one(
        "eran.master.shift",
        string="Shift"
    )

    workcenter_id = fields.Many2one(
        "mrp.workcenter",
        string="Work Center"
    )

    # =========================
    # SCAN
    # =========================

    check_in = fields.Datetime()

    scan_time = fields.Datetime()

    # =========================
    # MES
    # =========================

    line_ids = fields.One2many(
        "mes.scan.approval.line",
        "approval_id",
        string="Work Orders"
    )

    # =========================
    # PRODUKSI
    # =========================

    qty_target = fields.Float()

    qty_actual = fields.Float(default=0)

    sph = fields.Integer()


    # ========================
    # WORK ORDER
    # ========================

    workorder_info = fields.Html(
        string="Today's Assignment",
        compute="_compute_workorder_info",
        sanitize=False,
    )

    def action_open_my_mo_history(self):
        """Buka riwayat MO hanya untuk operator pada hasil scan ini."""

        self.ensure_one()
        employee = self.employee_id.sudo()

        return {
            "type": "ir.actions.act_window",
            "name": "Riwayat MO - %s" % (employee.name or "-"),
            "res_model": "mes.scan.approval",
            "view_mode": "tree,form",
            "domain": [("employee_id", "=", employee.id)],
            "context": {
                "group_by": "scan_time:day",
                "default_employee_id": employee.id,
            },
        }

    def _render_downtime_html(self, line):
        if not line.downtime_ids:
            return ""

        items = ""
        for d in line.downtime_ids.sorted("start_time", reverse=True):
            start_str = self._format_downtime_time(d.start_time)
            end_str = self._format_downtime_time(d.end_time)
            note_str = f"<br/><i>Catatan: {d.note}</i>" if d.note else ""

            items += f"""
            <li style="margin-bottom:6px;">
                <b>{d.loss_id.name}</b> —
                dari {start_str} sampai {end_str}
                {note_str}
            </li>
            """

        return f"""
        <div style="margin-top:8px;">
            <b>Riwayat Downtime</b>
            <ul style="padding-left:18px;margin:4px 0 0 0;">
                {items}
            </ul>
        </div>
        """

    def _render_productivity_period_html(self, line):
        start_time, end_time = self._get_productivity_period(line)

        if not start_time:
            return ""

        start_str = self._format_downtime_time(start_time)
        end_str = self._format_downtime_time(end_time)

        return f"""
        <div style="margin-top:8px;">
            <b>Productivity Period</b>

            <div style="margin:4px 0 0 0;">
                {start_str} sampai {end_str}
            </div>  
        </div>
        """

    def _get_productivity_period(self, line):
        if line.state == "running":
            return line.start_time, False

        return line.start_time, line.stop_time

    def _format_downtime_time(self, value):
        if not value:
            return "-"

        tz_record = self.with_context(tz=self.env.user.tz or "Asia/Jakarta")
        local_time = fields.Datetime.context_timestamp(tz_record, value)
        return local_time.strftime("%d/%m/%Y %H:%M")
    
    @api.depends(
        "check_in",
        "employee_id",
        "line_ids",
        "line_ids.state",
        "line_ids.start_time",
        "line_ids.stop_time",
        "line_ids.workorder_id.time_ids.date_start",
        "line_ids.workorder_id.time_ids.date_end",
        "line_ids.downtime_ids",
        "line_ids.downtime_ids.loss_id",
        "line_ids.downtime_ids.note",
        "line_ids.downtime_ids.start_time",
        "line_ids.downtime_ids.end_time",
        "line_ids.edit_request_ids",
        "line_ids.edit_request_ids.state",
        "line_ids.has_pending_edit",
    )
    def _compute_workorder_info(self):

        for rec in self:

            # =====================================================
            # BELUM CHECK IN
            # =====================================================

            if not rec.check_in:
                rec.workorder_info = ""
                continue

            # =====================================================
            # SEMUA DATA DIBACA DENGAN SUDO
            # Supaya user MES / Leader tidak perlu akses penuh
            # ke Manufacturing / HR.
            # =====================================================

            rec_sudo = rec.sudo()

            lines = rec_sudo.line_ids.sorted("sequence")

            # =====================================================
            # TIDAK ADA WORK ORDER
            # =====================================================

            if not lines:
                rec.workorder_info = (
                    "<p style='color:#999;'>"
                    "Tidak ada Work Order untuk hari ini."
                    "</p>"
                )
                continue

            # =====================================================
            # PISAHKAN ACTIVE DAN DONE
            # =====================================================

            active_lines = lines.filtered(
                lambda l: l.state != "done"
            )

            done_lines = lines.filtered(
                lambda l: l.state == "done"
            )

            html = []

            # =====================================================
            # SECTION ACTIVE
            # =====================================================

            total_active = len(active_lines)

            for idx, line in enumerate(active_lines, start=1):

                # -------------------------------------------------
                # SELALU DEFINISIKAN line_sudo DI DALAM LOOP
                # -------------------------------------------------

                line_sudo = line.sudo()
                wo = line_sudo.workorder_id.sudo()

                # -------------------------------------------------
                # DATA WORK ORDER
                # -------------------------------------------------

                leader = (
                    wo.leader_id.sudo().name
                    if wo.leader_id
                    else "-"
                )

                workcenter_name = (
                    wo.workcenter_id.sudo().name
                    if wo.workcenter_id
                    else "-"
                )

                production_name = (
                    wo.production_id.sudo().name
                    if wo.production_id
                    else "-"
                )

                product_name = (
                    wo.product_id.sudo().display_name
                    if wo.product_id
                    else "-"
                )

                # =================================================
                # CEK APAKAH WO BELUM BOLEH START
                # =================================================

                if (
                    line_sudo.state != "running"
                    and not line_sudo.can_start
                ):

                    html.append(f"""
                    <div style="
                        border:1px solid #dcdcdc;
                        border-radius:8px;
                        padding:12px;
                        margin-bottom:12px;
                        background:#f8f9fa;
                    ">

                        <div style="
                            display:flex;
                            justify-content:space-between;
                            align-items:center;
                            gap:12px;
                        ">

                            <h4 style="
                                margin:0;
                                color:#0b72b9;
                            ">
                                📍 {workcenter_name}
                                ({idx}/{total_active})
                            </h4>

                            <span style="
                                display:inline-block;
                                padding:3px 10px;
                                border-radius:12px;
                                background:#e9ecef;
                                color:#555;
                                font-size:12px;
                                font-weight:bold;
                            ">
                                {line_sudo.state.upper()}
                            </span>

                        </div>

                    </div>
                    """)

                    continue

                # =================================================
                # ACTION BUTTON
                #
                # RUNNING  -> STOP
                # CAN START -> START
                # =================================================

                action_button = ""

                if line_sudo.state == "running":

                    # Cari bagian tombol STOP (sekitar line 360-390), ganti href jadi onclick:
                    action_button = f"""
                    <div style="text-align:right;margin-top:14px;">
                        <button
                            onclick="mesStop({line_sudo.id})"
                            style="display:inline-block;padding:8px 16px;background:#dc3545;
                            color:white;border-radius:6px;font-size:13px;font-weight:bold;
                            border:none;cursor:pointer;">
                            ⏹️ STOP
                        </button>
                    </div>
                    """

                elif line_sudo.can_start:
                    action_button = f"""
                    <div style="text-align:right;margin-top:14px;">
                        <button
                            onclick="mesStart({line_sudo.id}, this)"
                            style="display:inline-block;padding:8px 16px;background:#28a745;
                            color:white;border-radius:6px;font-size:13px;font-weight:bold;
                            border:none;cursor:pointer;">
                            ▶️ START
                        </button>
                    </div>
                    """

                # =================================================
                # HTML ACTIVE
                # =================================================

                html.append(f"""
                <div style="
                    border:1px solid #28a745;
                    border-radius:8px;
                    padding:12px;
                    margin-bottom:12px;
                    background:#f4fbf6;
                ">

                    <div style="
                        display:flex;
                        justify-content:space-between;
                        align-items:center;
                    ">

                        <h4 style="
                            margin:0;
                            color:#0b72b9;
                        ">
                            📍 {workcenter_name}
                            ({idx}/{total_active})
                        </h4>

                        <span style="
                            background:#28a745;
                            color:white;
                            padding:2px 10px;
                            border-radius:12px;
                            font-size:12px;
                            font-weight:bold;
                        ">
                            {line_sudo.state.upper()}
                        </span>

                    </div>

                    <p>
                        <b>Leader :</b> {leader}
                    </p>

                    <p>
                        <b>Manufacturing Order</b><br/>
                        {production_name}
                    </p>

                    <p>
                        <b>Work Order</b><br/>
                        {wo.name or "-"}
                    </p>

                    <p>
                        <b>Product</b><br/>
                        {product_name}
                    </p>

                    <p>
                        <b>Target</b><br/>
                        {line_sudo.qty_target}
                    </p>

                    <p>
                        <b>Output</b><br/>
                        {line_sudo.qty_actual}
                    </p>

                    <p>
                        <b>Status</b><br/>
                        {line_sudo.state.upper()}
                    </p>

                    {rec_sudo._render_downtime_html(line_sudo)}

                    {rec_sudo._render_productivity_period_html(line_sudo)}

                    {action_button}

                </div>
                """)

            # =====================================================
            # SEMUA WO AKTIF SUDAH SELESAI
            # =====================================================

            if not active_lines:

                html.append("""
                <p style="
                    color:#28a745;
                    font-weight:bold;
                    margin-top:12px;
                ">
                    🎉 Semua Work Order hari ini sudah selesai.
                </p>
                """)

            # =====================================================
            # SECTION DONE
            #
            # EDIT HANYA MUNCUL DI SINI
            # Jadi selama WO belum DONE,
            # tombol Edit TIDAK AKAN MUNCUL.
            # =====================================================

            if done_lines:

                total_done = len(done_lines)

                html.append("""
                <hr style="
                    margin:24px 0;
                    border:none;
                    border-top:2px dashed #ccc;
                " />

                <h3 style="
                    color:#555;
                    margin-bottom:12px;
                ">
                    Sudah Selesai
                </h3>
                """)

                # =================================================
                # LOOP SETIAP WO YANG SUDAH DONE
                # =================================================

                for idx, line in enumerate(done_lines, start=1):

                    line_sudo = line.sudo()
                    wo = line_sudo.workorder_id.sudo()

                    # -------------------------------------------------
                    # DATA WORK ORDER
                    # -------------------------------------------------

                    leader = (
                        wo.leader_id.sudo().name
                        if wo.leader_id
                        else "-"
                    )

                    workcenter_name = (
                        wo.workcenter_id.sudo().name
                        if wo.workcenter_id
                        else "-"
                    )

                    production_name = (
                        wo.production_id.sudo().name
                        if wo.production_id
                        else "-"
                    )

                    product_name = (
                        wo.product_id.sudo().display_name
                        if wo.product_id
                        else "-"
                    )

                    # =================================================
                    # EDIT BUTTON
                    #
                    # HANYA UNTUK WO DONE
                    #
                    # waiting  -> Menunggu persetujuan edit
                    # approved -> Edit sudah disetujui
                    # rejected / belum ada request -> tombol Edit
                    # =================================================

                    edit_button = ""
                    latest_request = line_sudo.edit_request_ids.sorted(
                        "create_date", reverse=True
                    )[:1]

                    if latest_request and latest_request.state == "waiting":
                        edit_status_text = "⏳ Menunggu persetujuan edit"
                        edit_status_color = "#888"
                        edit_button = f"""
                        <div style="text-align:right; margin-top:10px;">
                            <span style="font-size:12px; color:{edit_status_color};">
                                {edit_status_text}
                            </span>
                        </div>
                        """

                    elif latest_request and latest_request.state == "approved":
                        edit_status_text = "✅ Edit sudah disetujui"
                        edit_status_color = "#28a745"
                        edit_button = f"""
                        <div style="text-align:right; margin-top:10px;">
                            <span style="font-size:12px; color:{edit_status_color};">
                                {edit_status_text}
                            </span>
                        </div>
                        """

                    else:

                        edit_button = f"""
                        <div style="text-align:right;margin-top:10px;">
                            <button
                                data-mes-edit="{line_sudo.id}"
                                style="display:inline-block;padding:6px 14px;background:#6c757d;
                                color:white;border-radius:5px;border:none;font-size:12px;
                                font-weight:bold;cursor:pointer;">
                                ✏️ Edit
                            </button>
                        </div>
                        """

                    # =================================================
                    # HTML DONE
                    # =================================================

                    html.append(f"""
                    <div style="
                        border:1px solid #28a745;
                        border-radius:8px;
                        padding:12px;
                        margin-bottom:12px;
                        background:#f4fbf6;
                    ">

                        <div style="
                            display:flex;
                            justify-content:space-between;
                            align-items:center;
                        ">

                            <h4 style="
                                margin:0;
                                color:#0b72b9;
                            ">
                                📍 {workcenter_name}
                                ({idx}/{total_done})
                            </h4>

                            <span style="
                                background:#28a745;
                                color:white;
                                padding:2px 10px;
                                border-radius:12px;
                                font-size:12px;
                                font-weight:bold;
                            ">
                                ✅ SELESAI
                            </span>

                        </div>

                        <p>
                            <b>Leader :</b> {leader}
                        </p>

                        <p>
                            <b>Manufacturing Order</b><br/>
                            {production_name}
                        </p>

                        <p>
                            <b>Work Order</b><br/>
                            {wo.name or "-"}
                        </p>

                        <p>
                            <b>Product</b><br/>
                            {product_name}
                        </p>

                        <p>
                            <b>Target</b><br/>
                            {line_sudo.qty_target}
                        </p>

                        <p>
                            <b>Output</b><br/>
                            {line_sudo.qty_actual}
                        </p>

                        <p>
                            <b>Status</b><br/>
                            {line_sudo.state.upper()}
                        </p>

                        {rec_sudo._render_downtime_html(line_sudo)}

                        {rec_sudo._render_productivity_period_html(line_sudo)}

                        {edit_button}

                    </div>
                    """)

                    html.append("""
                    <script>
                    function mesScanEditRequest(lineId, btn) {

                        // Cegah double click
                        btn.disabled = true;
                        btn.innerText = '⏳ Memproses...';

                        // ── POPUP KONFIRMASI ──────────────────────────────────
                        const backdrop = document.createElement('div');
                        Object.assign(backdrop.style, {
                            position:'fixed', inset:'0', background:'rgba(0,0,0,0.55)',
                            zIndex:'99999', display:'flex', alignItems:'center', justifyContent:'center'
                        });

                        const box = document.createElement('div');
                        Object.assign(box.style, {
                            background:'white', borderRadius:'12px', padding:'28px 24px',
                            width:'340px', maxWidth:'90vw', textAlign:'center',
                            boxShadow:'0 8px 32px rgba(0,0,0,0.25)', fontFamily:'Arial,sans-serif'
                        });

                        box.innerHTML = `
                            <div style="font-size:36px;margin-bottom:10px;">⚠️</div>
                            <h3 style="margin:0 0 8px;">Ajukan Edit?</h3>
                            <p style="color:#777;font-size:13px;margin-bottom:20px;">
                                Permintaan edit akan dikirim ke Leader untuk disetujui.
                                Setelah disetujui, Leader akan membuat Memo ke Tim IT.
                            </p>
                            <div style="display:flex;gap:10px;">
                                <button id="mes-edit-cancel" style="flex:1;padding:12px;border:none;
                                    border-radius:6px;background:#6c757d;color:white;
                                    font-size:14px;cursor:pointer;">Batal</button>
                                <button id="mes-edit-confirm" style="flex:1;padding:12px;border:none;
                                    border-radius:6px;background:#0b72b9;color:white;
                                    font-size:14px;font-weight:bold;cursor:pointer;">Ya, Ajukan</button>
                            </div>
                        `;

                        backdrop.appendChild(box);
                        document.body.appendChild(backdrop);

                        // Batal → tutup popup, enable tombol lagi
                        box.querySelector('#mes-edit-cancel').onclick = () => {
                            backdrop.remove();
                            btn.disabled = false;
                            btn.innerText = '✏️ Edit';
                        };

                        // Konfirmasi → kirim request via fetch
                        box.querySelector('#mes-edit-confirm').onclick = async () => {
                            box.querySelector('#mes-edit-confirm').disabled = true;
                            box.querySelector('#mes-edit-confirm').innerText = '⏳...';

                            try {
                                const resp = await fetch(`/mes/edit/${lineId}/request-json`, {
                                    method: 'POST',
                                    headers: {'Content-Type': 'application/json'},
                                    body: JSON.stringify({}),
                                });
                                const data = await resp.json();

                                backdrop.remove();

                                // ── POPUP HASIL ──────────────────────────────────
                                const resultBackdrop = document.createElement('div');
                                Object.assign(resultBackdrop.style, {
                                    position:'fixed', inset:'0', background:'rgba(0,0,0,0.55)',
                                    zIndex:'99999', display:'flex', alignItems:'center', justifyContent:'center'
                                });

                                const resultBox = document.createElement('div');
                                Object.assign(resultBox.style, {
                                    background:'white', borderRadius:'12px', padding:'28px 24px',
                                    width:'340px', maxWidth:'90vw', textAlign:'center',
                                    boxShadow:'0 8px 32px rgba(0,0,0,0.25)', fontFamily:'Arial,sans-serif'
                                });

                                const isOk = data.success;
                                resultBox.innerHTML = `
                                    <div style="font-size:36px;margin-bottom:10px;">
                                        ${isOk ? '✅' : '❌'}
                                    </div>
                                    <h3 style="margin:0 0 8px;color:${isOk ? '#28a745' : '#dc3545'};">
                                        ${isOk ? 'Request Terkirim' : 'Gagal'}
                                    </h3>
                                    <p style="color:#555;font-size:13px;margin-bottom:20px;">
                                        ${data.message || '-'}
                                    </p>
                                    <button id="mes-edit-ok" style="width:100%;padding:12px;border:none;
                                        border-radius:6px;background:${isOk ? '#28a745' : '#dc3545'};
                                        color:white;font-size:14px;font-weight:bold;cursor:pointer;">
                                        OK
                                    </button>
                                `;

                                resultBackdrop.appendChild(resultBox);
                                document.body.appendChild(resultBackdrop);

                                // OK → tutup popup + refresh workorder_info
                                resultBox.querySelector('#mes-edit-ok').onclick = () => {
                                    resultBackdrop.remove();
                                    // Trigger reload form Odoo supaya workorder_info ter-refresh
                                    if (window.__owl__ || window.odoo) {
                                        window.location.reload();
                                    } else {
                                        window.location.reload();
                                    }
                                };

                            } catch (e) {
                                backdrop.remove();
                                alert('Terjadi kesalahan. Silakan coba lagi.');
                                btn.disabled = false;
                                btn.innerText = '✏️ Edit';
                            }
                        };
                    }
                    </script>
                    """)

            # =====================================================
            # HASIL AKHIR HTML
            # =====================================================

            rec.workorder_info = "".join(html)

    # =========================
    # STATUS
    # =========================

    state = fields.Selection([
        ("draft", "Waiting"),
        ("ready", "Ready"),
        ("running", "Running"),
        ("done", "Done"),
    ], default="draft")

    start_time = fields.Datetime()

    stop_time = fields.Datetime()

    duration = fields.Float()

    note = fields.Text()

    def action_approve(self):
        self.write({
            "state": "ready"
        })
        return True

    def action_reject(self):
        self.write({
            "state": "draft"
        })
        return True
    
    def action_start_workorder(self, workorder, sequence):
        self.ensure_one()
        _logger.warning("========== START ==========")

        workorder.write({
            "operator_id": self.employee_id.id,
            "shift_id": self.shift_id.id,
            "start_time": fields.Datetime.now(),
            "state": "progress",
        })

        self.write({
            "state": "running"
        })

        return True
    
    def action_stop_workorder(self):
        self.ensure_one()

        _logger.warning("========== STOP ==========")

        self.write({
            "state": "ready",
        })

        return True

class MrpWorkcenterProductivity(models.Model):
    _inherit = "mrp.workcenter.productivity"

    shift_id = fields.Many2one("eran.master.shift", string="Shift")
    # scan_time sudah di-handle oleh Odoo lewat field 'date_start'

class MesScanApprovalLine(models.Model):
    _name = "mes.scan.approval.line"
    _description = "MES Scan Approval Line"

    approval_id = fields.Many2one(
        "mes.scan.approval",
        required=True,
        ondelete="cascade",
    )

    sequence = fields.Integer()

    workorder_id = fields.Many2one(
        "mrp.workorder",
        required=True,
    )

    production_id = fields.Many2one(
        related="workorder_id.production_id",
        store=True,
    )

    workcenter_id = fields.Many2one(
        related="workorder_id.workcenter_id",
        store=True,
    )

    leader_id = fields.Many2one(
        related="workorder_id.leader_id",
        store=True,
    )

    product_id = fields.Many2one(
        related="workorder_id.product_id",
        store=True,
    )

    # ===== TARGET PRODUKSI =====

    qty_target = fields.Float(
        related="workorder_id.production_id.product_qty",
        store=True,
    )

    qty_actual = fields.Float(default=0)

    sph = fields.Integer()

    # ===== STATUS =====

    state = fields.Selection([
        ("ready", "Ready"),
        ("running", "Running"),
        ("paused", "Paused"),
        ("done", "Done"),
    ], default="ready")

    start_time = fields.Datetime()

    stop_time = fields.Datetime()

    duration = fields.Float()

    stop_reason = fields.Selection([
        ("material", "Material Habis"),
        ("machine", "Problem Mesin"),
        ("done", "Pekerjaan Telah Selesai"),
    ], string="Alasan Stop")

    can_start = fields.Boolean(compute="_compute_can_start")

    @api.depends("sequence", "approval_id.line_ids.state", "approval_id.line_ids.sequence")
    def _compute_can_start(self):
        for line in self:
            prior_lines = line.approval_id.line_ids.filtered(
                lambda l: l.sequence < line.sequence
            )
            line.can_start = all(l.state == "done" for l in prior_lines)

    def action_start(self):
        self.ensure_one()

        if not self.can_start:
            raise UserError("Selesaikan terlebih dahulu Work Order yang sedang berjalan.")

        wo = self.workorder_id.sudo()

        if self.state == "done":
            raise UserError("Work Order ini sudah selesai dan tidak bisa di-start lagi.")

        if wo.state == "cancel":
            raise UserError("Work Order ini sudah dibatalkan.")

        scan_time = fields.Datetime.now()

        if wo.date_planned_finished and wo.date_planned_finished < scan_time:
            wo.date_planned_finished = scan_time + timedelta(hours=1)

        if wo.date_planned_start and wo.date_planned_start > wo.date_planned_finished:
            wo.date_planned_start = scan_time

        if wo.state != "progress":
            wo.button_start()
        else:
            open_time = wo.time_ids.filtered(lambda t: not t.date_end)
            if not open_time:
                wo.button_start()

        open_time = wo.time_ids.filtered(lambda t: not t.date_end)
        if open_time:
            open_time[0].write({"date_start": scan_time})

        # ===== TUTUP DOWNTIME YANG MASIH TERBUKA =====
        open_downtime = self.downtime_ids.filtered(lambda d: not d.end_time)
        if open_downtime:
            open_downtime[0].write({"end_time": scan_time})

        self.write({
            "state": "running",
            "start_time": scan_time,
        })

        if self.approval_id.state != "running":
            self.approval_id.write({"state": "running"})

    def action_stop(self, reason, note=None, qty=None, loss_id=None, create_backorder=None):
        self.ensure_one()

        wo = self.workorder_id.sudo()
        now = fields.Datetime.now()

        duration = 0.0
        if self.start_time:
            duration = (now - self.start_time).total_seconds() / 60.0

        if reason == "done":
            produced_qty = qty or 0.0

            if produced_qty <= 0:
                raise UserError("Jumlah hasil produksi harus lebih dari 0.")

            self._finish_production(produced_qty, create_backorder)

            self.write({
                "stop_time": now,
                "duration": self.duration + duration,
                "qty_actual": self.qty_actual + produced_qty,
                "state": "done",
            })

        else:
    # reason == "stop"
            if not loss_id:
                raise UserError("Alasan stop harus dipilih.")

            open_times = wo.time_ids.filtered(lambda t: not t.date_end)

            _logger.warning("MES DEBUG STOP - open_times ditemukan: %s", open_times.ids)

            if open_times:
                latest_open = open_times.sorted("id", reverse=True)[0]
                latest_open.write({
                    "date_end": now,
                    "loss_id": loss_id,
                })
                _logger.warning(
                    "MES DEBUG STOP - ditutup time_id=%s loss_id=%s date_end=%s",
                    latest_open.id, loss_id, now
                )
            else:
                _logger.warning("MES DEBUG STOP - TIDAK ADA open_time yang ditemukan!")

            self.env["mes.scan.approval.line.downtime"].sudo().create({
                "line_id": self.id,
                "loss_id": loss_id,
                "note": note,
                "start_time": now,
            })

            self.write({
                "stop_time": now,
                "duration": self.duration + duration,
                "state": "ready",
            })

    def _finish_production(self, produced_qty, create_backorder):
        self.ensure_one()

        wo = self.workorder_id.sudo()
        production = wo.production_id.sudo()
        now = fields.Datetime.now()

        wo.write({"qty_producing": produced_qty})

        open_time = wo.time_ids.filtered(lambda t: not t.date_end)
        if open_time:
            open_time[0].write({"date_end": now})
        latest_time = wo.time_ids.sorted("date_start", reverse=True)[:1]
        if latest_time and not latest_time.date_end:
            latest_time.write({"date_end": now})

        if wo.state != "done":
            wo.with_context(skip_good_total_check=True).button_finish()

        production.write({
            "good_total": production.good_total + produced_qty,
        })

        remaining_wo = production.workorder_ids.filtered(
            lambda w: w.id != wo.id and w.state not in ("done", "cancel")
        )

        if remaining_wo:
            return

        result = production.with_context(skip_good_total_check=True).button_mark_done()

        if isinstance(result, dict) and result.get("res_model") == "mrp.production.backorder":
            wizard = self.env[result["res_model"]].with_context(
                dict(result.get("context", {}), skip_good_total_check=True)
            ).create({})

            if create_backorder:
                wizard.action_backorder()
            else:
                wizard.action_close_mo()

    def _is_last_active_workorder(self):
        self.ensure_one()
        production = self.workorder_id.production_id
        remaining = production.workorder_ids.filtered(
            lambda w: w.id != self.workorder_id.id and w.state not in ("done", "cancel")
        )
        return not remaining

    def _check_underproduced(self, produced_qty):
        self.ensure_one()
        return (self.qty_actual + produced_qty) < self.qty_target

    def _stop_workorder_without_validating_production(self, workorder, stop_time):
        workorder = workorder.sudo()

        open_time = workorder.time_ids.filtered(lambda t: not t.date_end)
        if open_time:
            open_time[0].write({"date_end": stop_time})

        if workorder.state not in ("done", "cancel"):
            workorder.end_all()
            workorder.with_context(bypass_duration_calculation=True).write({
                "qty_produced": workorder.qty_produced or workorder.qty_producing or workorder.qty_production,
                "state": "done",
                "date_finished": stop_time,
                "date_planned_finished": stop_time,
                "costs_hour": workorder.workcenter_id.costs_hour,
            })
        else:
            workorder.write({
                "date_planned_finished": stop_time,
            })

        if workorder.production_id:
            workorder.production_id.write({
                "end_time": stop_time,
            })

    downtime_ids = fields.One2many(
        "mes.scan.approval.line.downtime",
        "line_id",
        string="Riwayat Downtime",
    )

    edit_request_ids = fields.One2many(
        "mes.scan.approval.edit.request",
        "line_id",
        string="Riwayat Edit Request",
    )

    has_pending_edit = fields.Boolean(compute="_compute_has_pending_edit")

    @api.depends(
        "edit_request_ids",
        "edit_request_ids.state"
    )
    def _compute_has_pending_edit(self):

        for line in self:

            line.has_pending_edit = bool(
                line.edit_request_ids.filtered(
                    lambda r: r.state in ("waiting", "approved")
                )
            )

class MesScanApprovalLineDowntime(models.Model):
    _name = "mes.scan.approval.line.downtime"
    _description = "MES Downtime Log"
    _order = "start_time desc"

    line_id = fields.Many2one(
        "mes.scan.approval.line",
        required=True,
        ondelete="cascade",
    )

    loss_id = fields.Many2one(
        "mrp.workcenter.productivity.loss",
        string="Alasan Stop",
        required=True,
    )

    note = fields.Text()

    start_time = fields.Datetime(required=True)
    end_time = fields.Datetime()     
   

class HrEmployee(models.Model):
    _inherit = "hr.employee"

    @api.model
    def _eran_jakarta_day_bounds(self, now_utc=None):
        """Awal dan akhir hari kalender Asia/Jakarta, dalam UTC naive."""
        tz = pytz.timezone("Asia/Jakarta")
        now_utc = now_utc or fields.Datetime.now()
        if getattr(now_utc, "tzinfo", None):
            now_utc = now_utc.astimezone(pytz.utc).replace(tzinfo=None)
        now_local = pytz.utc.localize(now_utc).astimezone(tz)
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = start_local + timedelta(days=1)
        return (
            start_local.astimezone(pytz.utc).replace(tzinfo=None),
            end_local.astimezone(pytz.utc).replace(tzinfo=None),
        )

    @api.model
    def _eran_today_attendance(self, employee, now_utc=None):
        start_utc, end_utc = self._eran_jakarta_day_bounds(now_utc)
        return self.env["hr.attendance"].sudo().search([
            ("employee_id", "=", employee.id),
            ("check_in", ">=", start_utc),
            ("check_in", "<", end_utc),
        ], order="check_in desc", limit=1)

    def _mes_get_or_create_approval(self, barcode):
        """
        Return record mes.scan.approval untuk barcode ini,
        pakai yang sudah ada hari ini kalau ada, atau bikin baru.
        Setiap scan akan mengecek ulang apakah ada WO baru yang
        perlu ditambahkan ke approval yang sudah ada.
        """

        employee = self.sudo().search([
            ("barcode", "=", barcode)
        ], limit=1)

        if not employee:
            return None

        scan_time = fields.Datetime.now()
        tz = pytz.timezone("Asia/Jakarta")
        scan_time_local = pytz.utc.localize(scan_time).astimezone(tz)
        scan_hour = scan_time_local.hour + scan_time_local.minute / 60.0
        today, tomorrow = self._eran_jakarta_day_bounds(scan_time)

        # =========================================================
        # VALIDASI 1: WAJIB ABSEN DULU DI HR.ATTENDANCE
        # =========================================================

        attendance = self._eran_today_attendance(employee, scan_time)
        if not attendance:
            return {
                "error": (
                    f"{employee.name} belum melakukan absen masuk hari ini. "
                    "Silakan scan absen di mesin absensi terlebih dahulu."
                )
            }
        check_in_value = attendance.check_in

        # =========================================================
        # VALIDASI 2: CEK JAM SHIFT
        # Operator tidak boleh scan MO di luar jam shiftnya
        # =========================================================

        shift = employee.shift_id if hasattr(employee, "shift_id") else None

        # Ambil shift dari WO kalau employee belum punya
        if not shift:
            # Cek WO hari ini milik employee untuk dapat shift-nya
            sample_wo = self.env["mrp.workorder"].sudo().search([
                "|",
                    ("operator_id", "=", employee.id),
                    ("production_id.operator_id", "=", employee.id),
                ("state", "in", ["pending", "waiting", "ready", "progress"]),
                ("production_id.date_planned_start", ">=", today),
                ("production_id.date_planned_start", "<", tomorrow),
            ], limit=1)
            if sample_wo:
                shift = sample_wo.shift_id

        if shift:
            # shift.hour_start dan shift.hour_end dalam format float
            # misal 07.5 = 07:30, 15.0 = 15:00
            # Sesuaikan nama field ini dengan model eran.master.shift Anda
            shift_start = getattr(shift, "hour_start", None)   # jam mulai shift
            shift_end   = getattr(shift, "hour_end", None)     # jam selesai shift

            # Toleransi: 30 menit sebelum shift mulai & 60 menit setelah shift selesai
            TOLERANSI_AWAL  = 0.5   # 30 menit
            TOLERANSI_AKHIR = 1.0   # 60 menit

            if shift_start is not None and shift_end is not None:
                batas_awal  = shift_start - TOLERANSI_AWAL
                batas_akhir = shift_end + TOLERANSI_AKHIR

                # Handle shift malam yang melewati tengah malam
                # Contoh: shift mulai 22:00 (22.0), selesai 06:00 (6.0)
                if shift_end < shift_start:
                    # Shift malam: valid kalau jam >= batas_awal ATAU jam <= batas_akhir
                    dalam_shift = (scan_hour >= batas_awal) or (scan_hour <= batas_akhir)
                else:
                    dalam_shift = batas_awal <= scan_hour <= batas_akhir

                if not dalam_shift:
                    # Format jam untuk pesan error
                    def fmt_jam(h):
                        jam = int(h)
                        menit = int(round((h - jam) * 60))
                        return f"{jam:02d}:{menit:02d}"

                    return {
                        "error": (
                            f"{employee.name} tidak dapat scan MO sekarang. "
                            f"Jam kerja shift {shift.name} adalah "
                            f"{fmt_jam(shift_start)} – {fmt_jam(shift_end)}. "
                            f"Scan dilakukan pukul {scan_time_local.strftime('%H:%M')}."
                        )
                    }

        # =========================================================
        # CARI WO YANG COCOK
        # =========================================================

        domain = [
            "|",
                ("operator_id", "=", employee.id),
                ("production_id.operator_id", "=", employee.id),
            ("state", "in", ["pending", "waiting", "ready", "progress", "done"]),
            ("production_id.date_planned_start", ">=", today),
            ("production_id.date_planned_start", "<", tomorrow),
        ]

        workorders = self.env["mrp.workorder"].sudo().search(domain)

        _logger.warning("MES DEBUG - domain dipakai: %s", domain)
        _logger.warning("MES DEBUG - total WO ditemukan: %s", len(workorders))

        STATE_MAP = {
            "pending": "ready",
            "waiting": "ready",
            "ready": "ready",
            "progress": "running",
            "done": "done",
        }

        # =========================================================
        # CEK APPROVAL YANG SUDAH ADA HARI INI
        # =========================================================

        existing = self.env["mes.scan.approval"].sudo().search([
            ("employee_id", "=", employee.id),
            ("check_in", ">=", today),
            ("check_in", "<", tomorrow),
        ], limit=1)

        if existing:
            existing.write({"scan_time": scan_time})

            existing_wo_ids = existing.line_ids.mapped("workorder_id").ids
            new_workorders = workorders.filtered(lambda wo: wo.id not in existing_wo_ids)

            if new_workorders:
                last_sequence = max(existing.line_ids.mapped("sequence") or [0])

                for idx, wo in enumerate(new_workorders, start=1):
                    self.env["mes.scan.approval.line"].sudo().create({
                        "approval_id": existing.id,
                        "sequence": last_sequence + idx,
                        "workorder_id": wo.id,
                        "qty_target": wo.production_id.product_qty,
                        "qty_actual": 0,
                        "state": STATE_MAP.get(wo.state, "ready"),
                    })

            return existing

        # =========================================================
        # BELUM ADA APPROVAL — BUAT BARU
        # =========================================================

        if not workorders:
            return {"error": f"Tidak ada Work Order untuk {employee.name} hari ini."}

        approval = self.env["mes.scan.approval"].sudo().create({
            "employee_id": employee.id,
            "check_in": check_in_value,
            "scan_time": scan_time,
            "shift_id": workorders[:1].shift_id.id,
            "workcenter_id": workorders[:1].workcenter_id.id,
            "state": "ready",
        })

        for seq, wo in enumerate(workorders, start=1):
            self.env["mes.scan.approval.line"].sudo().create({
                "approval_id": approval.id,
                "sequence": seq,
                "workorder_id": wo.id,
                "qty_target": wo.production_id.product_qty,
                "qty_actual": 0,
                "state": STATE_MAP.get(wo.state, "ready"),
            })

        return approval

    @api.model
    def attendance_scan(self, barcode):
        """
        Dipanggil oleh kiosk attendance bawaan Odoo.
        Catat hr.attendance lalu arahkan ke halaman sambutan custom.
        """
        import pytz
        from datetime import timedelta

        employee = self.sudo().search([("barcode", "=", barcode)], limit=1)

        if not employee:
            return {"warning": "Barcode tidak dikenali."}

        now_utc = fields.Datetime.now()
        existing = self._eran_today_attendance(employee, now_utc)

        if existing:
            return {
                "action": {
                    "type": "ir.actions.act_url",
                    "url": f"/attendance/kiosk/welcome/{employee.id}?already=1",
                    "target": "self",
                }
            }

        if not existing:
            # Tutup attendance terbuka sebelumnya
            open_att = self.env["hr.attendance"].sudo().search([
                ("employee_id", "=", employee.id),
                ("check_out", "=", False),
            ], limit=1)
            if open_att:
                open_att.write({"check_out": now_utc})

            # Buat check-in baru
            att_vals = {"employee_id": employee.id, "check_in": now_utc}
            shift = getattr(employee, "shift_id", None)
            if shift:
                att_vals["shift_id"] = shift.id
            self.env["hr.attendance"].sudo().create(att_vals)

        # Redirect ke halaman sambutan
        return {
            "action": {
                "type": "ir.actions.act_url",
                "url": f"/attendance/kiosk/welcome/{employee.id}",
                "target": "self",
            }
        }

    @api.model
    def mes_kiosk_scan(self, barcode):
        
        # =========================================================
        # VALIDASI 1: WAJIB ABSEN DULU DI HR.ATTENDANCE
        # Dilakukan di sini, bukan di _mes_get_or_create_approval
        # supaya attendance kiosk bawaan Odoo tidak ikut ke-block
        # =========================================================
        
        import pytz
        from datetime import timedelta

        scan_time = fields.Datetime.now()
        tz = pytz.timezone("Asia/Jakarta")
        scan_time_local = pytz.utc.localize(scan_time).astimezone(tz)

        employee = self.sudo().search([("barcode", "=", barcode)], limit=1)

        if not employee:
            return {"warning": "Barcode tidak dikenali."}

        attendance = self._eran_today_attendance(employee, scan_time)

        if not attendance:
            return {
                "warning": (
                    f"{employee.name} belum melakukan absen masuk hari ini. "
                    "Silakan scan absen di mesin absensi terlebih dahulu."
                )
            }

        # =========================================================
        # VALIDASI 2: CEK JAM SHIFT
        # =========================================================

        scan_hour = scan_time_local.hour + scan_time_local.minute / 60.0
        shift = getattr(employee, "shift_id", None)

        if shift:
            shift_start = getattr(shift, "hour_start", None)
            shift_end   = getattr(shift, "hour_end", None)

            TOLERANSI_AWAL  = 0.5   # 30 menit sebelum shift
            TOLERANSI_AKHIR = 1.0   # 60 menit setelah shift

            if shift_start is not None and shift_end is not None:
                batas_awal  = shift_start - TOLERANSI_AWAL
                batas_akhir = shift_end + TOLERANSI_AKHIR

                # Handle shift malam (lintas tengah malam)
                if shift_end < shift_start:
                    dalam_shift = (scan_hour >= batas_awal) or (scan_hour <= batas_akhir)
                else:
                    dalam_shift = batas_awal <= scan_hour <= batas_akhir

                if not dalam_shift:
                    def fmt_jam(h):
                        jam = int(h)
                        menit = int(round((h - jam) * 60))
                        return f"{jam:02d}:{menit:02d}"

                    return {
                        "warning": (
                            f"{employee.name} tidak dapat scan MO sekarang. "
                            f"Jam kerja shift {shift.name} adalah "
                            f"{fmt_jam(shift_start)} – {fmt_jam(shift_end)}. "
                            f"Scan dilakukan pukul {scan_time_local.strftime('%H:%M')}."
                        )
                    }

        # =========================================================
        # SEMUA VALIDASI LOLOS — LANJUT PROSES APPROVAL
        # =========================================================

        result = self._mes_get_or_create_approval(barcode)

        if isinstance(result, dict) and "error" in result:
            return {"warning": result["error"]}

        if not result:
            return {"warning": "Barcode tidak dikenali."}

        return {
            "action": {
                "type": "ir.actions.act_url",
                "url": f"/mes/greet/{result.id}",
                "target": "self",
            }
        }

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

    @http.route("/mes/edit/<int:line_id>", type="http", auth="user")
    def mes_edit_confirm(self, line_id, **kwargs):
            line = request.env["mes.scan.approval.line"].sudo().browse(line_id)
    
            if not line.exists():
                return self._info_page("Gagal", f"Line ID {line_id} tidak ditemukan.", color="#dc3545")
    
            if line.has_pending_edit:
                return self._info_page(
                    "Sudah Menunggu",
                    "Request edit untuk Work Order ini sudah diajukan dan sedang menunggu persetujuan.",
                    color="#dc3545",
                )
    
            html = f"""
            <html>
            <head><meta charset="utf-8"/><title>Konfirmasi Edit</title></head>
            <body style="font-family:-apple-system,Arial,sans-serif;background:#f4f4f4;
                display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
                <div style="background:white;border-radius:12px;padding:30px;
                    box-shadow:0 4px 20px rgba(0,0,0,0.15);width:340px;text-align:center;">
                    <div style="font-size:40px;margin-bottom:10px;">⚠️</div>
                    <h3 style="margin:0 0 8px 0;">Apakah Anda yakin untuk mengedit form ini?</h3>
                    <p style="color:#777;font-size:13px;">
                        {line.workorder_id.name} — {line.workorder_id.production_id.name}
                    </p>
                    <p style="color:#555;font-size:13px;margin-bottom:20px;">
                        Permintaan edit akan dikirim ke Leader untuk disetujui.
                        Setelah disetujui, Leader akan membuat Memo ke Tim IT
                        untuk proses perubahan quantity.
                    </p>
    
                    <a href="/mes/edit/{line.id}/request"
                        style="display:block;margin:10px 0;padding:14px;background:#0b72b9;
                        color:white;border-radius:6px;text-decoration:none;font-weight:bold;">
                        Ya, Ajukan Edit
                    </a>
                </div>
            </body>
            </html>
            """
            return request.make_response(html)

    @http.route(
        "/mes/edit/<int:line_id>/request",
        type="http",
        auth="user"
    )
    def mes_edit_request(self, line_id, **kwargs):

        line = request.env[
            "mes.scan.approval.line"
        ].sudo().browse(line_id)

        if not line.exists():
            return self._info_page(
                "Gagal",
                f"Line ID {line_id} tidak ditemukan.",
                color="#dc3545",
            )

        if line.has_pending_edit:
            return self._info_page(
                "Sudah Menunggu",
                "Request edit sudah diajukan sebelumnya.",
                color="#dc3545",
            )

        # =====================================================
        # CEK LEADER
        # =====================================================

        leader = line.leader_id.sudo()

        if not leader:
            return self._info_page(
                "Gagal",
                "Work Order ini belum memiliki Leader.",
                color="#dc3545",
            )

        leader_user = request.env[
            "mes.scan.approval.edit.request"
        ].sudo()._find_leader_user(leader)

        if not leader_user:
            return self._info_page(
                "Gagal",
                (
                    f"Leader {leader.name} belum memiliki "
                    "User Odoo dan tidak ditemukan User "
                    "dengan nama yang sesuai."
                ),
                color="#dc3545",
            )

        _logger.warning(
            "MES EDIT REQUEST DEBUG: "
            "line_id=%s | leader_id=%s | leader_name=%s | "
            "user_id=%s | user_name=%s | login=%s",
            line.id,
            leader.id,
            leader.name,
            leader_user.id,
            leader_user.name,
            leader_user.login,
        )
        # =====================================================
        # CREATE REQUEST
        # =====================================================

        edit_request = request.env[
            "mes.scan.approval.edit.request"
        ].sudo().create({
            "line_id": line.id,
        })

        # =====================================================
        # REALTIME POPUP KE LEADER
        # =====================================================

        edit_request._send_leader_notification()

        return self._info_page(
            "Request Terkirim",
            (
                f"Permintaan edit untuk "
                f"{line.workorder_id.name} telah dikirim "
                f"ke Leader {leader.name}."
            ),
        )

    @http.route("/mes/edit/<int:line_id>/request-json", type="http", auth="user", methods=["POST"], csrf=False)
    def mes_edit_request_json(self, line_id, **kwargs):
        import json

        line = request.env["mes.scan.approval.line"].sudo().browse(line_id)

        if not line.exists():
            return request.make_response(
                json.dumps({"success": False, "message": "Line tidak ditemukan."}),
                headers={"Content-Type": "application/json"}
            )

        if line.has_pending_edit:
            return request.make_response(
                json.dumps({"success": False, "message": "Request edit sudah diajukan dan sedang menunggu persetujuan."}),
                headers={"Content-Type": "application/json"}
            )

        leader = line.leader_id.sudo()
        if not leader:
            return request.make_response(
                json.dumps({"success": False, "message": "Work Order ini belum memiliki Leader."}),
                headers={"Content-Type": "application/json"}
            )

        leader_user = request.env["mes.scan.approval.edit.request"].sudo()._find_leader_user(leader)
        if not leader_user:
            return request.make_response(
                json.dumps({"success": False, "message": f"Leader {leader.name} tidak memiliki User Odoo."}),
                headers={"Content-Type": "application/json"}
            )

        edit_request = request.env["mes.scan.approval.edit.request"].sudo().create({
            "line_id": line.id,
        })
        edit_request._send_leader_notification()

        return request.make_response(
            json.dumps({
                "success": True,
                "message": f"Permintaan edit untuk {line.workorder_id.name} telah dikirim ke Leader {leader.name}."
            }),
            headers={"Content-Type": "application/json"}
        )

class MesScanApprovalEditRequest(models.Model):
    _name = "mes.scan.approval.edit.request"
    _description = "MES Edit Request"
    _order = "create_date desc"

    line_id = fields.Many2one(
        "mes.scan.approval.line",
        required=True,
        ondelete="cascade",
    )

    requested_by = fields.Many2one(
        "hr.employee",
        string="Diminta Oleh",
        related="line_id.approval_id.employee_id",
        store=True,
        readonly=True,
    )

    workorder_id = fields.Many2one(
        "mrp.workorder",
        related="line_id.workorder_id",
        store=True,
        readonly=True,
    )

    leader_id = fields.Many2one(
        "hr.employee",
        string="Leader",
        related="line_id.leader_id",
        store=True,
        readonly=True,
    )

    leader_user_id = fields.Many2one(
        "res.users",
        string="User Leader",
        compute="_compute_leader_user",
        store=True,
        readonly=True,
    )

    @api.depends("leader_id", "leader_id.user_id")
    def _compute_leader_user(self):
        for record in self:

            leader = record.leader_id.sudo()

            record.leader_user_id = (
                leader.user_id.sudo()
                if leader and leader.user_id
                else False
            )

    current_qty = fields.Float(
        string="Output Saat Ini",
        related="line_id.qty_actual",
        readonly=True,
    )

    new_qty = fields.Float(
        string="Quantity Perubahan",
    )

    state = fields.Selection([
        ("waiting", "Menunggu Persetujuan"),
        ("approved", "Disetujui oleh Leader"),
        ("rejected", "Ditolak"),
    ], default="waiting", required=True)

    approved_by = fields.Many2one(
        "res.users",
        string="Disetujui Oleh",
        readonly=True,
    )

    approved_date = fields.Datetime(
        readonly=True,
    )

    memo_notified = fields.Boolean(
        string="Notifikasi Memo Terkirim",
        default=False,
        readonly=True,
    )

    note = fields.Text(
        string="Catatan",
    )

    # =========================================================
    # LEADER USER
    # =========================================================

    @api.model
    def _find_leader_user(self, leader):
        """
        Cari User Odoo berdasarkan Employee Leader.

        Prioritas:
        1. Employee.user_id
        2. Fallback berdasarkan nama, case-insensitive.

        Contoh:
            MUSTAMIR
            Mustamir
            mustamir

        akan dianggap sama sementara.
        """

        leader = leader.sudo()

        # -----------------------------------------------------
        # Leader tidak ditemukan
        # -----------------------------------------------------

        if not leader or not leader.exists():
            return self.env["res.users"]

        # -----------------------------------------------------
        # PRIORITAS 1
        # Employee sudah memiliki user_id
        # -----------------------------------------------------

        if leader.user_id:
            return leader.user_id.sudo()

        # -----------------------------------------------------
        # PRIORITAS 2
        # Cari User berdasarkan nama
        # Case-insensitive
        # -----------------------------------------------------

        leader_name = (leader.name or "").strip()

        if not leader_name:
            return self.env["res.users"]

        leader_user = self.env["res.users"].sudo().search([
            ("name", "=ilike", leader_name),
            ("active", "=", True),
        ], limit=1)

        # -----------------------------------------------------
        # LOG
        # -----------------------------------------------------

        if leader_user:
            _logger.warning(
                "MES EDIT REQUEST FALLBACK: "
                "Employee '%s' (ID %s) belum memiliki user_id. "
                "Menggunakan User '%s' (ID %s).",
                leader.name,
                leader.id,
                leader_user.name,
                leader_user.id,
            )

        else:
            _logger.warning(
                "MES EDIT REQUEST: "
                "Tidak menemukan User Odoo untuk Leader '%s' "
                "(Employee ID %s).",
                leader.name,
                leader.id,
            )

        return leader_user


    def _get_leader_user(self):
        """
        Ambil User Odoo dari Leader pada request ini.

        Menggunakan _find_leader_user() supaya:
        - Employee -> User langsung tetap diprioritaskan
        - Kalau user_id kosong, fallback nama digunakan
        - Kapitalisasi nama tidak menjadi masalah
        """

        self.ensure_one()

        return self._find_leader_user(
            self.sudo().leader_id
        )
        
    # =========================================================
    # REALTIME NOTIFICATION
    # =========================================================

    def _notification_payload(self):
        self.ensure_one()
        rec = self.sudo()
        line = rec.line_id
        wo = rec.workorder_id
        production = wo.production_id
        return {
            "request_id": rec.id,
            "operator_name": rec.requested_by.name or "-",
            "leader_name": rec.leader_id.name or "-",
            "workorder_name": wo.name or "-",
            "production_name": production.name or "-",
            "product_name": wo.product_id.display_name or "-",
            "current_qty": line.qty_actual,
            "state": rec.state,
        }

    @api.model
    def get_pending_for_current_leader(self):
        """Request waiting milik leader yang sedang login.

        Dipakai saat leader baru login, karena notifikasi bus
        tidak tersimpan kalau dia sedang offline.
        """
        user = self.env.user
        requests = self.sudo().search(
            [("state", "=", "waiting")],
            order="create_date asc",
        )
        payloads = []
        for rec in requests:
            leader_user = rec._get_leader_user()
            if leader_user and leader_user.id == user.id:
                payloads.append(rec._notification_payload())
        return payloads

    def _send_leader_notification(self):
        """
        Kirim realtime notification hanya ke user Odoo
        yang merupakan Leader dari Work Order ini.
        """

        self.ensure_one()

        rec = self.sudo()
        leader_user = rec._get_leader_user()

        if not leader_user:
            _logger.warning(
                "MES EDIT REQUEST: Leader %s belum memiliki user Odoo.",
                rec.leader_id.name if rec.leader_id else "-",
            )
            return

        if not leader_user.partner_id:
            _logger.warning(
                "MES EDIT REQUEST: User %s tidak memiliki partner.",
                leader_user.name,
            )
            return

        payload = rec._notification_payload()

        # Odoo Bus realtime notification
        self.env["bus.bus"]._sendone(
            leader_user.partner_id,
            "mes_edit_request",
            payload,
        )

        _logger.info(
            "MES EDIT REQUEST: notification dikirim ke Leader %s "
            "(user_id=%s, partner_id=%s), request_id=%s",
            leader_user.name,
            leader_user.id,
            leader_user.partner_id.id,
            rec.id,
        )

    # =========================================================
    # APPROVE
    # =========================================================

    def _check_leader_user(self):
        self.ensure_one()
        leader_user = self._get_leader_user()
        if not leader_user:
            raise UserError(
                "Leader Work Order ini belum memiliki user Odoo."
            )
        if self.env.user.id != leader_user.id:
            raise UserError(
                "Anda bukan Leader dari Work Order ini. "
                "Hanya Leader yang dapat memproses request edit."
            )
        return leader_user

    def _memo_context(self):
        rec = self.sudo()
        workorder = rec.workorder_id
        production = workorder.production_id
        request_dt = rec.approved_date or rec.create_date or fields.Datetime.now()
        tz_record = rec.with_context(tz=self.env.user.tz or "Asia/Jakarta")
        local_dt = fields.Datetime.context_timestamp(tz_record, request_dt)
        return {
            "operator_name": rec.requested_by.name or "-",
            "leader_name": rec.approved_by.name or rec.leader_id.name or "-",
            "workorder_name": workorder.name or "-",
            "production_name": production.name or "-",
            "product_name": workorder.product_id.display_name or "-",
            "current_qty": rec.current_qty or 0,
            "new_qty": rec.new_qty or 0,
            "date_str": local_dt.strftime("%d/%m/%Y %H:%M"),
            "note": rec.note or "-",
        }

    def _get_admin_users(self):
        admin_group = self.env.ref("base.group_system", raise_if_not_found=False)
        if not admin_group:
            return self.env["res.users"]
        return admin_group.sudo().users.filtered(
            lambda user: user.active and user.partner_id
        )

    def action_approve(self):
        self.ensure_one()

        if self.state != "waiting":
            raise UserError(
                "Request ini sudah diproses sebelumnya."
            )

        self._check_leader_user()

        rec = self.sudo()
        ctx = rec._memo_context()
        leader_name = self.env.user.name or ctx["leader_name"]
        operator_name = ctx["operator_name"]
        wo_name = ctx["workorder_name"]
        mo_name = ctx["production_name"]

        rec.write({
            "state": "approved",
            "approved_by": self.env.user.id,
            "approved_date": fields.Datetime.now(),
            "note": (
                f"✅ Disetujui oleh Leader: {leader_name}\n"
                f"Operator  : {operator_name}\n"
                f"MO        : {mo_name}\n"
                f"WO        : {wo_name}\n"
                f"Perlu konfirmasi memo ke IT."
            ),
        })

        rec._send_operator_result_notification("approved")
        rec._notify_administrators_memo()
        return True

    def action_confirm_it_memo(self):
        """Konfirmasi Leader untuk mengirim pengajuan memo ke admin."""
        self.ensure_one()
        self._check_leader_user()
        rec = self.sudo()
        if rec.state != "approved":
            raise UserError("Request edit harus disetujui terlebih dahulu.")
        if not rec.memo_notified:
            rec._notify_administrators_memo()
        return True

    def action_create_it_note(self):
        """Membuat Memo/Notes untuk Tim IT setelah Leader menyetujui."""
        self.ensure_one()
        rec = self.sudo()
        if rec.state != "approved":
            raise UserError(
                "Request edit belum disetujui oleh Leader."
            )
        if rec.memo_notified:
            return True
        return rec._notify_administrators_memo()

    # =========================================================
    # REJECT
    # =========================================================

    def action_reject(self):
        self.ensure_one()

        # -----------------------------------------------------
        # 1. REQUEST HARUS MASIH WAITING
        # -----------------------------------------------------

        if self.state != "waiting":
            raise UserError(
                "Request ini sudah diproses sebelumnya."
            )

        # -----------------------------------------------------
        # 2. VALIDASI LEADER
        # -----------------------------------------------------

        self._check_leader_user()

        self.sudo().write({
            "state": "rejected",
            "approved_by": self.env.user.id,
            "approved_date": fields.Datetime.now(),
        })

        self.sudo()._send_operator_result_notification(
            "rejected"
        )

        return True

    # =========================================================
    # NOTIFIKASI OPERATOR
    # =========================================================

    def _send_operator_result_notification(self, result):
        """
        Kirim hasil approval/rejection kembali ke operator.
        """

        self.ensure_one()
        rec = self.sudo()

        approval = rec.line_id.approval_id

        if not approval or not approval.employee_id:
            return

        operator_user = approval.employee_id.user_id

        if not operator_user or not operator_user.partner_id:
            return

        workorder_name = rec.workorder_id.name or "-"
        approver_name = rec.approved_by.name or "-"

        if result == "approved":
            title = "✅ Edit Disetujui"
            message = (
                f"Request edit {workorder_name} "
                f"telah disetujui oleh {approver_name}."
            )
        else:
            title = "❌ Edit Ditolak"
            message = (
                f"Request edit {workorder_name} "
                f"ditolak oleh {approver_name}."
            )

        rec.env["bus.bus"]._sendone(
            operator_user.partner_id,
            "mes_edit_request_result",
            {
                "request_id": rec.id,
                "title": title,
                "message": message,
                "state": result,
            },
        )

    # ========================================================
    # VERIFIKASI LEADER APPROVED, BUAT MEMO IT
    # ========================================================
    
    def _send_memo_it_notification(self):
        """
        Memberikan instruksi kepada Leader bahwa request
        sudah disetujui dan perlu dibuatkan Memo ke Tim IT.
        """

        self.ensure_one()

        leader_user = self._get_leader_user()

        if not leader_user:
            _logger.warning(
                "MES EDIT REQUEST: Leader tidak ditemukan "
                "untuk Memo IT. request_id=%s",
                self.id,
            )
            return

        if not leader_user.partner_id:
            _logger.warning(
                "MES EDIT REQUEST: Leader tidak memiliki partner. "
                "request_id=%s",
                self.id,
            )
            return

        line = self.line_id.sudo()
        wo = self.workorder_id.sudo()
        production = wo.production_id.sudo()

        payload = {
            "request_id": self.id,

            "operator_name": (
                self.requested_by.sudo().name
                if self.requested_by
                else "-"
            ),

            "leader_name": (
                self.leader_id.sudo().name
                if self.leader_id
                else "-"
            ),

            "workorder_name": (
                wo.name
                if wo
                else "-"
            ),

            "production_name": (
                production.name
                if production
                else "-"
            ),

            "product_name": (
                wo.product_id.sudo().display_name
                if wo and wo.product_id
                else "-"
            ),

            "current_qty": line.qty_actual,

            "state": "approved",

            "action": "create_it_memo",
        }

        self.env["bus.bus"]._sendone(
            leader_user.partner_id,
            "mes_edit_request_approved",
            payload,
        )

        _logger.info(
            "MES EDIT REQUEST: instruksi Memo IT dikirim "
            "ke Leader %s, request_id=%s",
            leader_user.name,
            self.id,
        )

    def _notify_administrators_memo(self):
        """Kirim notes + popup ke administrator setelah Leader setuju."""
        self.ensure_one()
        rec = self.sudo()
        ctx = rec._memo_context()
        admin_users = rec._get_admin_users()

        if not admin_users:
            _logger.warning(
                "MES EDIT REQUEST: Tidak ada user admin aktif untuk request_id=%s",
                rec.id,
            )
            return False

        message = (
            f"MO {ctx['production_name']}, atas nama {ctx['operator_name']}, "
            f"tanggal {ctx['date_str']}, Leader {ctx['leader_name']} "
            "akan membuat memo terkait perubahan data output "
            "yang sudah diinput oleh operator."
        )
        note_title = (
            f"Memo Perubahan Data - {ctx['production_name']} - {ctx['workorder_name']}"
        )
        note_body = f"""
            <h2>Pengajuan Perubahan Data Produksi</h2>
            <p>{message}</p>
            <table style="border-collapse: collapse; width: 100%;">
                <tr>
                    <td style="padding: 6px; font-weight: bold;">Operator</td>
                    <td style="padding: 6px;">{ctx['operator_name']}</td>
                </tr>
                <tr>
                    <td style="padding: 6px; font-weight: bold;">Leader</td>
                    <td style="padding: 6px;">{ctx['leader_name']}</td>
                </tr>
                <tr>
                    <td style="padding: 6px; font-weight: bold;">Tanggal</td>
                    <td style="padding: 6px;">{ctx['date_str']}</td>
                </tr>
                <tr>
                    <td style="padding: 6px; font-weight: bold;">Manufacturing Order</td>
                    <td style="padding: 6px;">{ctx['production_name']}</td>
                </tr>
                <tr>
                    <td style="padding: 6px; font-weight: bold;">Work Order</td>
                    <td style="padding: 6px;">{ctx['workorder_name']}</td>
                </tr>
                <tr>
                    <td style="padding: 6px; font-weight: bold;">Product</td>
                    <td style="padding: 6px;">{ctx['product_name']}</td>
                </tr>
                <tr>
                    <td style="padding: 6px; font-weight: bold;">Output Saat Ini</td>
                    <td style="padding: 6px;">{ctx['current_qty']}</td>
                </tr>
            </table>
            <p><strong>Status:</strong> Disetujui oleh Leader. Menunggu memo perubahan data ke Tim IT.</p>
        """
        payload = {
            "request_id": rec.id,
            "title": "Pengajuan Memo Perubahan Data",
            "message": message,
            "operator_name": ctx["operator_name"],
            "leader_name": ctx["leader_name"],
            "production_name": ctx["production_name"],
            "workorder_name": ctx["workorder_name"],
            "product_name": ctx["product_name"],
            "date_str": ctx["date_str"],
            "current_qty": ctx["current_qty"],
        }

        for admin_user in admin_users:
            rec.env["bus.bus"]._sendone(
                admin_user.partner_id,
                "mes_edit_request_admin_memo",
                payload,
            )

        email_from = (
            self.env.user.partner_id.email_formatted
            or self.env.company.partner_id.email_formatted
            or "noreply@localhost"
        )
        try:
            rec.env["mail.thread"].message_notify(
                partner_ids=admin_users.mapped("partner_id").ids,
                subject=note_title,
                body=f"<p>{message}</p>",
                model="mes.scan.approval.edit.request",
                res_id=rec.id,
                email_from=email_from,
            )
        except Exception:
            _logger.exception(
                "MES EDIT REQUEST: gagal kirim inbox admin, request_id=%s",
                rec.id,
            )

        created_note = False
        if "note.note" in rec.env:
            Note = rec.env["note.note"]
            created_notes = Note.browse()
            for admin_user in admin_users:
                stage = rec.env["note.stage"].search(
                    [("user_id", "=", admin_user.id)],
                    limit=1,
                )
                vals = {
                    "name": note_title,
                    "user_id": admin_user.id,
                    "memo": note_body,
                }
                if stage:
                    vals["stage_ids"] = [(6, 0, [stage.id])]
                created_notes |= Note.create(vals)
            created_note = created_notes[:1]

        rec.write({"memo_notified": True})
        _logger.info(
            "MES EDIT REQUEST: notes/notifikasi admin dikirim ke %s admin, request_id=%s",
            len(admin_users),
            rec.id,
        )
        return {
            "note_id": created_note.id if created_note else False,
            "note_name": created_note.name if created_note else note_title,
        }

    def _send_admin_memo_notification(self):
        """Alias lama: kirim notes dan popup ke administrator."""
        return self._notify_administrators_memo()

class MesEditRequest(models.Model):
    _name = "mes.edit.request"
    _description = "MES Edit Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]  # ← ini harus ada