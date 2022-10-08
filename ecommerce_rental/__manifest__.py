{
    "name": "Business Suite eCommerce Rental",
    "version": "15.0.0",
    "author": "Business Suite Team",
    "category": "eCommerce",
    "summary": "Set up rental products on your Odoo website. The module provides an easy way to manage and rent out products to customer in Odoo.",
    "description": """
        Create rental products in Odoo
        Publish rental products
        Manage rental product in Odoo
        Renting business
        Manage rent on items
        Rent items
        Rent products
        Odoo Website Rental Sale
        Rental Sale in Odoo Website
        Odoo Lease Management
        Odoo Website Lease Sale
        Odoo Rental Sale
        Odoo Website Rental Management
        Rental Management in Odoo Website
        Odoo Odoo Website Rental Sale
        Rental service in Odoo
        Manage rental products in Odoo
    """,
    "depends": [
        "account_payment",
        "website_sale",
        "businesssuite_rental",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/rental_product_view.xml",
        "views/inherit_website_template.xml",
        "views/inherit_website_cart_template.xml",
        "views/my_account_rental_contract_template.xml",
        "data/rental_data.xml",
    ],
    "demo": [],
    "application": True,
    "installable": True,
    "auto_install": False,
    "pre_init_hook": "pre_init_check",
    "assets": {
        "web.assets_frontend": [
            "businesssuite_ecommerce_rental/static/src/**/*",
        ],
    }
}
