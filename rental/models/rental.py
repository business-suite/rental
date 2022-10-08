import logging
from datetime import *

from dateutil.relativedelta import *

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class RentalOrderContract(models.Model):
    """ Inherit product.template modal to adding addition requirements for order_id.partner_shipping_idrental product """

    # Private attributes

    _name = "rental.order.contract"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "id desc"
    _description = "Rental Order Contract"

    # Fields declaration

    name = fields.Char("Contract",
                       required=True,
                       default=lambda self: _('New'),
                       readonly=True
                       )
    sale_order_line_id = fields.Many2one(
        "sale.order.line",
        "Sale Order Line",
        required=True,
        ondelete='cascade'
    )
    rental_sequence = fields.Char(
        related="sale_order_line_id.rental_sequence",
        string="Rental Order Lines",
        readonly=True
    )
    start_time = fields.Datetime(
        string='Start Time',
        compute='_compute_rental_start_time',
        inverse='_set_rental_start_time',
        store=True,
        states={'closed': [('readonly', True)], 'expired': [('readonly', True)]},
        tracking='1',
    )
    end_time = fields.Datetime(
        string='End Time',
        compute='_compute_rental_end_time',
        store=True,
        tracking='1',
    )
    rental_product_id = fields.Many2one(
        'product.product',
        related='sale_order_line_id.product_id',
        string="Rental Product",
        readonly=True,
        store=True,
    )
    rental_customer_id = fields.Many2one(
        'res.partner',
        related='sale_order_line_id.order_id.partner_id',
        string="Customer",
        readonly=True,
        store=True,
    )
    product_rental_agreement_id = fields.Many2one(
        "rental.product.agreement",
        "Agreement",
        required=True,
    )
    state = fields.Selection(
        [('new', 'Draft'), ('ready', 'Ready'), ("in_progress", "In Progress"), ("expired", "Expired"),
         ('closed', 'Closed')],
        string="State",
        default="new",
    )
    rental_qty = fields.Float(
        "Quantity",
        required=True,
        readonly=True,
        tracking='1',
    )
    rental_uom_id = fields.Many2one(
        "uom.uom",
        "Tenure UOM",
        required=True,
        domain=lambda self: [('is_rental_uom', '=', True)],
        readonly=True,
    )
    rental_tenure = fields.Float(
        "Tenure",
        required=True,
        readonly=True,
    )
    rental_invoice_ids = fields.Many2many(
        "account.move",
        "rental_contract_invoice_rel",
        "rental_contract_id",
        "rental_invoice_id",
        "Rental Invoice",
        compute="_get_rental_invoiced",
    )
    invoice_line_ids = fields.One2many(
        "account.move.line",
        "rental_contract_id",
        "Invoice Lines",
        readonly=True,
    )
    create_date = fields.Datetime('Create Date')
    closed_time = fields.Datetime('Closed Time')
    stock_move_ids = fields.Many2many(
        "stock.move",
        "rental_stock_move_contract_id",
        "contract_id",
        "stock_move_id",
        "Stock Moves",
        readonly=True,
    )
    rental_delivery_status = fields.Selection(
        [
            ('delivery_waiting', 'Not Delivered'),
            ('partial_deliver', 'Partial Delivered'),
            ('all_delivered', 'Delivered'),
            ('receiving_waiting', 'Not Received'),
            ('partial_receive', 'Partial Received'),
            ('all_received', 'Received'),
        ],
        string="Delivery Status",
        store=True,
        compute="_compute_rental_delivery_status",
        help="* The 'Not Delivered' status means product(s) not delivered yet.\n"
             " * The 'Partial Delivered' status means some product(s) delivered but some product(s) not.\n"
             " * The 'Delivered' status means all product has been delivered.\n"
             " * The 'Not Received' status is used when user cancel invoice.\n"
             " * The 'Partial Received' status is used when user cancel invoice.\n"
             " * The 'Received' status is used when user cancel invoice.\n"
    )
    price_unit = fields.Float(
        'Unit Price',
        required=True,
        digits='Product Price',
        default=0.0,
    )
    price_subtotal = fields.Monetary(
        compute='_compute_amount',
        string='Subtotal',
        readonly=True,
        store=True,
    )
    price_tax = fields.Float(
        compute='_compute_amount',
        string='Taxes',
        readonly=True,
        store=True,
    )
    price_total = fields.Monetary(
        compute='_compute_amount',
        string='Total',
        readonly=True,
        store=True,
    )
    tax_ids = fields.Many2many(
        'account.tax',
        string='Taxes on Price',
        domain=['|', ('active', '=', False), ('active', '=', True)],
        compute="_get_sol_tax_ids",
    )
    discount = fields.Float(
        string='Discount (%)',
        digits='Discount',
        default=0.0,
    )
    currency_id = fields.Many2one(
        related='sale_order_line_id.order_id.currency_id',
        store=True,
        string='Currency',
        readonly=True,
    )
    company_id = fields.Many2one(
        related='sale_order_line_id.order_id.company_id',
        string='Company',
        store=True,
        readonly=True,
    )
    rental_note = fields.Text(
        "Note",
        states={'closed': [('readonly', True)], 'expired': [('readonly', True)]},
    )
    invoice_created = fields.Boolean(
        "Invoiced",
        compute="_get_invoiced_delivered_returned",
    )
    out_delivery_created = fields.Boolean(
        "Delivered",
        compute="_get_invoiced_delivered_returned",
    )
    return_delivery_created = fields.Boolean(
        "Returned",
        compute="_get_invoiced_delivered_returned",
    )
    is_renewal_contract = fields.Boolean("Renewal Contract")
    # attachment_id = fields.Many2one()
    total_deposit_security_amount = fields.Float(
        related='sale_order_line_id.total_deposit_security_amount',
        store=True,
        readonly=True,
        string='Security Deposit',
    )

    # compute and search fields, in the same order of fields declaration

    @api.depends('stock_move_ids.state')
    def _compute_rental_start_time(self):
        for obj in self:
            if not obj.start_time and obj.stock_move_ids:
                rental_out_stock_moves = obj.stock_move_ids.filtered(
                    lambda r: r.picking_type_id.code == "outgoing")
                if rental_out_stock_moves:
                    obj.start_time = rental_out_stock_moves[0].date
                    obj.sale_order_line_id.current_start_time = obj.start_time

    def _set_rental_start_time(self):
        # Make start time field writable
        pass

    @api.depends('stock_move_ids.state', 'start_time')
    def _compute_rental_end_time(self):
        for obj in self:
            if obj.start_time:
                obj.end_time = obj.calculate_end_time()
                obj.sale_order_line_id.current_end_time = obj.end_time

    @api.depends('sale_order_line_id.invoice_lines', 'sale_order_line_id.invoice_status')
    def _get_rental_invoiced(self):
        """        """
        for contract in self:
            invoice_ids = contract.sale_order_line_id.mapped('invoice_lines').filtered(
                lambda r: r.rental_contract_id == contract).mapped('move_id').filtered(
                lambda r: r.move_type in ['out_invoice', 'out_refund'])
            contract.update({
                'rental_invoice_ids': invoice_ids.ids
            })

    @api.depends('stock_move_ids.state')
    def _compute_rental_delivery_status(self):
        """        """
        for contract in self:
            rental_out_stock_moves = contract.stock_move_ids.filtered(
                lambda r: r.picking_type_id.code == "outgoing")
            rental_in_stock_moves = contract.stock_move_ids.filtered(
                lambda r: r.picking_type_id.code == "incoming")
            contract.update({"rental_delivery_status": "delivery_waiting"})
            if rental_out_stock_moves:
                if len(rental_out_stock_moves) == len(rental_out_stock_moves.filtered(lambda r: r.state == "done")):
                    contract.set_contract_in_progress()
                    contract.update({"rental_delivery_status": "all_delivered"})
                elif rental_out_stock_moves.filtered(lambda r: r.state == "done"):
                    contract.update({"rental_delivery_status": "partial_deliver"})
            if rental_in_stock_moves:
                if len(rental_in_stock_moves) == len(rental_in_stock_moves.filtered(lambda r: r.state == "done")):
                    contract.set_contract_closed()
                    contract.update({"rental_delivery_status": "all_received"})
                elif rental_in_stock_moves.filtered(lambda r: r.state == "done"):
                    contract.update({"rental_delivery_status": "partial_receive"})
                elif contract.state == "expired" and len(rental_out_stock_moves) == len(
                        rental_out_stock_moves.filtered(lambda r: r.state == "done")):
                    contract.update({"rental_delivery_status": "receiving_waiting"})

    # @api.depends('rental_qty', 'discount', 'price_unit', 'tax_ids', 'sale_order_line_id.tax_id')
    # To remove warning Field rental.order.contract.price_subtotal depends on non-stored field rental.order.contract.tax_ids

    @api.depends('rental_qty', 'discount', 'price_unit', 'sale_order_line_id.tax_id')
    def _compute_amount(self):
        """
        Compute the amounts of the Rental contract for  linked SO line.
        """
        for rental_contract in self:
            price = rental_contract.price_unit * \
                    (1 - (rental_contract.discount or 0.0) / 100.0)
            taxes = rental_contract.tax_ids.compute_all(
                price,
                rental_contract.sale_order_line_id.order_id.currency_id,
                rental_contract.rental_qty,
                product=rental_contract.sale_order_line_id.product_id,
                partner=rental_contract.sale_order_line_id.order_id.partner_id
            )
            rental_contract.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })

    @api.depends('sale_order_line_id.tax_id')
    def _get_sol_tax_ids(self):
        for contract in self:
            contract.tax_ids = contract.sudo().sale_order_line_id.tax_id.ids

    @api.depends('invoice_line_ids', 'stock_move_ids')
    def _get_invoiced_delivered_returned(self):
        for contract in self:
            if contract.invoice_line_ids:
                contract.invoice_created = True
            else:
                contract.invoice_created = False

            if contract.stock_move_ids.filtered(lambda r: r.picking_type_id.code == "outgoing"):
                contract.out_delivery_created = True
            else:
                contract.out_delivery_created = False

            if contract.stock_move_ids.filtered(lambda r: r.picking_type_id.code == "incoming"):
                contract.return_delivery_created = True
            else:
                contract.return_delivery_created = False

    def set_contract_in_progress(self):
        for contract in self:
            if contract.state == "ready":
                contract.write({
                    'state': "in_progress"
                })
                if contract == contract.sale_order_line_id.current_rental_contract_id:
                    contract.sale_order_line_id.write(
                        {"rental_state": "in_progress"})
                elif contract == contract.sale_order_line_id.inital_rental_contract_id:
                    contract.sale_order_line_id.write(
                        {"rental_state": "in_progress"})

    def set_contract_closed(self):
        for contract in self:
            contract.write({
                'state': "closed",
                'closed_time': fields.datetime.now(),
            })
            contract.post_msg_closed_reason()
            if contract == contract.sale_order_line_id.current_rental_contract_id:
                contract.sale_order_line_id.write(
                    {"rental_state": "closed"})
            elif contract.state == "closed" and contract == contract.sale_order_line_id.inital_rental_contract_id:
                contract.sale_order_line_id.write(
                    {"rental_state": "closed"})

    def set_to_ready(self):
        for contract in self:
            contract.write({
                'state': "ready"
            })
            if contract == contract.sale_order_line_id.current_rental_contract_id:
                contract.sale_order_line_id.write(
                    {"rental_state": "confirm"})
            elif contract == contract.sale_order_line_id.inital_rental_contract_id:
                contract.sale_order_line_id.write(
                    {"rental_state": "confirm"})

    # Constraints and onchanges

    # CRUD methods (and name_get, name_search, pass) overrides

    def unlink(self):
        if self.filtered(lambda x: x.state not in ('new')):
            raise UserError(
                _('You can not delete a rental contract which is not in Draft state.'))
        return super(RentalOrderContract, self).unlink()

    # Action methods

    def action_confirm(self):
        """ Create contract sequence """
        for contract in self:
            if contract.company_id.id:
                contract.write({
                    'name': self.env['ir.sequence'].with_company(contract.company_id.id).next_by_code(
                        'rental.order.contract') or _('New'),
                })
                contract.set_to_ready()

    def view_outgoing_delivery_order(self):
        self.ensure_one()
        action = self.env.ref('stock.action_picking_tree_all').read()[0]
        rental_out_picking_ids = self.stock_move_ids.filtered(
            lambda r: r.picking_type_id.code == "outgoing").mapped("picking_id")
        if len(rental_out_picking_ids) > 1:
            action['domain'] = [('id', 'in', rental_out_picking_ids.ids)]
        elif rental_out_picking_ids:
            action['views'] = [
                (self.env.ref('stock.view_picking_form').id, 'form')]
            action['res_id'] = rental_out_picking_ids.id
        else:
            action['domain'] = [('id', 'in', [])]
        return action

    def view_return_delivery_order(self):
        self.ensure_one()
        action = self.env.ref('stock.action_picking_tree_all').read()[0]
        rental_in_picking_ids = self.stock_move_ids.filtered(
            lambda r: r.picking_type_id.code == "incoming").mapped("picking_id")
        if len(rental_in_picking_ids) > 1:
            action['domain'] = [('id', 'in', rental_in_picking_ids.ids)]
        elif rental_in_picking_ids:
            action['views'] = [
                (self.env.ref('stock.view_picking_form').id, 'form')]
            action['res_id'] = rental_in_picking_ids.id
        else:
            action['domain'] = [('id', 'in', [])]
        return action

    def closed_rental_contract(self):
        """  Before closing the contract we have to implement some checking policy"""
        for rec in self:
            rec.write({
                "state": "closed",
                # "closed_date": fields.Datetime.now
            })
            rec.post_msg_closed_reason()

    def post_msg_closed_reason(self):
        rental_reason_id = self.env.ref(
            'businesssuite_rental.rental_reason_demo_data_closed')
        reason_msg = _(
            "Rental product(s) has been received from that's why contract has been closed.")
        if rental_reason_id:
            reason_msg = "Closing Reason : " + rental_reason_id.description
        self.message_post(body=reason_msg)
        # self.message_post(reason_msg, subtype='mail.mt_comment',
        #                   message_type='comment')

    def post_msg_expired_reason(self):
        for rec in self:
            rental_reason_id = self.env.ref(
                'businesssuite_rental.rental_reason_demo_data_expired')
            reason_msg = _(
                "Rental product(s) has been received from that's why contract has been closed.")
            if rental_reason_id:
                reason_msg = "Expired : " + rental_reason_id.description
            rec.message_post(body=reason_msg)
            # rec.message_post(reason_msg, subtype='mail.mt_comment',
            #                   message_type='comment')

    def _action_launch_procurement_rule(self):
        """
        Launch procurement group run method in similar manner happening in sale_stock module.
        """
        precision = self.env['decimal.precision'].precision_get(
            'Product Unit of Measure')
        errors = []
        for contract in self:
            if not contract.rental_product_id.type in ('consu', 'product'):
                # Leave non-consumable and non-stockable products
                continue
            qty = 0.0
            for move in contract.stock_move_ids.filtered(lambda r: r.state != 'cancel'):
                qty += move.product_qty
            if float_compare(qty, contract.rental_qty, precision_digits=precision) >= 0:
                continue

            group_id = contract.sale_order_line_id.order_id.procurement_group_id
            if not group_id:
                group_id = self.env['procurement.group'].create({
                    'name': contract.sale_order_line_id.order_id.name,
                    'move_type': contract.sale_order_line_id.order_id.picking_policy,
                    'sale_id': contract.sale_order_line_id.order_id.id,
                    'partner_id': contract.sale_order_line_id.order_id.partner_shipping_id.id,
                })
                contract.sale_order_line_id.order_id.procurement_group_id = group_id
            else:
                updated_vals = {}
                if group_id.partner_id != contract.sale_order_line_id.order_id.partner_shipping_id:
                    updated_vals.update(
                        {'partner_id': contract.sale_order_line_id.order_id.partner_shipping_id.id})
                if group_id.move_type != contract.sale_order_line_id.order_id.picking_policy:
                    updated_vals.update(
                        {'move_type': contract.sale_order_line_id.order_id.picking_policy})
                if updated_vals:
                    group_id.write(updated_vals)

            values = contract.sale_order_line_id._prepare_procurement_values(
                group_id=group_id)
            values.update({'date_planned': fields.Datetime.now()})
            product_qty = contract.rental_qty - qty
            try:
                self.env['procurement.group'].run([self.env['procurement.group'].Procurement(contract.rental_product_id,
                                                                                             product_qty,
                                                                                             contract.sale_order_line_id.product_uom,
                                                                                             contract.sale_order_line_id.order_id.partner_shipping_id.property_stock_customer,
                                                                                             contract.sale_order_line_id.name,
                                                                                             contract.sale_order_line_id.order_id.name,
                                                                                             contract.sale_order_line_id.company_id,
                                                                                             values,
                                                                                             )])

            except UserError as error:
                errors.append(error.args[0])
        if errors:
            raise UserError('\n'.join(errors))
        return True

    def cancel_out_moves(self):
        for contract in self:
            contract.stock_move_ids.filtered(
                lambda r: r.picking_type_id.code == "outgoing" and r.state != "done")._action_cancel()

    def action_reverse_transfer(self):
        self.ensure_one()
        if self.stock_move_ids.filtered(
                lambda r: r.picking_type_id.code == "incoming"):
            raise UserError(_("Reverse delivery has been already created."))
        if self.id != self.sale_order_line_id.current_rental_contract_id.id:
            return self.sale_order_line_id.current_rental_contract_id.action_reverse_transfer()

        view_id = self.env.ref('stock.view_stock_return_picking_form').id
        context = self._context.copy()
        context["active_model"] = "stock.picking"
        context["active_id"] = self.stock_move_ids.filtered(
            lambda r: r.picking_type_id.code == "outgoing")[0].picking_id.id
        context["active_ids"] = [self.stock_move_ids.filtered(
            lambda r: r.picking_type_id.code == "outgoing")[0].picking_id.id]
        # context["params"]["id"] = self.id
        return {
            'name': 'Reverse Transfer',
            'view_mode': 'form',
            'views': [(view_id, 'form')],
            'res_model': 'stock.return.picking',
            'view_id': view_id,
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': context,
        }

    # Business methods

    def create_rental_invoice(self):
        """ Create contract sequence """
        InvoiceObj = self.env['account.move']
        for contract in self:
            if len(contract) == 1 and len(contract.rental_invoice_ids) != 0:
                raise UserError(
                    _('Invoice has been already created fro this contract. \
                    You can create additional invoice from linked sale order.'))
            contract.action_confirm()
            rental_invoice_vals = contract._prepare_rental_invoice()
            rental_invoice_vals['invoice_line_ids'].append(
                (0, 0, contract._prepare_rental_invoice_line(contract.rental_qty)))
            rental_invoice = self.env['account.move'].with_context(default_move_type='out_invoice').create(
                rental_invoice_vals)
            contract.update({
                'rental_invoice_ids': [(6, 0, [rental_invoice.id])],
            })
            # New code start from here: need to test in deeply
            security_refund_product_id = self.env['ir.default'].sudo().get(
                'res.config.settings', 'security_refund_product_id')
            if security_refund_product_id:
                security_refund_product_obj = self.env["product.product"].browse(
                    security_refund_product_id)
                inv_line_id = contract.sale_order_line_id.rental_contract_ids.mapped("invoice_line_ids").filtered(
                    lambda o: o.product_id == security_refund_product_obj and o.move_id.move_type == 'out_invoice')
                inv_line_id.rental_contract_id = contract.id
            # New code end here
            view_id = self.env.ref('account.view_move_form').id
            return {
                'name': 'Rental Invoice',
                'view_mode': 'form',
                'views': [(view_id, 'form')],
                'res_model': 'account.move',
                'view_id': view_id,
                'type': 'ir.actions.act_window',
                'res_id': rental_invoice.id,
            }

    def _prepare_rental_invoice(self):
        self.ensure_one()
        journal = self.env['account.move'].with_context(default_move_type='out_invoice')._get_default_journal()
        if not journal:
            raise UserError(_('Please define an accounting sales journal for the company %s (%s).') % (
                self.company_id.name, self.company_id.id))

        rental_invoice_vals = {
            'name': '/',
            'invoice_origin': self.name,
            'ref': self.sale_order_line_id.order_id.name,
            'move_type': 'out_invoice',
            'partner_shipping_id': self.sale_order_line_id.order_id.partner_shipping_id.id,
            'currency_id': self.sale_order_line_id.order_id.pricelist_id.currency_id.id,
            'invoice_payment_term_id': self.sale_order_line_id.order_id.partner_id.property_payment_term_id and self.sale_order_line_id.order_id.partner_id.property_payment_term_id.id,
            'fiscal_position_id': self.sale_order_line_id.order_id.partner_id.property_account_position_id and self.sale_order_line_id.order_id.partner_id.property_account_position_id.id,
            'partner_id': self.sale_order_line_id.order_id.partner_invoice_id.id,
            'journal_id': journal.id,
            'company_id': self.company_id.id,
            'invoice_user_id': self.sale_order_line_id.order_id.user_id and self.sale_order_line_id.order_id.user_id.id,
            'team_id': self.sale_order_line_id.order_id.team_id.id,
            'narration': self.rental_note,
            'invoice_line_ids': [],
        }
        return rental_invoice_vals

    def _prepare_rental_invoice_line(self, rental_qty):

        vals = {
            'sequence': self.sale_order_line_id.sequence,
            'price_unit': self.price_unit,
            'quantity': rental_qty,
            'discount': self.discount,
            'ref': self.sale_order_line_id.order_id.name,
            'product_uom_id': self.sale_order_line_id.product_uom.id,
            'product_id': self.rental_product_id.id or False,
            'tax_ids': [(6, 0, self.tax_ids.ids)],
            'analytic_account_id': self.sale_order_line_id.order_id.analytic_account_id.id,
            'analytic_tag_ids': [(6, 0, self.sale_order_line_id.analytic_tag_ids.ids)],
            'sale_line_ids': [(4, self.sale_order_line_id.id)],
        }
        return vals

    def calculate_end_time(self):
        self.ensure_one()
        end_datetime = False
        duration_unit = self.rental_uom_id.duration_unit
        rental_tenure = self.rental_tenure
        if duration_unit and rental_tenure:
            end_datetime = fields.Datetime.from_string(
                self.start_time) + relativedelta(**{duration_unit: int(rental_tenure)})
        return end_datetime

    @api.model
    def cron_method_to_make_expired_contract(self):
        x = self.search([('state', 'in', ['ready', 'in_progress'])])
        for contract in x:
            if contract.end_time and fields.Datetime.from_string(contract.end_time) < datetime.now():
                contract.state = "expired"
                if contract.rental_delivery_status == "all_received":
                    contract.closed_rental_contract()
                contract.cancel_out_moves()
                contract.post_msg_expired_reason()
                contract.sale_order_line_id.rental_state = "expired"

    def create_out_delivery(self):
        for contract in self:
            if contract.state == "ready":
                if not contract.stock_move_ids.filtered(
                        lambda r: r.picking_type_id.code == "outgoing"):
                    contract.with_context(
                        contract_id=contract.id)._action_launch_procurement_rule()
                    ctx = dict(self.env.context)
                    out_move = contract.stock_move_ids.filtered(lambda r: r.picking_type_id.code == "outgoing")
                    if out_move:
                        ctx.update({
                            'search_default_picking_type_id': out_move[0].picking_type_id.id,
                            'search_default_draft': False,
                            'search_default_assigned': False,
                            'search_default_confirmed': False,
                            'search_default_ready': False,
                            'search_default_late': False,
                            'search_default_available': False,
                        })
                        return {
                            'name': _('Delivery Picking'),
                            'view_mode': 'form,tree,calendar',
                            'res_model': 'stock.picking',
                            'res_id': out_move[0].picking_id.id,
                            'type': 'ir.actions.act_window',
                            'context': ctx,
                        }
                else:
                    raise UserError(_("Delivery Order has been already created for this contract."))
            else:
                raise UserError(
                    _("Can't create delivery order. Contract is not in ready state."))

    def check_product_received(self):
        self.ensure_one()
        rental_in_stock_moves = self.stock_move_ids.filtered(
            lambda r: r.picking_type_id.code == "incoming")
        if rental_in_stock_moves and len(rental_in_stock_moves) == len(
                rental_in_stock_moves.filtered(lambda r: r.state == "done")):
            return True
        return False

    def link_move_to_new_contract(self, from_contract, to_contract):
        if not from_contract or not to_contract:
            return False
        stock_moves = from_contract.stock_move_ids.filtered(
            lambda r: r.picking_type_id.code == "outgoing" and r.state == "done").sorted(key="id")
        if stock_moves:
            to_contract.update({
                "stock_move_ids": [(6, 0, [stock_moves[0].id])]
            })


class RentalReasons(models.Model):
    # Private attributes
    _name = 'rental.reason'
    _description = "Rental Reason"

    # Fields declaration
    name = fields.Char("Name", required=True)
    description = fields.Text("Description")
    sequence = fields.Integer("Sequence")
