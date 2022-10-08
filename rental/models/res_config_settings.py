import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Fields declaration

    rental_rate_calculation_method = fields.Selection(
        [
            ('dynamic', 'Dynamic Calculation'),
            ('simple', 'Simple Calculation')
        ],
        string="Rental Rate Calculation Method",
        help="* 'Dynamic' means product(s) not delivered yet.\n"
             " * 'Simple' means some product(s) delivered but some product(s) not.\n"
    )
    security_refund_product_id = fields.Many2one(
        "product.product",
        "Rental Security Refund Product",
    )
    auto_generate_rental_in_move = fields.Boolean(
        "Auto Generate Stock Moves",
        help="Automatically generate incoming stock moves when rental contract get expired.",
    )

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        IRDefault = self.env['ir.default'].sudo()
        rental_rate_calculation_method = IRDefault.get(
            'res.config.settings', 'rental_rate_calculation_method') or "dynamic"
        auto_generate_rental_in_move = IRDefault.get(
            'res.config.settings', 'auto_generate_rental_in_move')
        try:
            security_refund_product_id = IRDefault.get(
                'res.config.settings', 'security_refund_product_id').id
        except Exception as e:
            try:
                security_refund_product_id = self.env.ref(
                    'businesssuite_rental.rental_security_payment_product_demo_data').id
            except:
                security_refund_product_id = False

        res.update(
            rental_rate_calculation_method=rental_rate_calculation_method,
            auto_generate_rental_in_move=auto_generate_rental_in_move,
            security_refund_product_id=security_refund_product_id,
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        IRDefault = self.env['ir.default'].sudo()
        IRDefault.set('res.config.settings', 'security_refund_product_id', self.security_refund_product_id.id)
        IRDefault.set('res.config.settings', 'rental_rate_calculation_method',
                      self.rental_rate_calculation_method or "dynamic")
        IRDefault.set('res.config.settings', 'auto_generate_rental_in_move', self.auto_generate_rental_in_move)
        return True
