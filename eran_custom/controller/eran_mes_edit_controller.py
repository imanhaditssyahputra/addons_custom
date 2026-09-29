import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class MesEditController(http.Controller):

    def _info_page(self, title, message, color="#28a745"):
        html = f"""
        <html>
        <head><meta charset="utf-8"/><title>{title}</title></head>
        <body style="font-family:-apple-system,Arial,sans-serif;background:#f4f4f4;
            display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
            <div style="background:white;border-radius:12px;padding:30px;
                box-shadow:0 4px 20px rgba(0,0,0,0.15);width:320px;text-align:center;">
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

    def _json(self, payload):
        return request.make_response(
            json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

    def _submit_edit_request(self, line_id):
        line = request.env["mes.scan.approval.line"].sudo().browse(line_id)
        if not line.exists():
            return False, "Line tidak ditemukan."
        if line.has_pending_edit:
            return False, "Request edit sudah diajukan dan sedang menunggu persetujuan."

        leader = line.leader_id.sudo()
        if not leader:
            return False, "Work Order ini belum memiliki Leader."

        Edit = request.env["mes.scan.approval.edit.request"].sudo()
        leader_user = Edit._find_leader_user(leader)
        if not leader_user:
            return False, f"Leader {leader.name} tidak memiliki User Odoo."

        edit_request = Edit.create({"line_id": line.id})
        edit_request._send_leader_notification()
        return True, (
            f"Permintaan edit untuk {line.workorder_id.name} "
            f"telah dikirim ke Leader {leader.name}."
        )

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

    @http.route("/mes/edit/<int:line_id>/request", type="http", auth="user")
    def mes_edit_request(self, line_id, **kwargs):
        ok, message = self._submit_edit_request(line_id)
        return self._info_page(
            "Request Terkirim" if ok else "Gagal",
            message,
            color="#28a745" if ok else "#dc3545",
        )

    @http.route(
        "/mes/edit/<int:line_id>/request-json",
        type="http",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def mes_edit_request_json(self, line_id, **kwargs):
        ok, message = self._submit_edit_request(line_id)
        return self._json({"success": ok, "message": message})
