import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    rental_contract_id = fields.Many2one(
        "rental.order.contract", "Rental Contract")
