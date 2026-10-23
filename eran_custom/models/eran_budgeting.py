from odoo import api, fields, models, _
from odoo.tools import is_html_empty
from odoo.exceptions import ValidationError, UserError
import json
import logging
_logger = logging.getLogger(__name__)

class EranBudgeting(models.Model):
    _name = 'eran.budgeting'
    _description = 'Eran Budgeting'
    _rec_name = 'budgeting_name'

    budgeting_name = fields.Char(string='Budgeting Name', required=True)
    department_id = fields.Many2one('hr.department', string='Department', required=True)
    description = fields.Text(string='Description')
    saldo_awal = fields.Float(string='Saldo Awal', required=True)
    amount = fields.Float(string='Amount', required=True)
    date_budget = fields.Date(string='Budget Date', required=True)
    sisa_budget = fields.Float(string='Sisa Budget', compute='_compute_sisa_budget', store=True)

    @api.depends('amount','department_id')
    def _compute_sisa_budget(self):
        for record in self:
            if record.department_id:
                po_lines = self.env['purchase.order.line'].search([
                    ('department_id', '=', record.department_id.id),
                    ('state', 'in', ['purchase', 'done'])
                ])
                
                # 2. Jumlahkan seluruh subtotal (price_subtotal) dari PO Line tersebut
                total_terpakai = sum(line.price_subtotal for line in po_lines)
                
                # 3. Sisa Budget = Anggaran Awal - Total Terpakai
                record.sisa_budget = record.amount - total_terpakai
            else:
                record.sisa_budget = record.amount