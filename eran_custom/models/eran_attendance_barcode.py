from pyparsing import line

from odoo import models, fields, api
import logging
from datetime import timedelta
from collections import Counter
from odoo.exceptions import UserError
from odoo import http
from odoo.http import request

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

                    action_button = f"""
                    <div style="
                        text-align:right;
                        margin-top:14px;
                    ">
                        <a href="/mes/stop/{line_sudo.id}"
                            style="
                                display:inline-block;
                                padding:8px 16px;
                                background:#dc3545;
                                color:white;
                                border-radius:6px;
                                text-decoration:none;
                                font-size:13px;
                                font-weight:bold;
                            ">
                            ⏹️ STOP
                        </a>
                    </div>
                    """

                elif line_sudo.can_start:

                    action_button = f"""
                    <div style="
                        text-align:right;
                        margin-top:14px;
                    ">
                        <a href="/mes/start/{line_sudo.id}"
                            style="
                                display:inline-block;
                                padding:8px 16px;
                                background:#28a745;
                                color:white;
                                border-radius:6px;
                                text-decoration:none;
                                font-size:13px;
                                font-weight:bold;
                            ">
                            ▶️ START
                        </a>
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
                    # waiting -> tampil "Menunggu persetujuan edit"
                    # selain waiting -> tampil tombol Edit
                    # =================================================

                    edit_button = ""

                    if line_sudo.has_pending_edit:

                        edit_button = """
                        <div style="
                            text-align:right;
                            margin-top:10px;
                        ">
                            <span style="
                                font-size:12px;
                                color:#888;
                            ">
                                ⏳ Menunggu persetujuan edit
                            </span>
                        </div>
                        """

                    else:

                        edit_button = f"""
                        <div style="
                            text-align:right;
                            margin-top:10px;
                        ">
                            <a href="/mes/edit/{line_sudo.id}"
                                style="
                                    display:inline-block;
                                    padding:6px 14px;
                                    background:#6c757d;
                                    color:white;
                                    border-radius:5px;
                                    text-decoration:none;
                                    font-size:12px;
                                    font-weight:bold;
                                ">
                                ✏️ Edit
                            </a>
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
                    lambda r: r.state == "waiting"
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
        today = scan_time.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)

        attendance = self.env["hr.attendance"].sudo().search([
            ("employee_id", "=", employee.id),
            ("check_in", ">=", today),
            ("check_in", "<", tomorrow),
        ], order="check_in desc", limit=1)

        if not attendance:
            _logger.warning(
                "[DEV MODE] %s belum absen wajah, pakai scan_time sebagai check_in dummy",
                employee.name
            )
            check_in_value = scan_time
        else:
            check_in_value = attendance.check_in

        # ===== CARI WO YANG COCOK — DIJALANIN SETIAP KALI SCAN, =====
        # ===== SEBELUM CEK APPROVAL EXISTING ATAU ENGGAK =====
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
        for wo in workorders:
            _logger.warning("MES DEBUG - WO=%s MO=%s state=%s wo.operator_id=%s mo.operator_id=%s",
                wo.name, wo.production_id.name, wo.state,
                wo.operator_id.name if wo.operator_id else "-",
                wo.production_id.operator_id.name if wo.production_id.operator_id else "-"
            )

        STATE_MAP = {
            "pending": "ready",
            "waiting": "ready",
            "ready": "ready",
            "progress": "running",
            "done": "done",
        }

        # ===== CEK APPROVAL YANG SUDAH ADA HARI INI =====
        existing = self.env["mes.scan.approval"].sudo().search([
            ("employee_id", "=", employee.id),
            ("check_in", ">=", today),
            ("check_in", "<", tomorrow),
        ], limit=1)

        if existing:
            existing.write({"scan_time": scan_time})

            # ===== Tambahkan WO baru yang belum ada di line_ids =====
            existing_wo_ids = existing.line_ids.mapped("workorder_id").ids
            new_workorders = workorders.filtered(lambda wo: wo.id not in existing_wo_ids)

            _logger.warning("MES DEBUG - existing_wo_ids: %s", existing_wo_ids)
            _logger.warning("MES DEBUG - new_workorders: %s", new_workorders.mapped("name"))

            if new_workorders:
                last_sequence = max(existing.line_ids.mapped("sequence") or [0])

                for idx, wo in enumerate(new_workorders, start=1):
                    self.env["mes.scan.approval.line"].sudo().create({
                        "approval_id": existing.id,
                        "sequence": last_sequence + idx,
                        "workorder_id": wo.id,
                        "qty_target": wo.production_id.product_qty,
                        # QTY ACTUAL = 0 karena WO baru, belum ada produksi sama sekali
                        "qty_actual": 0,
                        "state": STATE_MAP.get(wo.state, "ready"),
                    })

            return existing

        # ===== KALAU BELUM ADA APPROVAL SAMA SEKALI, BARU BIKIN =====
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
                # QTY ACTUAL = 0 karena WO baru, belum ada produksi sama sekali
                "qty_actual": 0,
                "state": STATE_MAP.get(wo.state, "ready"),
            })

        return approval

    @api.model
    def attendance_scan(self, barcode):
        result = self._mes_get_or_create_approval(barcode)

        if isinstance(result, dict) and "error" in result:
            return {"warning": result["error"]}

        if result:
            return {"success": f"Approval untuk {result.employee_id.name} siap."}

        return {"warning": "Barcode tidak dikenali."}

    @api.model
    def mes_kiosk_scan(self, barcode):
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

    def _get_leader_user(self):
        """
        Mengambil User Odoo dari Leader.

        Prioritas:
        1. Employee.user_id
        2. Fallback cari res.users berdasarkan nama Leader
        tanpa memperhatikan kapitalisasi.

        Contoh:
            MUSTAMIR
            Mustamir
            mustamir

        akan dianggap sama sementara.
        """

        self.ensure_one()

        return self._find_leader_user(
            self.leader_id
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
            self.leader_id
        )
        
    # =========================================================
    # REALTIME NOTIFICATION
    # =========================================================

    def _send_leader_notification(self):
        """
        Kirim realtime notification hanya ke user Odoo
        yang merupakan Leader dari Work Order ini.
        """

        self.ensure_one()

        leader_user = self._get_leader_user()

        if not leader_user:
            _logger.warning(
                "MES EDIT REQUEST: Leader %s belum memiliki user Odoo.",
                self.leader_id.name if self.leader_id else "-",
            )
            return

        if not leader_user.partner_id:
            _logger.warning(
                "MES EDIT REQUEST: User %s tidak memiliki partner.",
                leader_user.name,
            )
            return

        line = self.line_id.sudo()
        wo = self.workorder_id.sudo()
        production = wo.production_id.sudo()

        operator_name = (
            self.requested_by.sudo().name
            if self.requested_by
            else "-"
        )

        leader_name = (
            self.leader_id.sudo().name
            if self.leader_id
            else "-"
        )

        payload = {
            "request_id": self.id,

            "operator_name": operator_name,

            "leader_name": leader_name,

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

            "state": self.state,
        }

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
            self.id,
        )

    # =========================================================
    # APPROVE
    # =========================================================

    def action_approve(self):
        self.ensure_one()

        if self.state != "waiting":
            raise UserError(
                "Request ini sudah diproses sebelumnya."
            )

        leader_user = self._get_leader_user()

        if not leader_user:
            raise UserError(
                "Leader Work Order ini belum memiliki user Odoo."
            )

        if self.env.user != leader_user:
            raise UserError(
                "Anda bukan Leader dari Work Order ini. "
                "Hanya Leader yang dapat menyetujui request edit."
            )

        # =====================================================
        # APPROVE REQUEST
        # =====================================================

        self.write({
            "state": "approved",
            "approved_by": self.env.user.id,
            "approved_date": fields.Datetime.now(),
        })

        # =====================================================
        # NOTIFIKASI KE OPERATOR
        # =====================================================

        self._send_operator_result_notification(
            "approved"
        )

        # Notifikasi admin dikirim setelah Leader menekan OK pada popup Memo IT.
        return True

    def action_confirm_it_memo(self):
        """Konfirmasi Leader untuk mengirim pengajuan memo ke admin."""
        self.ensure_one()

        leader_user = self._get_leader_user()
        if self.env.user != leader_user:
            raise UserError("Hanya Leader Work Order yang dapat mengonfirmasi Memo IT.")
        if self.state != "approved":
            raise UserError("Request edit harus disetujui terlebih dahulu.")

        if not self.memo_notified:
            self._send_admin_memo_notification()
            self.write({"memo_notified": True})
        return True

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

        leader_user = self._get_leader_user()

        if not leader_user:
            raise UserError(
                "Leader Work Order ini belum memiliki user Odoo."
            )

        if self.env.user != leader_user:
            raise UserError(
                "Anda bukan Leader dari Work Order ini. "
                "Hanya Leader yang dapat menolak request edit."
            )

        # -----------------------------------------------------
        # 3. SIMPAN REJECT
        # -----------------------------------------------------

        self.write({
            "state": "rejected",
            "approved_by": self.env.user.id,
            "approved_date": fields.Datetime.now(),
        })

        # -----------------------------------------------------
        # 4. NOTIFIKASI OPERATOR
        # -----------------------------------------------------

        self._send_operator_result_notification(
            "rejected"
        )

        return True

    # =========================================================
    # NOTIFIKASI OPERATOR
    # =========================================================

    def _send_operator_result_notification(self, result):
        """
        Kirim hasil approval/rejection kembali ke operator.

        Ini optional untuk tahap sekarang, tapi gue pasang
        sekalian supaya operator tahu request-nya sudah diproses.
        """

        self.ensure_one()

        approval = self.line_id.sudo().approval_id.sudo()

        if not approval or not approval.employee_id:
            return

        # Akses employee harus sudo: tanpa itu Odoo dapat memakai model
        # hr.employee.public yang tidak mengenal field custom barcode_id.
        operator_employee = approval.employee_id.sudo()
        operator_user = operator_employee.user_id.sudo()

        if not operator_user or not operator_user.partner_id:
            return

        # Work Order tidak dapat dibaca oleh semua akun Leader. Karena hanya
        # dipakai sebagai isi pesan, gunakan akses internal untuk relasinya.
        workorder_name = self.workorder_id.sudo().name or "-"
        approver_name = self.approved_by.sudo().name or "-"

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

        self.env["bus.bus"]._sendone(
            operator_user.partner_id,
            "mes_edit_request_result",
            {
                "request_id": self.id,
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

    def _send_admin_memo_notification(self):
        """Kirim pengingat memo ke seluruh user administrator aktif."""

        self.ensure_one()

        admin_group = self.env.ref("base.group_system", raise_if_not_found=False)
        admin_users = admin_group.sudo().users.filtered(
            lambda user: user.active and user.partner_id
        ) if admin_group else self.env["res.users"]

        if not admin_users:
            _logger.warning(
                "MES EDIT REQUEST: Tidak ada user admin aktif untuk request_id=%s",
                self.id,
            )
            return

        workorder = self.workorder_id.sudo()
        production_name = workorder.production_id.sudo().name or "-"
        workorder_name = workorder.name or "-"
        payload = {
            "request_id": self.id,
            "title": "Pengajuan Memo Perubahan Data",
            "message": (
                "Ada pengajuan memo dari Produksi terkait perubahan data "
                f"(MO: {production_name}; Work Order: {workorder_name})."
            ),
        }

        for admin_user in admin_users:
            self.env["bus.bus"]._sendone(
                admin_user.partner_id,
                "mes_edit_request_admin_memo",
                payload,
            )

        _logger.info(
            "MES EDIT REQUEST: notifikasi memo dikirim ke %s admin, request_id=%s",
            len(admin_users),
            self.id,
        )

