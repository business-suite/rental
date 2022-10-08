import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class RentalReasonWizard(models.TransientModel):
    _name = 'rental.reason.wizard'
    _description = "Rental Wizard Reason"

    # Default methods

    @api.model
    def _get_rental_contract(self):
        sol_id = self._context.get('active_id', False)
        if sol_id:
            sol_obj = self.env["sale.order.line"].browse(sol_id)
            if sol_obj and sol_obj.current_rental_contract_id:
                return sol_obj.current_rental_contract_id.id
            else:
                return sol_obj.inital_rental_contract_id and sol_obj.inital_rental_contract_id.id

    # Fields declaration

    rental_contract_id = fields.Many2one(
        "rental.order.contract",
        string="Rental Contract",
        default=_get_rental_contract,
    )
    reason_id = fields.Many2one(
        "rental.reason",
        string="Reason",
        required="1",
    )
    additional_comment = fields.Text(string="Additional Comment")

    def do_cancel(self):
        self.ensure_one()
        # raise Warning("Canceling reason")
        if self.rental_contract_id:
            self.rental_contract_id.sale_order_line_id.rental_state = "cancel"
            reason_msg = "Cancel Reason : " + self.reason_id.name + "\n" + \
                         self.reason_id.description + "\n" + self.additional_comment
            self.rental_contract_id.message_post(
                reason_msg, subtype='mail.mt_comment', message_type='comment')
