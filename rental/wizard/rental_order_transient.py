import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

RentalDurationUnits = [
    ('minutes', 'Minute(s)'),
    ('hours', 'Hour(s)'),
    ('days', 'Day(s)'),
    ('weeks', 'Week(s)'),
    ('months', 'Month(s)'),
    ('years', 'Year(s)')
]


class RentalOrderWizard(models.TransientModel):
    # Private attributes
    _name = 'businesssuite.rental.order.wizard'
    _description = 'Wizard model to add rental product to SO'

    # Default methods
    def _default_name(self):
        pass

    # Fields declaration
    order_id = fields.Many2one(
        "sale.order",
        default=lambda self: self._context.get('active_id', False),
        required=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="order_id.pricelist_id.currency_id",
        string="Currency",
        required=True,
    )
    product_id = fields.Many2one("product.product", string='Rental Product', domain=[('rental_ok', '=', True)],
                                 required=True)
    rental_tenure_id = fields.Many2one(comodel_name="product.rental.tenure", string="Rental Tenure Id", default=False)
    quantity = fields.Float('Quantity', required=True, default=1.0)
    rental_tenure_type = fields.Selection(
        [('standard', 'Standard Tenure'), ('custom', 'Custom Tenure')], "Rental Tenure Type", default="standard")
    unit_security_amount = fields.Float(
        'Security Unit Amount', required=True, digits='Product Price', default=0.0)
    rental_uom_id = fields.Many2one("uom.uom", "Tenure UOM", required=True, domain=lambda self: [
        ('is_rental_uom', '=', True)])
    rental_tenure = fields.Float("Rental Tenure")
    rental_tenure_ids_domain = fields.Many2many(
        "product.rental.tenure",
        "Rental Tenure Ids for domain",
        compute="compute_product_id_change_tenure",
    )
    rental_uom_ids_domain = fields.Many2many(
        "uom.uom",
        "Tenure UOM for domain",
        domain=lambda self: [('is_rental_uom', '=', True)],
        compute="compute_product_id_change_uom",
    )

    # compute and search fields, in the same order of fields declaration

    # Constraints and onchanges

    @api.depends('product_id')
    def compute_product_id_change_tenure(self):
        self.rental_tenure_ids_domain = []
        product = self.product_id
        if product and product.product_tmpl_id and product.product_tmpl_id.rental_tenure_ids:
            self.rental_tenure_ids_domain = product.product_tmpl_id.rental_tenure_ids.ids

    @api.depends('product_id')
    def compute_product_id_change_uom(self):
        self.rental_uom_ids_domain = []
        product = self.product_id
        if product and product.product_tmpl_id:
            self.rental_uom_ids_domain = product.product_tmpl_id.get_applicable_rental_uom_ids()

    @api.onchange('rental_tenure_id')
    def onchange_rental_tenure_id(self):
        for rec in self:
            if rec.rental_tenure_id:
                rec.rental_tenure = rec.rental_tenure_id.tenure_value
                rec.rental_uom_id = rec.rental_tenure_id.rental_uom_id.id

    @api.onchange('product_id')
    def product_id_change(self):
        self.ensure_one()
        if self.product_id:
            product = self.product_id.with_context(
                lang=self.order_id.partner_id.lang,
                partner=self.order_id.partner_id.id,
                quantity=self.quantity,
                date=self.order_id.date_order,
                pricelist=self.order_id.pricelist_id.id,
            )
            self.unit_security_amount = self.product_id.currency_id.compute(
                self.unit_security_amount or self.product_id.security_amount, self.order_id.pricelist_id.currency_id)
            self.quantity = 1.0
            self.rental_tenure_id = False
            self.rental_uom_id = False
        else:
            self.unit_security_amount = 0.0
            self.rental_tenure_id = False
            self.quantity = 0.0
            self.rental_uom_id = False
            self.rental_tenure = 0.0
            self.rental_tenure_id = False

    # CRUD methods (and name_get, name_search, pass) overrides

    def action_add_rental_product(self):
        self.ensure_one()
        if self.quantity <= 0:
            raise UserError(_("Qty must be greater than 0."))
        if self.rental_tenure_type == "standard" and not self.rental_tenure_id:
            raise UserError(_("Please select rental tenure scheme for standard type of tenure."))
        if self.rental_tenure <= 0:
            raise UserError(_("Rental tenure must be greater than 0."))
        if self.product_id:
            taxes_ids = []
            if self.product_id.taxes_id:
                taxes_ids = self.product_id.taxes_id.ids
            rental_uom_id = self.rental_uom_id.id
            rental_tenure = self.rental_tenure
            return_value_price_pair = self.product_id.get_product_tenure_price(
                rental_tenure, rental_uom_id)
            price_unit = 0.0
            if return_value_price_pair:
                rental_tenure = return_value_price_pair[0]
                price_unit = return_value_price_pair[1]

            sol_values = {
                'order_id': self._context['active_id'],
                'product_id': self.product_id.id,
                'is_rental_order': True,
                'price_unit': self.product_id.currency_id.compute(price_unit, self.order_id.pricelist_id.currency_id),
                'product_uom': 1,  # unit
                'product_uom_qty': self.quantity,
                'tax_id': [(6, 0, taxes_ids)],
                'rental_uom_id': rental_uom_id,
                'rental_tenure': rental_tenure,
                # 'rental_status': "new",
                'unit_security_amount': self.product_id.currency_id.compute(
                    self.unit_security_amount or self.product_id.security_amount,
                    self.order_id.pricelist_id.currency_id),
            }
            self.env['sale.order.line'].create(sol_values)
            return True

    # Business methods
