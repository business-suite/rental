{
    "name": "Business Suite Rental",
    "version": "15.0.0",
    "author": "Business Suite Team",
    "category": "Sales",
    "summary": "Odoo Rental Sale Management allows you to make a product available for rent and offer the same to the people.",
    "description": """
        Odoo Rental Sale Management
        Rental Sale Management
        Rent
        Odoo Rental Sale Management in Odoo
        Rental Products
        Rent Products
        Rental Management
        Odoo Website Rental Sale
        Odoo Marketplace Rental Sale
        Rent Product Tenure
        Hire Products
        Hiring Management
    """,
    "depends": [
        "sale_stock",
        "sale_management",
    ],
    "data": [
        "security/rental_sale_security.xml",
        "security/ir.model.access.csv",
        "data/uom_uom_rental_data.xml",
        "data/rental_reason_data.xml",
        "data/product_demo.xml",
        "data/rental_cron.xml",
        "data/ir_sequence_data.xml",
        "wizard/rental_order_transient_view.xml",
        "wizard/renew_rental_order_transient_view.xml",
        "wizard/rental_reason_transient_view.xml",
        "views/rental_product_view.xml",
        "views/rental_view.xml",
        "views/rental_order_view.xml",
        "views/rental_menu_view.xml",
        "views/inherited_sale_order_views.xml",
        "views/inherit_picking_view.xml",
        "views/res_config_settings_views.xml",
        "views/rental_contract_report_template.xml",
    ],
    "demo": [],
    "application": True,
    "installable": True,
    "auto_install": False,
    "pre_init_hook": "pre_init_check",
    "assets": {
        "web.assets_frontend": [
            "businesssuite_rental/static/src/**/*",
        ],
    }
}
