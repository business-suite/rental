import logging

from odoo import models
from odoo.http import request

_logger = logging.getLogger(__name__)


class Website(models.Model):
    _inherit = 'website'

    def _get_rental_tenure_short_name(self, duration_unit, tenure_value):
        unit = duration_unit
        value = tenure_value
        uom_name = ''
        if unit == 'months' and value == 1:
            uom_name = 'month'
        elif unit == 'months' and value != 1:
            uom_name = 'months'

        if unit == 'days' and value == 1:
            uom_name = 'day'
        elif unit == 'days' and value != 1:
            uom_name = 'days'

        if unit == 'weeks' and value == 1:
            uom_name = 'week'
        elif unit == 'weeks' and value != 1:
            uom_name = 'weeks'

        if unit == 'years' and value == 1:
            uom_name = 'year'
        elif unit == 'years' and value != 1:
            uom_name = 'years'

        if unit == 'hours' and value == 1:
            uom_name = 'hour'
        elif unit == 'hours' and value != 1:
            uom_name = 'hours'

        if unit == 'minutes' and value == 1:
            uom_name = 'minute'
        elif unit == 'minutes' and value != 1:
            uom_name = 'minutes'
        return uom_name

    def get_cartline_popover_content(self, line_id):
        msg = ''
        sol_obj = request.env['sale.order.line'].sudo().browse(line_id)
        if sol_obj and sol_obj.is_rental_order:
            msg = msg + "Tenure " + str(sol_obj.rental_tenure).rstrip('0').rstrip('.') if '.' in str(
                sol_obj.rental_tenure) else str(sol_obj.rental_tenure)
            msg = msg + request.website._get_rental_tenure_short_name(sol_obj.rental_uom_id.duration_unit,
                                                                      sol_obj.rental_tenure)
            msg = msg + " @ "
            if request.website.currency_id.position == 'after':
                msg = msg + str(sol_obj.price_unit) + request.website.currency_id.symbol
            else:
                msg = msg + request.website.currency_id.symbol + str(sol_obj.price_unit)
            if sol_obj.product_id.security_amount > 0.0:
                if request.website.currency_id.position == 'after':
                    msg = msg + ' + ' + str(sol_obj.product_id.security_amount) + request.website.currency_id.symbol
                else:
                    msg = msg + ' + ' + request.website.currency_id.symbol + str(sol_obj.product_id.security_amount)
                msg = msg + " Security Amount"
        return msg

    def get_website_price(self, product=False, value=False):
        web_currency_id = request.website.currency_id
        converted_currency = False
        if product and value:
            product_currency_id = product.currency_id
            converted_currency = product_currency_id.compute(value, web_currency_id)
        return converted_currency
