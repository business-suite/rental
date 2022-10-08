import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _website_product_id_change(self, order_id, product_id, qty=0, **kwargs):
        res = super(SaleOrder, self)._website_product_id_change(order_id, product_id, qty, **kwargs)

        if self._context.get('rental_vals'):

            rental_vals = self._context.get('rental_vals')
            tenure_uom = int(rental_vals.get('tenure_uom')) if rental_vals.get('tenure_uom') else False
            tenure_value = float(rental_vals.get('tenure_value')) if rental_vals.get('tenure_value') else False
            tenure_price = float(rental_vals.get('tenure_price')) if rental_vals.get('tenure_price') else False
            product = self.env['product.product'].browse(product_id)
            security_amount = self.env["website"].get_website_price(product, product.security_amount)
            if product and product.rental_ok and tenure_uom:
                vals = {
                    'is_rental_order': True,
                    'price_unit': tenure_price,
                    'rental_uom_id': tenure_uom,
                    'rental_tenure': tenure_value,
                    'unit_security_amount': security_amount,
                }
                res.update(vals)

        return res

    def _cart_update(self, product_id=None, line_id=None, add_qty=0, set_qty=0, **kwargs):
        flag = 0
        tenure_rent_price = None
        if line_id:
            line_obj = self.env['sale.order.line'].browse(line_id)
            if line_obj and line_obj.is_rental_order:
                flag = 1
                tenure_rent_price = line_obj.price_unit

        res = super(SaleOrder, self)._cart_update(product_id, line_id, add_qty, set_qty, **kwargs)

        if res.get('line_id') and flag == 1 and res.get('quantity') != 0:
            line_obj = self.env['sale.order.line'].browse(res.get('line_id'))
            line_obj.price_unit = tenure_rent_price

            if line_obj.inital_rental_contract_id and line_obj.inital_rental_contract_id.rental_qty != line_obj.product_uom_qty:
                line_obj.inital_rental_contract_id.rental_qty = line_obj.product_uom_qty

        return res

    def _cart_find_product_line(self, product_id=None, line_id=None, **kwargs):
        # check if new line needs to be created forcefully or not

        rental_order = kwargs.get('rental_order')
        tenure_uom = int(kwargs.get('tenure_uom')) if kwargs.get('tenure_uom') else False
        tenure_value = float(kwargs.get('tenure_value')) if kwargs.get('tenure_value') else False

        if not line_id:
            flag = 0
            domain = [('order_id', '=', self.id), ('product_id', '=', product_id)]
            sol_obj = self.env['sale.order.line'].sudo().search(domain)
            if sol_obj:

                for sol in sol_obj:
                    if sol.is_rental_order and rental_order:
                        if sol.rental_tenure == tenure_value and sol.rental_uom_id.id == tenure_uom:
                            return self.env['sale.order.line'].sudo().browse(sol.id)
                        else:
                            flag = 1
                    if sol.is_rental_order and not rental_order:
                        flag = 1
                    if not sol.is_rental_order and rental_order:
                        flag = 1
                    if not sol.is_rental_order and not rental_order:
                        return self.env['sale.order.line'].sudo().browse(sol.id)

            if flag == 1:
                return self.env['sale.order.line']

        self.ensure_one()
        product = self.env['product.product'].browse(product_id)

        # split lines with the same product if it has untracked attributes
        if product and product.mapped('attribute_line_ids').filtered(
                lambda r: not r.attribute_id.create_variant) and not line_id:
            return self.env['sale.order.line']

        domain = [('order_id', '=', self.id), ('product_id', '=', product_id)]
        if line_id:
            domain += [('id', '=', line_id)]
        return self.env['sale.order.line'].sudo().search(domain)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _get_display_price(self, product):
        res = super(SaleOrderLine, self)._get_display_price(product)
        if self._context.get("rental_vals"):
            price_unit = float(self._context.get("rental_vals").get("tenure_price"))
            return price_unit
        return res


class RentalOrderContract(models.Model):
    _inherit = "rental.order.contract"

    rental_qty = fields.Float(
        "Quantity",
        readonly=True,
        tracking=True,
        related='sale_order_line_id.product_uom_qty',
    )
