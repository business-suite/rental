import json
import logging
from datetime import datetime

from werkzeug.exceptions import NotFound

from odoo import fields, http
from odoo.addons.http_routing.models.ir_http import slug
from odoo.addons.website_sale.controllers.main import QueryURL, TableCompute, WebsiteSale
from odoo.http import request
from odoo.tools.json import scriptsafe as json_scriptsafe
from odoo.tools.misc import flatten

_logger = logging.getLogger(__name__)

# noinspection PyBroadException
try:
    # noinspection PyUnresolvedReferences
    import urlparse
    # noinspection PyUnresolvedReferences
    from urllib import urlencode
except:  # For Python 3
    # noinspection PyUnresolvedReferences
    import urllib.parse as urlparse
    # noinspection PyUnresolvedReferences
    from urllib.parse import urlencode


class WebsiteRentalSale(http.Controller):

    @http.route(["/set/tenure/maxvalue"], type="json", auth="public", website=True)
    def _set_tenure_maxvalue(self, product_id, tenure_uom_id):
        product_id = request.env['product.product'].sudo().browse(product_id)
        max_tenure_value = product_id.get_tenure_maxvalue(int(tenure_uom_id))
        return {"max_value": max_tenure_value, }

    @http.route(["/get/tenure/price"], type="json", auth="public", website=True)
    def _get_tenure_price(self, product_id, tenure_uom_id=None, tenure_value=None, tenure_id=None):
        if tenure_id:
            rent_price = request.env['product.rental.tenure'].browse(int(tenure_id)).rent_price
            rent_price = request.env["website"].get_website_price(
                request.env['product.product'].sudo().browse(product_id), rent_price)
            return str('%.2f' % rent_price)
        tenure_uom_id = request.env['uom.uom'].sudo().browse(tenure_uom_id).id or False
        product_id = request.env['product.product'].sudo().browse(product_id)
        max_tenure_value = product_id.get_tenure_maxvalue(int(tenure_uom_id))
        if float(tenure_value) > max_tenure_value:
            return {"error": "true",
                    "max_value": request.env["website"].get_website_price(product_id, max_tenure_value), }

        if tenure_uom_id and tenure_value and product_id:
            tenure_price = product_id.get_product_tenure_price(float(tenure_value), tenure_uom_id)
            return {"error": "false", "tenure_price": str(
                '%.2f' % round(request.env["website"].get_website_price(product_id, tenure_price[1]),
                               2)), } if tenure_price else {}

    @http.route(['/rental/order/renew'], type='http', auth='public', website=True, )
    def renew_rental_order(self, **kw):
        url = request.httprequest.referrer
        params = {}
        try:
            product_id = request.env['product.product'].browse(int(kw.get('product_id')))
            rental_order = kw.get('is_rental_product', None) and product_id.rental_ok
            sale_order_line_id = request.env['sale.order.line'].browse(int(kw.get("sale_order_line_id")))
            if rental_order:
                tenure_uom = False
                tenure_value = 0
                tenure_price = 0
                if kw.get('standard') and kw.get('tenure_id'):
                    tenure_id = request.env['product.rental.tenure'].browse(
                        int(kw.get('tenure_id')) if kw.get('tenure_id') else False)
                    tenure_uom = tenure_id.rental_uom_id.id if tenure_id else False
                    tenure_value = float(tenure_id.tenure_value) if tenure_id else 0
                    tenure_price = float(tenure_id.rent_price) if tenure_id else 0

                if kw.get('custom') and kw.get('custom_tenure_price'):
                    tenure_uom = request.env['uom.uom'].sudo().browse(kw.get('tenure_uom')).id or False
                    tenure_value = float(kw.get('tenure_value')) or 0
                    tenure_price = float(product_id.get_product_tenure_price(tenure_value, tenure_uom) or kw.get(
                        'custom_tenure_price') or 0)

                    return_value_price_pair = product_id.get_product_tenure_price(tenure_value, tenure_uom)
                    if return_value_price_pair:
                        tenure_value = return_value_price_pair[0]
                        tenure_price = return_value_price_pair[1]
                taxes_ids = []

                if product_id.sudo().taxes_id:
                    taxes_ids = product_id.taxes_id.ids
                ro_contract_values = {
                    'sale_order_line_id': sale_order_line_id.id,
                    'product_rental_agreement_id': product_id.rental_agreement_id.id,
                    'price_unit': sale_order_line_id.product_id.currency_id.compute(tenure_price,
                                                                                    sale_order_line_id.order_id.pricelist_id.currency_id),
                    'rental_qty': sale_order_line_id.product_uom_qty,
                    'rental_uom_id': tenure_uom,
                    'rental_tenure': tenure_value,
                    'tax_ids': [(6, 0, taxes_ids)],
                    'is_renewal_contract': True,
                }

                new_created_rental_contract = request.env['rental.order.contract'].sudo().create(ro_contract_values)
                new_created_rental_contract.action_confirm()
                new_created_rental_contract = new_created_rental_contract.sudo()
                inv = new_created_rental_contract.create_rental_invoice()
                inv_id = inv.get("res_id") or False
                if inv_id:
                    inv_obj = request.env['account.move'].browse(int(inv_id))
                    inv_obj.sudo().action_post()
                    params = {'renew_success': inv_obj.id}

                if new_created_rental_contract and len(sale_order_line_id.rental_contract_ids) == 1:
                    sale_order_line_id.sudo().inital_rental_contract_id = new_created_rental_contract.id

                else:

                    contract_to_check = False
                    if sale_order_line_id.sudo().current_rental_contract_id:
                        contract_to_check = sale_order_line_id.sudo().current_rental_contract_id
                    else:
                        contract_to_check = sale_order_line_id.sudo().inital_rental_contract_id
                    if contract_to_check and not (contract_to_check.check_product_received()):
                        # code to link current contract done move to latest contrcat
                        new_created_rental_contract.link_move_to_new_contract(
                            contract_to_check, new_created_rental_contract)
                        new_created_rental_contract.start_time = fields.datetime.now()
                        sale_order_line_id.sudo().current_start_time = new_created_rental_contract.start_time

                    sale_order_line_id.sudo().write({
                        "current_rental_contract_id": new_created_rental_contract.id,
                        "last_renewal_time": datetime.now(),
                    })

                    new_created_rental_contract.sale_order_line_id.sudo().write(
                        {"rental_state": "in_progress"})


        except Exception as e:

            params = {'renew_error': 1}
            pass
        url_parts = list(urlparse.urlparse(url))
        query = dict(urlparse.parse_qsl(url_parts[4]))
        if query.get("renew_success") or query.get("renew_error"):
            pass
        else:
            query.update(params)
        url_parts[4] = urlencode(query)
        url = urlparse.urlunparse(url_parts)
        return request.redirect(url)


class WebsiteSale(WebsiteSale):

    def _get_rental_search_domain(self, search, rental_categ, category, attrib_values):
        domain = []
        if search:
            for srch in search.split(" "):
                domain += [
                    '|', '|', '|', ('name', 'ilike', srch), ('description', 'ilike', srch),
                    ('description_sale', 'ilike', srch), ('product_variant_ids.default_code', 'ilike', srch)]
        domain += [('rental_ok', '=', True)]

        if category:
            domain += [('public_categ_ids', 'child_of', int(category))]

        if rental_categ:
            domain += [('rental_categ_id', '=', int(rental_categ))]

        if attrib_values:
            attrib = None
            ids = []
            for value in attrib_values:
                if not attrib:
                    attrib = value[0]
                    ids.append(value[1])
                elif value[0] == attrib:
                    ids.append(value[1])
                else:
                    domain += [('attribute_line_ids.value_ids', 'in', ids)]
                    attrib = value[0]
                    ids = [value[1]]
            if attrib:
                domain += [('attribute_line_ids.value_ids', 'in', ids)]

        return domain

    def get_parent_categs(self, categ, categ_list=None):
        if categ_list is None:
            categ_list = []
        if categ.parent_id:
            categ_list.append(categ.parent_id.id)
            self.get_parent_categs(categ=categ.parent_id, categ_list=categ_list)
        return request.env["product.public.category"].browse(categ_list)

    @http.route([
        '/shop/rental',
        '/shop/rental/page/<int:page>',
        '/shop/rental/category/<model("product.public.category"):category>',
        '/shop/rental/category/<model("product.public.category"):category>/page/<int:page>'
    ], type='http', auth="public", website=True)
    def shop_rental(self, rental_categ=0, page=0, category=None, search='', ppg=False, **post):
        add_qty = int(post.get('add_qty', 1))
        Category = request.env['product.public.category']
        if category:
            category = Category.search([('id', '=', int(category))], limit=1)
            if not category or not category.can_access_from_current_website():
                raise NotFound()
        else:
            category = Category

        if ppg:
            try:
                ppg = int(ppg)
                post['ppg'] = ppg
            except ValueError:
                ppg = False
        if not ppg:
            ppg = request.env['website'].get_current_website().shop_ppg or 20

        ppr = request.env['website'].get_current_website().shop_ppr or 4

        attrib_list = request.httprequest.args.getlist('attrib')
        attrib_values = [[int(x) for x in v.split("-")] for v in attrib_list if v]
        attributes_ids = {v[0] for v in attrib_values}
        attrib_set = {v[1] for v in attrib_values}

        domain = self._get_rental_search_domain(search, rental_categ, category, attrib_values)

        keep = QueryURL('/shop/rental', rental_categ=rental_categ, category=category and int(category), search=search,
                        attrib=attrib_list, order=post.get('order'))

        pricelist_context, pricelist = self._get_pricelist_context()

        request.context = dict(request.context, pricelist=pricelist.id, partner=request.env.user.partner_id)

        url = "/shop/rental"
        if search:
            post["search"] = search
        if category:
            category = request.env['product.public.category'].browse(int(category))
            url = "/shop/rental/category/%s" % slug(category)
        if rental_categ:
            rental_categ = request.env['rental.product.category'].browse(int(rental_categ))
            post["rental_categ"] = rental_categ
        if attrib_list:
            post['attrib'] = attrib_list

        categs = request.env['product.public.category'].search([('parent_id', '=', False)])
        rental_categs = request.env['rental.product.category'].search([('hide_all_product', '=', False)])

        Product = request.env['product.template'].with_context(bin_size=True)

        search_product = Product.search(domain)
        website_domain = request.website.website_domain()
        categs_domain = [('parent_id', '=', False)] + website_domain
        if search:
            search_categories = Category.search(
                [('product_tmpl_ids', 'in', search_product.ids)] + website_domain).parents_and_self
            # noinspection PyTypeChecker
            categs_domain.append(('id', 'in', search_categories.ids))
        else:
            search_categories = Category
        categs = Category.search(categs_domain)

        parent_category_ids = []
        if category:
            url = "/shop/category/%s" % slug(category)

        product_count = len(search_product)
        pager = request.website.pager(url=url, total=product_count, page=page, step=ppg, scope=7, url_args=post)
        products = Product.search(domain, limit=ppg, offset=pager['offset'], order=self._get_search_order(post))

        ProductAttribute = request.env['product.attribute']
        if products:
            # get all products without limit
            selected_products = Product.search(domain, limit=False)
            attributes = ProductAttribute.search([('attribute_line_ids.product_tmpl_id', 'in', selected_products.ids)])
        else:
            attributes = ProductAttribute.browse(attributes_ids)

        # to apply domain in category of rental shop according to product categories added in rental category
        if rental_categ:
            categ_domain = []
            for c in rental_categ.public_categ_ids:
                categ_domain.append(self.get_parent_categs(c, []).ids)
            categ_domain.append(rental_categ.public_categ_ids.ids)
            categ_domain = flatten(categ_domain)
        else:
            categ_domain = False

        layout_mode = request.session.get('website_sale_shop_layout_mode')
        if not layout_mode:
            if request.website.viewref('website_sale.products_list_view').active:
                layout_mode = 'list'
            else:
                layout_mode = 'grid'

        values = {
            'search': search,
            'category': category,
            'rental_categ': rental_categ,
            'categ_domain': categ_domain if rental_categ else False,
            'attrib_values': attrib_values,
            'attrib_set': attrib_set,
            'pager': pager,
            'pricelist': pricelist,
            'add_qty': add_qty,
            'products': products,
            'search_count': product_count,  # common for all searchbox
            'bins': TableCompute().process(products, ppg, ppr),
            'ppg': ppg,
            'ppr': ppr,
            'categories': categs,
            'attributes': attributes,
            'keep': keep,
            'search_categories_ids': search_categories.ids,
            'layout_mode': layout_mode,
            'rental_categs': rental_categs,
            'parent_category_ids': parent_category_ids,
            'is_rental_page': True,
        }
        if category:
            values['main_object'] = category
        return request.render("website_sale.products", values)

    @http.route(['/shop/rental/product/<model("product.template"):product>'], type='http', auth="public", website=True)
    def product_rental(self, product, rental_categ=0, category='', search='', **kwargs):
        if not product.can_access_from_current_website():
            raise NotFound()

        # noinspection PyTypeChecker
        return request.render("website_sale.product",
                              self._prepare_rental_product_values(product, rental_categ, category, search, **kwargs))

    def _prepare_rental_product_values(self, product, rental_categ, category, search, **kwargs):
        add_qty = int(kwargs.get('add_qty', 1))

        product_context = dict(request.env.context, quantity=add_qty,
                               active_id=product.id,
                               partner=request.env.user.partner_id)
        ProductCategory = request.env['product.public.category']
        RentalCategory = request.env['rental.product.category']

        if category:
            category = ProductCategory.browse(int(category)).exists()

        if rental_categ:
            rental_categ = RentalCategory.browse(int(rental_categ))

        attrib_list = request.httprequest.args.getlist('attrib')
        attrib_values = [[int(x) for x in v.split("-")] for v in attrib_list if v]
        attrib_set = {v[1] for v in attrib_values}

        keep = QueryURL('/shop', rental_categ=rental_categ, category=category and category.id, search=search,
                        attrib=attrib_list)

        categs = ProductCategory.search([('parent_id', '=', False)])

        pricelist = request.website.get_current_pricelist()

        if not product_context.get('pricelist'):
            product_context['pricelist'] = pricelist.id
            product = product.with_context(product_context)

        # Needed to trigger the recently viewed product rpc
        view_track = request.website.viewref("website_sale.product").track
        return {
            'search': search,
            'category': category,
            'rental_categ': rental_categ,
            'pricelist': pricelist,
            'attrib_values': attrib_values,
            'attrib_set': attrib_set,
            'keep': keep,
            'categories': categs,
            'main_object': product,
            'product': product,
            'add_qty': add_qty,
            'view_track': view_track,
            'is_rental_product': True,
        }

    @http.route()
    def cart_update(self, product_id, add_qty=1, set_qty=0, **kw):

        product_id = request.env['product.product'].browse(int(product_id))
        rental_order = kw.get('is_rental_product', None) and product_id.rental_ok
        if rental_order:
            try:
                tenure_uom = False
                tenure_value = 0
                tenure_price = 0
                if not kw.get('standard') and not kw.get('custom'):
                    return request.redirect("/shop/cart")
                if kw.get('standard') and kw.get('tenure_id'):
                    tenure_id = request.env['product.rental.tenure'].browse(
                        int(kw.get('tenure_id')) if kw.get('tenure_id') else False)
                    tenure_uom = tenure_id.rental_uom_id.id if tenure_id else False
                    tenure_value = float(tenure_id.tenure_value) if tenure_id else 0
                    tenure_price = float(tenure_id.rent_price) if tenure_id else 0
                    tenure_price = request.env["website"].get_website_price(product_id, tenure_price)

                if kw.get('custom') and kw.get('custom_tenure_price'):
                    tenure_uom = request.env['uom.uom'].sudo().browse(kw.get('tenure_uom')).id or False
                    tenure_value = float(kw.get('tenure_value')) or 0
                    tenure_price = float(product_id.get_product_tenure_price(tenure_value, tenure_uom) or kw.get(
                        'custom_tenure_price') or 0)
                    return_value_price_pair = product_id.get_product_tenure_price(tenure_value, tenure_uom)
                    if return_value_price_pair:
                        tenure_value = return_value_price_pair[0]
                        tenure_price = return_value_price_pair[1]
                so = request.website.sale_get_order(force_create=1)
                if so.state != 'draft':
                    request.session['sale_order_id'] = None
                    so = request.website.sale_get_order(force_create=True)
                rental_vals = {
                    'tenure_uom': tenure_uom,
                    'tenure_value': tenure_value,
                    'tenure_price': tenure_price,
                }
                product_custom_attribute_values = None
                if kw.get('product_custom_attribute_values'):
                    product_custom_attribute_values = json.loads(kw.get('product_custom_attribute_values'))
                no_variant_attribute_values = None
                if kw.get('no_variant_attribute_values'):
                    no_variant_attribute_values = json.loads(kw.get('no_variant_attribute_values'))
                line = so.with_context(rental_vals=rental_vals)._cart_update(
                    product_id=int(product_id),
                    add_qty=float(add_qty),
                    set_qty=float(set_qty),
                    product_custom_attribute_values=product_custom_attribute_values,
                    no_variant_attribute_values=no_variant_attribute_values,
                    rental_order=True,
                    tenure_uom=tenure_uom,
                    tenure_value=tenure_value,
                )
                return request.redirect("/shop/cart")
            except:
                return request.redirect("/shop/cart")
        res = super(WebsiteSale, self).cart_update(product_id, add_qty, set_qty, **kw)
        return res

    @http.route(['/shop/cart/update_json'], type='json', auth="public", methods=['POST'], website=True, csrf=False)
    def cart_update_json(self, product_id, line_id=None, add_qty=None, set_qty=None, display=True, **kw):
        """
        This route is called :
            - When changing quantity from the cart.
            - When adding a product from the wishlist.
            - When adding a product to cart on the same page (without redirection).
        """

        product_id = request.env['product.product'].browse(int(product_id))

        rental_order = kw.get('is_rental_product', None) and product_id.rental_ok
        if rental_order:
            try:
                tenure_uom = False
                tenure_value = 0
                tenure_price = 0
                if not kw.get('standard') and not kw.get('custom'):
                    return request.redirect("/shop/cart")
                if kw.get('standard') and kw.get('tenure_id'):
                    tenure_id = request.env['product.rental.tenure'].browse(
                        int(kw.get('tenure_id')) if kw.get('tenure_id') else False)
                    tenure_uom = tenure_id.rental_uom_id.id if tenure_id else False
                    tenure_value = float(tenure_id.tenure_value) if tenure_id else 0
                    tenure_price = float(tenure_id.rent_price) if tenure_id else 0
                    tenure_price = request.env["website"].get_website_price(product_id, tenure_price)

                if kw.get('custom') and kw.get('custom_tenure_price'):
                    tenure_uom = request.env['uom.uom'].sudo().browse(kw.get('tenure_uom')).id or False
                    tenure_value = float(kw.get('tenure_value')) or 0
                    tenure_price = float(product_id.get_product_tenure_price(tenure_value, tenure_uom) or kw.get(
                        'custom_tenure_price') or 0)
                    return_value_price_pair = product_id.get_product_tenure_price(tenure_value, tenure_uom)
                    if return_value_price_pair:
                        tenure_value = return_value_price_pair[0]
                        tenure_price = return_value_price_pair[1]
                so = request.website.sale_get_order(force_create=1)
                if so.state != 'draft':
                    request.session['sale_order_id'] = None
                    so = request.website.sale_get_order(force_create=True)

                order = request.website.sale_get_order(force_create=1)
                if order.state != 'draft':
                    request.website.sale_reset()
                    if kw.get('force_create'):
                        order = request.website.sale_get_order(force_create=1)
                    else:
                        return {}

                rental_vals = {
                    'tenure_uom': tenure_uom,
                    'tenure_value': tenure_value,
                    'tenure_price': tenure_price,
                }
                pcav = kw.get('product_custom_attribute_values')
                nvav = kw.get('no_variant_attribute_values')

                value = order.with_context(rental_vals=rental_vals)._cart_update(
                    product_id=product_id.id,
                    line_id=line_id,
                    add_qty=add_qty,
                    set_qty=set_qty,
                    product_custom_attribute_values=json_scriptsafe.loads(pcav) if pcav else None,
                    no_variant_attribute_values=json_scriptsafe.loads(nvav) if nvav else None,
                    rental_order=True,
                    tenure_uom=tenure_uom,
                    tenure_value=tenure_value,
                )

                if not order.cart_quantity:
                    request.website.sale_reset()
                    return value

                order = request.website.sale_get_order()
                value['cart_quantity'] = order.cart_quantity

                if not display:
                    return value

                value['website_sale.cart_lines'] = request.env['ir.ui.view']._render_template("website_sale.cart_lines",
                                                                                              {
                                                                                                  'website_sale_order': order,
                                                                                                  'date': fields.Date.today(),
                                                                                                  'suggested_products': order._cart_accessories()
                                                                                              })
                value['website_sale.short_cart_summary'] = request.env['ir.ui.view']._render_template(
                    "website_sale.short_cart_summary", {
                        'website_sale_order': order,
                    })

                return value
            except:
                return super(WebsiteSale, self).cart_update_json(product_id.id, line_id, add_qty, set_qty, display,
                                                                 **kw)
        else:
            res = super(WebsiteSale, self).cart_update_json(product_id.id, line_id, add_qty, set_qty, display, **kw)
            return res
