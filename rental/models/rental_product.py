import logging
from heapq import nsmallest

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

RentalDurationUnits = [
    ('months', 'Month(s)'),
    ('days', 'Day(s)'),
    ('weeks', 'Week(s)'),
    ('years', 'Year(s)'),
    ('hours', 'Hour(s)'),
    ('minutes', 'Minute(s)'),
]


# relativedelta supports following:
#     self.years = 0
#     self.months = 0
#     self.days = 0
#     self.leapdays = 0
#     self.hours = 0
#     self.minutes = 0
#     self.seconds = 0
#     self.microseconds = 0
#     self.year = None
#     self.month = None
#     self.day = None
#     self.weekday = None
#     self.hour = None
#     self.minute = None
#     self.second = None
#     self.microsecond = None
#     self._has_time = 0


def get_tenure_value_price_tuple_list(my_dict, tenure_value, tenure_value_price_tuple_list=None):
    if tenure_value_price_tuple_list is None:
        tenure_value_price_tuple_list = []

    if my_dict.get(tenure_value, False):
        tenure_value_price_tuple_list.append(
            (tenure_value, my_dict.get(tenure_value, 0.0)))
        return tenure_value_price_tuple_list
    nearest_num_list = nsmallest(
        2, my_dict, key=lambda x: abs(x - tenure_value))
    if nearest_num_list:
        if tenure_value >= nearest_num_list[0]:
            tenure_value_price_tuple_list.append(
                (nearest_num_list[0], my_dict.get(nearest_num_list[0], 0.0)))
            tenure_value = tenure_value - nearest_num_list[0]
            get_tenure_value_price_tuple_list(
                my_dict, tenure_value, tenure_value_price_tuple_list)
            return tenure_value_price_tuple_list
        elif tenure_value < nearest_num_list[0] and len(nearest_num_list) == 2:
            if tenure_value >= nearest_num_list[1]:
                tenure_value_price_tuple_list.append(
                    (nearest_num_list[1], my_dict.get(nearest_num_list[1], 0.0)))
                tenure_value = tenure_value - nearest_num_list[1]
                get_tenure_value_price_tuple_list(
                    my_dict, tenure_value, tenure_value_price_tuple_list)
                return tenure_value_price_tuple_list


class RentalProductTemplate(models.Model):
    """ Inherit product.template modal to adding addition requirements for rental product """

    # Private attributes
    _inherit = 'product.template'

    # Default methods

    # Fields declaration
    rental_ok = fields.Boolean("Available for Rent")
    rental_tenure_ids = fields.One2many(
        "product.rental.tenure",
        "product_tmpl_id",
        "Rental Tenures",
    )
    description_rental = fields.Char("Rental Description")
    security_amount = fields.Float("Security Amount")
    tenure_type_standard = fields.Boolean(
        "Standard Tenure",
        default=True,
    )
    tenure_type_custom = fields.Boolean("Custom Tenure")
    rental_agreement_id = fields.Many2one(
        "rental.product.agreement",
        "Product Agreement",
    )
    rental_categ_id = fields.Many2one(
        "rental.product.category",
        "Rental Category",
    )

    # compute and search fields, in the same order of fields declaration

    # Constraints and onchanges

    # CRUD methods (and name_get, name_search, pass) overrides

    # Action methods
    def action_validate(self):
        self.ensure_one()
        pass

    # Business methods

    def get_product_tenure_price(self, tenure_value, tenure_uom_id):
        self.ensure_one()
        return_value_price_pair = []
        my_dict = self.get_rental_tenure_with_price(tenure_uom_id)
        rental_calculated_for = 0
        calculated_rental_price = 0
        if self.rental_ok:
            if my_dict and tenure_value:
                if self.env['ir.default'].sudo().get('res.config.settings',
                                                     'rental_rate_calculation_method') == "simple":
                    rental_calculated_for = 0.0
                    calculated_rental_price = 0.0
                else:
                    list_of_pairs = get_tenure_value_price_tuple_list(
                        my_dict, tenure_value, [])
                    if list_of_pairs:
                        return_value_price_pair = [sum(x) for x in zip(*list_of_pairs)]
                        if return_value_price_pair:
                            rental_calculated_for = return_value_price_pair[0]
                            calculated_rental_price = return_value_price_pair[1]
                if tenure_value > rental_calculated_for:
                    keys_tenure = my_dict.keys()
                    if keys_tenure:
                        min_tenure = min(keys_tenure)
                        price_for_min_tenure = my_dict.get(min_tenure, 0.0)
                        unit_rent_price = price_for_min_tenure / min_tenure
                        remaning_tenure = tenure_value - rental_calculated_for
                        remaning_tenure_amount = remaning_tenure * unit_rent_price
                        # update return_value_price_pair
                        temp_tenure = rental_calculated_for + \
                                      remaning_tenure
                        temp_price = calculated_rental_price + \
                                     remaning_tenure_amount
                        if return_value_price_pair:
                            return_value_price_pair[0] = temp_tenure
                            return_value_price_pair[1] = temp_price
                        else:
                            return_value_price_pair.append(temp_tenure)
                            return_value_price_pair.append(temp_price)
                    # Write message for how much time rent calculated
        return return_value_price_pair

    @api.model
    def get_applicable_rental_uom_ids(self):
        duration_list = []
        if self.rental_ok and self.rental_tenure_ids:
            for obj in self.rental_tenure_ids:
                duration_list.append(obj.rental_uom_id.id)
        return duration_list

    @api.model
    def get_rental_tenure_with_price(self, rental_uom):
        my_dict = {}
        if self.rental_ok:
            for rental_tenure_scheme in self.rental_tenure_ids.filtered(lambda r: r.rental_uom_id.id == rental_uom):
                my_dict.update({
                    rental_tenure_scheme.tenure_value: rental_tenure_scheme.rent_price
                })
            return my_dict

    @api.model
    def create(self, vals):
        if vals.get('rental_ok') and not vals.get('rental_tenure_ids'):
            raise UserError(_('Please add atleast one Rental Tenure'))
        return super(RentalProductTemplate, self).create(vals)

    def write(self, vals):
        res = super(RentalProductTemplate, self).write(vals)
        for rec in self:
            if rec.rental_ok and not rec.rental_tenure_ids:
                raise UserError(_('Please add atleast one Rental Tenure in "%s" product.' % rec.name))
        return res


class ProductProduct(models.Model):
    """ Inherit product.product modal to adding addition requirements for rental product """

    # Private attributes
    _inherit = 'product.product'

    # Business methods

    def get_product_tenure_price(self, tenure_value, tenure_uom_id):
        self.ensure_one()
        return self.product_tmpl_id.get_product_tenure_price(tenure_value, tenure_uom_id)

    @api.model
    def get_applicable_rental_uom_ids(self):
        return self.product_tmpl_id.get_applicable_rental_uom_ids()

    @api.model
    def get_rental_tenure_with_price(self, rental_uom):
        return self.product_tmpl_id.get_rental_tenure_with_price(rental_uom)


class ProductRentalTenure(models.Model):
    """ This modal is design to manage rental tenure for rental product"""

    # Private attributes
    _name = 'product.rental.tenure'
    _description = "Rental product rent tenures"

    # Fields declaration
    name = fields.Char(string="Tenure", compute="_compute_name")
    tenure_value = fields.Float("Tenure Value", default=1.0, required=True)
    max_tenure_value = fields.Float("Max. Tenure")
    rental_uom_id = fields.Many2one("uom.uom", "Tenure UOM", required=True,
                                    domain=lambda self: [('is_rental_uom', '=', True)])
    rent_price = fields.Float("Rent Price")
    is_default = fields.Boolean("Standard Tenure", help="Make default true to display this tenure on website in product page.")
    product_tmpl_id = fields.Many2one("product.template", "Product Template")
    currency_id = fields.Many2one(related="product_tmpl_id.currency_id", string="Currency")

    # rental_tenure_type = fields.Selection(
    #     [('standard', 'Standard Tenure'), ('custom', 'Custom Tenure')], "Rental Tenure Type", default="standard")

    # compute and search fields, in the same order of fields declaration
    @api.depends('product_tmpl_id', 'rental_uom_id')
    def _compute_name(self):
        for rec in self:
            name = "For " + str(rec.tenure_value) + " " + \
                   rec.rental_uom_id.name
            price_with_currency = ""
            if rec.currency_id and rec.currency_id.position == "before":
                price_with_currency = str(
                    rec.currency_id.symbol) + str(rec.rent_price)
            else:
                price_with_currency = str(
                    rec.rent_price) + str(rec.currency_id.symbol)
            rec.name = name + " @ " + price_with_currency

    # Constraints and onchanges
    @api.constrains('max_tenure_value')
    def _check_max_tenure_value(self):
        for rec in self:
            if rec.rental_uom_id and rec.max_tenure_value <= 0:
                raise UserError(_("Max Tenure Value for %r must be greter than zero." %
                                  rec.rental_uom_id.name))

    @api.onchange('max_tenure_value')
    def _onchange_max_tenure_value(self):
        if self.rental_uom_id and self.max_tenure_value <= 0:
            raise UserError(
                _("Max Tenure Value for %r must be greater than zero." % self.rental_uom_id.name))

    # Constraints and onchanges
    @api.constrains('rent_price')
    def _check_rent_price(self):
        for rec in self:
            if rec.rental_uom_id and rec.rent_price <= 0:
                raise UserError(_("Rent price for %r must be greter than zero." %
                                  rec.rental_uom_id.name))

    @api.onchange('rent_price')
    def _onchange_rent_price(self):
        if self.rental_uom_id and self.rent_price <= 0:
            raise UserError(
                _("Rent price for %r must be greter than zero." % self.rental_uom_id.name))

    # CRUD methods (and name_get, name_search, pass) overrides

    # Business methods


class RentalProductAgreement(models.Model):
    """ This modal is design to manage rental product agreement for rental product"""

    # Private attributes
    _name = 'rental.product.agreement'
    _description = "Rental Product Agreement"

    # Fields declaration
    name = fields.Char("Name", required=True)
    sequence = fields.Integer("Sequence", required=True)
    description = fields.Text(string="Description")
    agreement_file = fields.Binary("Product Agreement")

    filename = fields.Char('file name', readonly=True, store=False, compute='_getFilename')

    def _getFilename(self):
        for rec in self:
            if rec.name:
                rec.filename = rec.name[:10] + '.pdf'
            else:
                rec.filename = 'test' + '.pdf'


class ProductUom(models.Model):
    # Private attributes
    _inherit = 'uom.uom'

    # Fields declaration

    is_rental_uom = fields.Boolean("Rental UOM")
    duration_unit = fields.Selection(RentalDurationUnits, "Rental Unit")

    _sql_constraints = [
        ('unique_uom_duration_unit', 'unique(duration_unit)',
         _('There is already a record with this duration unit.'))
    ]


class RentalProductCategory(models.Model):
    """ This modal is design to manage rental category for rental product"""

    # Private attributes
    _name = 'rental.product.category'
    _description = "Rental product category"

    # Fields declaration

    name = fields.Char(string="Name", required=True, translate=True)
    hide_all_product = fields.Boolean("Hide Category from Website",
                                      help="Enable to hide this category and all products belong to this category from website.")
    product_count = fields.Integer(
        '# Products', compute='_compute_product_count',
        help="The number of products under this rental category.")
    image = fields.Binary("Category Image")

    # compute and search fields, in the same order of fields declaration

    def _compute_product_count(self):
        for categ in self:
            categ.product_count = self.env["product.template"].search_count([("rental_categ_id", '=', categ.id)])
