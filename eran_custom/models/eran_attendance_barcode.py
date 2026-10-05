from odoo import models, fields, api
import logging
from datetime import datetime, time, timedelta
from odoo.exceptions import UserError
import pytz

_logger = logging.getLogger(__name__)

class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"
 
    def name_get(self):
        result = []
        for rec in self:
            mo = rec.production_id.name or "-"
            wo = rec.name or "-"
            product = rec.production_id.product_id.display_name or "-"
            wc = rec.workcenter_id.name or "-"
            result.append((rec.id, f"{mo} | {wo} | {product} | {wc}"))
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

    scanned_production_id = fields.Many2one(
        "mrp.production",
        string="Scanned MO",
        help="QR MO Scan: tampilkan hanya MO ini. Kosong = ID MO Scan (semua MO hari ini).",
    )

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

    def _wo_line_labels(self, line):
        line = line.sudo()
        wo = line.workorder_id.sudo()
        return line, wo, {
            "leader": wo.leader_id.name if wo.leader_id else "-",
            "workcenter_name": wo.workcenter_id.name if wo.workcenter_id else "-",
            "production_name": wo.production_id.name if wo.production_id else "-",
            "product_name": wo.product_id.display_name if wo.product_id else "-",
            "wo_name": wo.name or "-",
        }

    def _render_wo_card(self, rec, line, labels, idx, total, status_text, footer_html=""):
        return f"""
        <div style="border:1px solid #28a745;border-radius:8px;padding:12px;
            margin-bottom:12px;background:#f4fbf6;">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <h4 style="margin:0;color:#0b72b9;">
                    📍 {labels['workcenter_name']} ({idx}/{total})
                </h4>
                <span style="background:#28a745;color:white;padding:2px 10px;
                    border-radius:12px;font-size:12px;font-weight:bold;">
                    {status_text}
                </span>
            </div>
            <p><b>Leader :</b> {labels['leader']}</p>
            <p><b>Manufacturing Order</b><br/>{labels['production_name']}</p>
            <p><b>Work Order</b><br/>{labels['wo_name']}</p>
            <p><b>Product</b><br/>{labels['product_name']}</p>
            <p><b>Target</b><br/>{line.qty_target}</p>
            <p><b>Output</b><br/>{line.qty_actual}</p>
            <p><b>Status</b><br/>{line.state.upper()}</p>
            {rec._render_downtime_html(line)}
            {rec._render_productivity_period_html(line)}
            {footer_html}
        </div>
        """
    
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
        "scanned_production_id",
    )
    def _compute_workorder_info(self):
        for rec in self:
            if not rec.check_in:
                rec.workorder_info = ""
                continue

            rec_sudo = rec.sudo()
            lines = rec_sudo.line_ids.sorted("sequence")
            filter_mo = rec.env.context.get("mes_filter_production_id") or rec.scanned_production_id.id
            if filter_mo:
                lines = lines.filtered(
                    lambda l: l.workorder_id.production_id.id == filter_mo
                )
            if not lines:
                rec.workorder_info = (
                    "<p style='color:#999;'>Tidak ada Work Order untuk MO ini.</p>"
                    if rec.env.context.get("mes_filter_production_id") or rec.scanned_production_id
                    else "<p style='color:#999;'>Tidak ada Work Order untuk hari ini.</p>"
                )
                continue

            active_lines = lines.filtered(lambda l: l.state != "done")
            done_lines = lines.filtered(lambda l: l.state == "done")
            html = []
            total_active = len(active_lines)

            for idx, line in enumerate(active_lines, start=1):
                line_sudo, wo, labels = rec_sudo._wo_line_labels(line)
                action_button = ""
                if line_sudo.state == "running":
                    action_button = f"""
                    <div style="text-align:right;margin-top:14px;">
                        <button onclick="mesStop({line_sudo.id})"
                            style="display:inline-block;padding:8px 16px;background:#dc3545;
                            color:white;border-radius:6px;font-size:13px;font-weight:bold;
                            border:none;cursor:pointer;">⏹️ STOP</button>
                    </div>
                    """
                else:
                    action_button = f"""
                    <div style="text-align:right;margin-top:14px;">
                        <button onclick="mesStart({line_sudo.id}, this)"
                            style="display:inline-block;padding:8px 16px;background:#28a745;
                            color:white;border-radius:6px;font-size:13px;font-weight:bold;
                            border:none;cursor:pointer;">▶️ START</button>
                    </div>
                    """

                html.append(rec_sudo._render_wo_card(
                    rec_sudo, line_sudo, labels, idx, total_active,
                    line_sudo.state.upper(), action_button,
                ))

            if not active_lines:
                html.append("""
                <p style="color:#28a745;font-weight:bold;margin-top:12px;">
                    🎉 Semua Work Order hari ini sudah selesai.
                </p>
                """)

            if done_lines:
                total_done = len(done_lines)
                html.append("""
                <hr style="margin:24px 0;border:none;border-top:2px dashed #ccc;" />
                <h3 style="color:#555;margin-bottom:12px;">Sudah Selesai</h3>
                """)
                for idx, line in enumerate(done_lines, start=1):
                    line_sudo, wo, labels = rec_sudo._wo_line_labels(line)
                    latest_request = line_sudo.edit_request_ids.sorted(
                        "create_date", reverse=True
                    )[:1]
                    if latest_request and latest_request.state == "waiting":
                        edit_button = """
                        <div style="text-align:right; margin-top:10px;">
                            <span style="font-size:12px; color:#888;">
                                ⏳ Menunggu persetujuan edit
                            </span>
                        </div>
                        """
                    elif latest_request and latest_request.state == "approved":
                        edit_button = """
                        <div style="text-align:right; margin-top:10px;">
                            <span style="font-size:12px; color:#28a745;">
                                ✅ Edit sudah disetujui
                            </span>
                        </div>
                        """
                    else:
                        edit_button = f"""
                        <div style="text-align:right;margin-top:10px;">
                            <button data-mes-edit="{line_sudo.id}"
                                style="display:inline-block;padding:6px 14px;background:#6c757d;
                                color:white;border-radius:5px;border:none;font-size:12px;
                                font-weight:bold;cursor:pointer;">✏️ Edit</button>
                        </div>
                        """
                    html.append(rec_sudo._render_wo_card(
                        rec_sudo, line_sudo, labels, idx, total_done,
                        "✅ SELESAI", edit_button,
                    ))

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

    @api.depends("state")
    def _compute_can_start(self):
        for line in self:
            line.can_start = line.state not in ("done", "running")

    def action_start(self):
        self.ensure_one()

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

        operator = self.approval_id.employee_id
        if operator:
            wo_vals = {"operator_id": operator.id}
            if not wo.production_id.operator_id:
                wo.production_id.write({"operator_id": operator.id})
            wo.write(wo_vals)

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
            self._close_open_problem_productivity(scan_time)

        self._sync_open_productivity_user_and_start(scan_time)

        self.write({
            "state": "running",
            "start_time": scan_time,
        })

        if self.approval_id.state != "running":
            self.approval_id.write({"state": "running"})

    def action_stop(self, reason, note=None, qty=None, loss_id=None, create_backorder=None, ng_qty=None,
                    start_hour=None, start_minute=None, end_hour=None, end_minute=None):
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

            if self._is_output_over_target(produced_qty):
                raise UserError("Output Melebihi Target")

            if create_backorder is None:
                create_backorder = False

            backorders = self._finish_production(
                produced_qty,
                create_backorder,
                ng_qty=ng_qty or 0.0,
            )

            if loss_id:
                self._record_problem_period(
                    loss_id,
                    start_hour, start_minute, end_hour, end_minute,
                    note=note,
                )
            elif start_hour not in (None, ""):
                latest_time = wo.time_ids.sorted("id", reverse=True)[:1]
                if latest_time:
                    self._apply_manual_productivity_period(
                        latest_time,
                        start_hour, start_minute, end_hour, end_minute,
                        note=note,
                    )

            self.write({
                "stop_time": now,
                "duration": self.duration + duration,
                "qty_actual": self.qty_actual + produced_qty,
                "state": "done",
            })
            return backorders

        else:
            if not loss_id:
                raise UserError("Alasan stop harus dipilih.")
            if start_hour in (None, "") or start_minute in (None, "") or end_hour in (None, "") or end_minute in (None, ""):
                open_times = wo.time_ids.filtered(lambda t: not t.date_end)
                if open_times:
                    latest_open = open_times.sorted("id", reverse=True)[0]
                    self._fill_productivity_end(latest_open, now)
                problem = self._create_problem_productivity(loss_id, now)
                if note:
                    problem.sudo().write({"description": note})
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
            else:
                start_dt, end_dt = self._record_problem_period(
                    loss_id,
                    start_hour, start_minute, end_hour, end_minute,
                    note=note,
                )
                self.env["mes.scan.approval.line.downtime"].sudo().create({
                    "line_id": self.id,
                    "loss_id": loss_id,
                    "note": note,
                    "start_time": start_dt,
                    "end_time": end_dt,
                })
                self.write({
                    "stop_time": start_dt,
                    "duration": self.duration + duration,
                    "state": "ready",
                })

    def _finish_production(self, produced_qty, create_backorder, ng_qty=0.0):
        self.ensure_one()

        wo = self.workorder_id.sudo()
        production = wo.production_id.sudo()
        now = fields.Datetime.now()
        good_qty = produced_qty or 0.0
        ng_qty = ng_qty or 0.0

        if ng_qty > 0:
            self.env["eran.ng.mrp.production"].sudo().create({
                "production_id": production.id,
                "workcenter_id": wo.workcenter_id.id,
                "quantity": ng_qty,
            })
            if hasattr(wo, "_get_ng_ids"):
                wo._get_ng_ids()

        production.invalidate_recordset(["ng_ids", "ng_total", "good_total", "qty_producing"])
        ng_total = sum(production.ng_ids.mapped("quantity"))
        new_good = (production.good_total or 0.0) + good_qty
        production.with_context(skip_good_total_check=True).write({
            "good_total": new_good,
            "qty_producing": new_good + ng_total,
        })

        wo.write({"qty_producing": good_qty})

        open_time = wo.time_ids.filtered(lambda t: not t.date_end)
        if open_time:
            self._fill_productivity_end(open_time[0], now)
        latest_time = wo.time_ids.sorted("date_start", reverse=True)[:1]
        if latest_time and not latest_time.date_end:
            self._fill_productivity_end(latest_time, now)

        if wo.state != "done":
            wo.with_context(skip_good_total_check=True).button_finish()

        remaining_wo = production.workorder_ids.filtered(
            lambda w: w.id != wo.id and w.state not in ("done", "cancel")
        )

        if remaining_wo:
            return self.env["mrp.production"]

        result = production.with_context(skip_good_total_check=True).button_mark_done()

        if isinstance(result, dict) and result.get("res_model") == "mrp.production.backorder":
            wizard = self.env[result["res_model"]].with_context(
                dict(result.get("context", {}), skip_good_total_check=True)
            ).create({})

            if create_backorder:
                existing = production.procurement_group_id.mrp_production_ids
                wizard.action_backorder()
                production.invalidate_recordset()
                new_mos = production.procurement_group_id.mrp_production_ids - existing
                new_mos = new_mos.filtered(lambda p: p.id != production.id)
                if not new_mos:
                    new_mos = production.procurement_group_id.mrp_production_ids.filtered(
                        lambda p: p.id != production.id
                    )
                return new_mos
            wizard.action_close_mo()
        return self.env["mrp.production"]

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

    def _is_output_over_target(self, produced_qty):
        self.ensure_one()
        target = self.qty_target or 0.0
        if target <= 0:
            return False
        return (self.qty_actual or 0.0) + produced_qty > target

    def _record_problem_period(self, loss_id, start_hour, start_minute, end_hour, end_minute, note=None):
        if start_hour in (None, "") or start_minute in (None, "") or end_hour in (None, "") or end_minute in (None, ""):
            raise UserError("Isi jam dari dan sampai untuk problem.")
        wo = self.workorder_id.sudo()
        start_dt, start_day, _ = self._dt_from_jakarta_hm(start_hour, start_minute)
        end_dt, _, _ = self._dt_from_jakarta_hm(end_hour, end_minute, start_day)
        if end_dt <= start_dt:
            end_dt, _, _ = self._dt_from_jakarta_hm(
                end_hour, end_minute, start_day + timedelta(days=1)
            )
        open_times = wo.time_ids.filtered(lambda t: not t.date_end)
        if open_times:
            self._fill_productivity_end(open_times.sorted("id", reverse=True)[0], start_dt)
        problem = self._create_problem_productivity(loss_id, start_dt)
        self._apply_manual_productivity_period(
            problem,
            start_hour, start_minute, end_hour, end_minute,
            note=note,
        )
        return start_dt, end_dt

    def _dt_from_jakarta_hm(self, hour, minute, base_day=None):
        tz = pytz.timezone("Asia/Jakarta")
        now_utc = fields.Datetime.now()
        now_local = pytz.utc.localize(now_utc).astimezone(tz)
        day = base_day or now_local.date()
        hour = int(hour)
        minute = int(minute)
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise UserError("Jam/menit tidak valid.")
        local_dt = tz.localize(datetime.combine(day, time(hour, minute, 0)))
        return local_dt.astimezone(pytz.utc).replace(tzinfo=None), day, hour + minute / 60.0

    def _apply_manual_productivity_period(self, time_rec, start_hour, start_minute, end_hour, end_minute, note=None):
        if time_rec is None or not time_rec:
            return
        if start_hour in (None, "") or start_minute in (None, "") or end_hour in (None, "") or end_minute in (None, ""):
            if note:
                time_rec.sudo().write({"description": note})
            return
        start_dt, start_day, start_float = self._dt_from_jakarta_hm(start_hour, start_minute)
        end_dt, end_day, end_float = self._dt_from_jakarta_hm(end_hour, end_minute, start_day)
        if end_dt <= start_dt:
            end_dt, end_day, end_float = self._dt_from_jakarta_hm(
                end_hour, end_minute, start_day + timedelta(days=1)
            )
        vals = {
            "start_date": start_day,
            "start_time": start_float,
            "end_date": end_day,
            "end_time": end_float,
            "date_start": start_dt,
            "date_end": end_dt,
        }
        if time_rec.loss_id:
            vals["loss_id"] = time_rec.loss_id.id
        if note:
            vals["description"] = note
        operator = self.workorder_id.sudo().operator_id or self.workorder_id.sudo().production_id.operator_id
        if operator:
            vals["operator_id"] = operator.id
        user = self._eran_operator_user()
        if user:
            vals["user_id"] = user.id
        time_rec.sudo().write(vals)

    def _eran_local_date_hour(self, dt):
        if not dt:
            return False, 0.0
        tz_record = self.with_context(tz="Asia/Jakarta")
        local = fields.Datetime.context_timestamp(tz_record, dt)
        return local.date(), local.hour + local.minute / 60.0 + local.second / 3600.0

    def _eran_operator_user(self):
        wo = self.workorder_id.sudo()
        employee = (
            wo.operator_id
            or wo.production_id.operator_id
            or self.approval_id.employee_id
        )
        if not employee:
            return self.env["res.users"]
        if employee.user_id:
            return employee.user_id.sudo()
        Users = self.env["res.users"].sudo()
        email = (employee.work_email or employee.private_email or "").strip()
        if email:
            user = Users.search([("login", "=ilike", email), ("active", "=", True)], limit=1)
            if user:
                return user
        name = (employee.name or "").strip()
        if not name:
            return self.env["res.users"]
        return Users.search([
            ("name", "=ilike", name),
            ("active", "=", True),
        ], limit=1)

    def _fill_productivity_start(self, time_rec, start_dt):
        start_date, start_hour = self._eran_local_date_hour(start_dt)
        vals = {
            "start_date": start_date,
            "start_time": start_hour,
        }
        operator = self.workorder_id.sudo().operator_id or self.workorder_id.sudo().production_id.operator_id
        if operator:
            vals["operator_id"] = operator.id
        user = self._eran_operator_user()
        if user:
            vals["user_id"] = user.id
        time_rec.sudo().write(vals)

    def _fill_productivity_end(self, time_rec, end_dt):
        end_date, end_hour = self._eran_local_date_hour(end_dt)
        time_rec.sudo().write({
            "end_date": end_date,
            "end_time": end_hour,
            "date_end": end_dt,
        })

    def _sync_open_productivity_user_and_start(self, start_dt):
        wo = self.workorder_id.sudo()
        open_times = wo.time_ids.filtered(lambda t: not t.date_end)
        if not open_times:
            return
        self._fill_productivity_start(open_times.sorted("id", reverse=True)[0], start_dt)

    def _create_problem_productivity(self, loss_id, start_dt):
        wo = self.workorder_id.sudo()
        start_date, start_hour = self._eran_local_date_hour(start_dt)
        vals = {
            "workorder_id": wo.id,
            "workcenter_id": wo.workcenter_id.id,
            "loss_id": loss_id,
            "start_date": start_date,
            "start_time": start_hour,
            "date_start": start_dt,
        }
        operator = wo.operator_id or wo.production_id.operator_id
        if operator:
            vals["operator_id"] = operator.id
        user = self._eran_operator_user()
        if user:
            vals["user_id"] = user.id
        return self.env["mrp.workcenter.productivity"].sudo().create(vals)

    def _close_open_problem_productivity(self, end_dt):
        wo = self.workorder_id.sudo()
        open_problems = wo.time_ids.filtered(
            lambda t: not t.date_end and t.loss_id and t.loss_id.loss_type != "productive"
        )
        for rec in open_problems:
            self._fill_productivity_end(rec, end_dt)

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

    @api.model
    def _mes_find_production_by_barcode(self, barcode):
        scanned = (barcode or "").strip()
        if not scanned:
            return self.env["mrp.production"]
        Production = self.env["mrp.production"].sudo()
        Workorder = self.env["mrp.workorder"].sudo()

        exact = Production.search([("name", "=", scanned)], limit=1)
        if exact:
            return exact

        scanned_norm = "".join(scanned.split()).upper()
        scanned_noslash = scanned_norm.replace("/", "").replace("-", "")
        for prod in Production.search([("name", "ilike", scanned.split("/")[0])], limit=40):
            mo_norm = "".join((prod.name or "").split()).upper()
            mo_noslash = mo_norm.replace("/", "").replace("-", "")
            if (
                scanned_norm == mo_norm
                or scanned_noslash == mo_noslash
                or (len(scanned_norm) >= 6 and scanned_norm in mo_norm)
                or (len(mo_norm) >= 6 and mo_norm in scanned_norm)
            ):
                return prod

        wo = Workorder.search([("name", "=", scanned)], limit=1)
        if wo:
            return wo.production_id
        wo = Workorder.search([("production_id.name", "=", scanned)], limit=1)
        if wo:
            return wo.production_id
        return Production.browse()

    def _mes_get_or_create_approval(self, barcode, production=None, require_attendance=True):
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
        return self._mes_build_approval(
            employee, production=production, require_attendance=require_attendance
        )

    def _mes_build_approval(self, employee, production=None, require_attendance=True):

        scan_time = fields.Datetime.now()
        tz = pytz.timezone("Asia/Jakarta")
        scan_time_local = pytz.utc.localize(scan_time).astimezone(tz)
        scan_hour = scan_time_local.hour + scan_time_local.minute / 60.0
        today, tomorrow = self._eran_jakarta_day_bounds(scan_time)

        # =========================================================
        # VALIDASI 1: WAJIB ABSEN DULU DI HR.ATTENDANCE
        # =========================================================

        attendance = self._eran_today_attendance(employee, scan_time)
        if require_attendance and not attendance:
            return {
                "error": (
                    f"{employee.name} belum melakukan absen masuk hari ini. "
                    "Silakan scan absen di mesin absensi terlebih dahulu."
                )
            }
        check_in_value = attendance.check_in if attendance else scan_time

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

        if production:
            workorders = production.workorder_ids.filtered(
                lambda wo: wo.state in ("pending", "waiting", "ready", "progress", "done")
            )
        else:
            domain = [
                "|",
                    ("operator_id", "=", employee.id),
                    ("production_id.operator_id", "=", employee.id),
                ("state", "in", ["pending", "waiting", "ready", "progress", "done"]),
                ("production_id.date_planned_start", ">=", today),
                ("production_id.date_planned_start", "<", tomorrow),
            ]
            workorders = self.env["mrp.workorder"].sudo().search(domain)
        _logger.debug("MES scan WO count=%s production=%s", len(workorders), production and production.name)

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
            existing.write({
                "scan_time": scan_time,
                "scanned_production_id": production.id if production else False,
            })

            existing_wo_ids = existing.line_ids.mapped("workorder_id").ids
            new_workorders = workorders.filtered(lambda wo: wo.id not in existing_wo_ids)

            if new_workorders:
                last_sequence = max(existing.line_ids.mapped("sequence") or [0])
                Line = self.env["mes.scan.approval.line"].sudo()
                Line.create([{
                    "approval_id": existing.id,
                    "sequence": last_sequence + idx,
                    "workorder_id": wo.id,
                    "qty_target": wo.production_id.product_qty,
                    "qty_actual": 0,
                    "state": STATE_MAP.get(wo.state, "ready"),
                } for idx, wo in enumerate(new_workorders, start=1)])

            return existing

        # =========================================================
        # BELUM ADA APPROVAL — BUAT BARU
        # =========================================================

        if not workorders:
            if production:
                return {"error": f"Tidak ada Work Order pada MO {production.name}."}
            return {"error": f"Tidak ada Work Order untuk {employee.name} hari ini."}

        approval = self.env["mes.scan.approval"].sudo().create({
            "employee_id": employee.id,
            "check_in": check_in_value,
            "scan_time": scan_time,
            "shift_id": workorders[:1].shift_id.id,
            "workcenter_id": workorders[:1].workcenter_id.id,
            "state": "ready",
            "scanned_production_id": production.id if production else False,
        })

        self.env["mes.scan.approval.line"].sudo().create([{
            "approval_id": approval.id,
            "sequence": seq,
            "workorder_id": wo.id,
            "qty_target": wo.production_id.product_qty,
            "qty_actual": 0,
            "state": STATE_MAP.get(wo.state, "ready"),
        } for seq, wo in enumerate(workorders, start=1)])

        return approval

    @api.model
    def attendance_scan(self, barcode):
        """
        Dipanggil oleh kiosk attendance bawaan Odoo.
        Catat hr.attendance lalu arahkan ke halaman sambutan custom.
        """
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

    @api.model
    def mes_mo_kiosk_scan(self, barcode):
        production = self._mes_find_production_by_barcode(barcode)
        if not production:
            return {"warning": "QR MO tidak dikenali. Scan QR di printout MO."}

        employee = production.operator_id
        if not employee:
            wo_ops = production.workorder_ids.mapped("operator_id").filtered(lambda e: e)
            employee = wo_ops[:1]
        if not employee:
            employee = self.sudo().search([("user_id", "=", self.env.uid)], limit=1)
        if not employee:
            return {"warning": f"MO {production.name} belum punya operator."}

        if employee.barcode:
            result = self._mes_get_or_create_approval(
                employee.barcode, production=production, require_attendance=False
            )
        else:
            result = self._mes_build_approval(
                employee, production=production, require_attendance=False
            )

        if isinstance(result, dict) and "error" in result:
            return {"warning": result["error"]}
        if not result:
            return {"warning": "Gagal membuka MO Scan."}

        form_view = self.env.ref("eran_custom.view_mes_scan_approval_form")
        return {
            "action": {
                "type": "ir.actions.act_window",
                "name": production.name,
                "res_model": "mes.scan.approval",
                "res_id": result.id,
                "view_mode": "form",
                "views": [(form_view.id, "form")],
                "target": "current",
                "context": {
                    "mes_filter_production_id": production.id,
                },
            }
        }

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

    previous_qty = fields.Float(
        string="Output Sebelum Edit",
        readonly=True,
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
            "qty_target": line.qty_target or 0,
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

    def _memo_context(self, old_qty=None):
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
            "current_qty": old_qty if old_qty is not None else rec.previous_qty or rec.current_qty or 0,
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

    def _get_memo_users(self):
        """Hanya Administrator dan IT yang terima notes/notif memo."""
        Users = self.env["res.users"].sudo()
        memo_users = Users.browse()
        admin = self.env.ref("base.user_admin", raise_if_not_found=False)
        if admin and admin.active and admin.partner_id:
            memo_users |= admin
        named = Users.search([
            ("active", "=", True),
            ("share", "=", False),
            "|", "|", "|", "|",
            ("login", "in", ["admin", "administrator", "it"]),
            ("name", "=ilike", "Administrator"),
            ("name", "=ilike", "Admin"),
            ("name", "=ilike", "IT"),
            ("name", "=ilike", "IT %"),
        ])
        memo_users |= named.filtered(lambda u: u.partner_id)
        it_employees = self.env["hr.employee"].sudo().search([
            "|", "|",
            ("department_id.name", "ilike", "IT"),
            ("job_id.name", "ilike", "IT"),
            ("name", "=ilike", "IT"),
        ])
        memo_users |= it_employees.mapped("user_id").filtered(
            lambda u: u.active and u.partner_id
        )
        if not memo_users:
            return self._get_admin_users()
        return memo_users

    def _apply_output_correction(self, new_qty):
        """Ubah output MES, Work Order, dan MO sesuai input Leader."""
        self.ensure_one()
        rec = self.sudo()
        line = rec.line_id
        if not line:
            raise UserError("Request edit tidak memiliki Work Order line.")

        old_qty = line.qty_actual or 0.0
        delta = new_qty - old_qty
        rec.new_qty = new_qty
        line.write({"qty_actual": new_qty})

        wo = rec.workorder_id
        if wo:
            wo_vals = {"qty_producing": new_qty}
            if "qty_produced" in wo._fields:
                wo_vals["qty_produced"] = new_qty
            wo.write(wo_vals)

        production = wo.production_id if wo else False
        if not production:
            return old_qty

        new_good = max((production.good_total or 0.0) + delta, 0.0)
        ng_total = getattr(production, "ng_total", 0.0) or 0.0
        prod_vals = {"good_total": new_good}
        if "qty_producing" in production._fields:
            prod_vals["qty_producing"] = new_good + ng_total
        production.with_context(skip_good_total_check=True).write(prod_vals)

        finish_moves = production.move_finished_ids.filtered(
            lambda move: move.product_id.id == production.product_id.id
            and move.state != "cancel"
        )
        if finish_moves:
            try:
                finish_moves.with_context(skip_good_total_check=True)._set_quantity_done(new_good)
            except Exception:
                _logger.warning(
                    "MES EDIT REQUEST: gagal update qty finished move MO %s request_id=%s",
                    production.name,
                    rec.id,
                    exc_info=True,
                )
            for move in finish_moves:
                lines = move.move_line_ids.filtered(lambda ml: ml.state != "cancel")
                if len(lines) == 1:
                    try:
                        lines.qty_done = new_good
                    except Exception:
                        _logger.warning(
                            "MES EDIT REQUEST: gagal update move line MO %s",
                            production.name,
                            exc_info=True,
                        )
        return old_qty

    def action_approve(self, new_qty=None):
        self.ensure_one()

        if self.state != "waiting":
            raise UserError(
                "Request ini sudah diproses sebelumnya."
            )

        self._check_leader_user()

        rec = self.sudo()
        qty = rec.new_qty if new_qty is None else new_qty
        try:
            qty = float(qty or 0.0)
        except (TypeError, ValueError):
            qty = 0.0
        if qty <= 0:
            raise UserError("Masukkan output terbaru yang benar (lebih dari 0).")
        target = rec.line_id.qty_target or 0.0
        if target and qty > target:
            raise UserError("Output Melebihi Target")

        old_qty = rec._apply_output_correction(qty)

        leader_name = self.env.user.name or rec.leader_id.name or "-"
        operator_name = rec.requested_by.name or "-"
        wo_name = rec.workorder_id.name or "-"
        mo_name = rec.workorder_id.production_id.name or "-"

        rec.write({
            "state": "approved",
            "approved_by": self.env.user.id,
            "approved_date": fields.Datetime.now(),
            "previous_qty": old_qty,
            "note": (
                f"✅ Disetujui oleh Leader: {leader_name}\n"
                f"Operator  : {operator_name}\n"
                f"MO        : {mo_name}\n"
                f"WO        : {wo_name}\n"
                f"Output lama: {old_qty}\n"
                f"Output baru: {qty}\n"
                f"Perlu konfirmasi memo ke IT."
            ),
        })

        rec._send_operator_result_notification("approved")
        return True

    def action_confirm_it_memo(self):
        """Konfirmasi Leader untuk mengirim pengajuan memo ke admin."""
        self.ensure_one()
        self._check_leader_user()
        rec = self.sudo()
        if rec.state != "approved":
            raise UserError("Request edit harus disetujui terlebih dahulu.")
        if not rec.memo_notified:
            rec._notify_administrators_memo(old_qty=rec.previous_qty)
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
        return rec._notify_administrators_memo(old_qty=rec.previous_qty)

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

    def _notify_administrators_memo(self, old_qty=None):
        """Kirim notes + popup ke Administrator dan IT saja."""
        self.ensure_one()
        rec = self.sudo()
        ctx = rec._memo_context(old_qty=old_qty)
        memo_users = rec._get_memo_users()

        if not memo_users:
            _logger.warning(
                "MES EDIT REQUEST: Tidak ada user Admin/IT untuk request_id=%s",
                rec.id,
            )
            return False

        message = (
            f"MO {ctx['production_name']}, atas nama {ctx['operator_name']}, "
            f"tanggal {ctx['date_str']}, Leader {ctx['leader_name']} "
            f"mengubah output dari {ctx['current_qty']} menjadi {ctx['new_qty']} "
            "dan akan membuat memo terkait perubahan data output."
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
                    <td style="padding: 6px; font-weight: bold;">Output Lama</td>
                    <td style="padding: 6px;">{ctx['current_qty']}</td>
                </tr>
                <tr>
                    <td style="padding: 6px; font-weight: bold;">Output Baru</td>
                    <td style="padding: 6px;">{ctx['new_qty']}</td>
                </tr>
            </table>
            <p><strong>Status:</strong> Disetujui oleh Leader. Memo perubahan data untuk Admin dan IT.</p>
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
            "new_qty": ctx["new_qty"],
        }

        for memo_user in memo_users:
            rec.env["bus.bus"]._sendone(
                memo_user.partner_id,
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
                partner_ids=memo_users.mapped("partner_id").ids,
                subject=note_title,
                body=f"<p>{message}</p>",
                model="mes.scan.approval.edit.request",
                res_id=rec.id,
                email_from=email_from,
            )
        except Exception:
            _logger.exception(
                "MES EDIT REQUEST: gagal kirim inbox Admin/IT, request_id=%s",
                rec.id,
            )

        created_note = False
        if "note.note" in rec.env:
            Note = rec.env["note.note"]
            created_notes = Note.browse()
            for memo_user in memo_users:
                stage = rec.env["note.stage"].search(
                    [("user_id", "=", memo_user.id)],
                    limit=1,
                )
                vals = {
                    "name": note_title,
                    "user_id": memo_user.id,
                    "memo": note_body,
                }
                if stage:
                    vals["stage_ids"] = [(6, 0, [stage.id])]
                created_notes |= Note.create(vals)
            created_note = created_notes[:1]

        rec.write({"memo_notified": True})
        _logger.info(
            "MES EDIT REQUEST: notes/notifikasi dikirim ke Admin/IT (%s user), request_id=%s",
            len(memo_users),
            rec.id,
        )
        return {
            "note_id": created_note.id if created_note else False,
            "note_name": created_note.name if created_note else note_title,
        }

    def _send_admin_memo_notification(self):
        """Alias lama: kirim notes dan popup ke administrator."""
        return self._notify_administrators_memo()
