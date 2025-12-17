# -*- coding: utf-8 -*-
{
    'name': "Belgogreen Sales Commission",

    'summary': "Hierarchical commission system for sales with multi-level calculation",

    'description': """
Belgogreen Sales Commission Module
===================================

This module provides a comprehensive hierarchical commission system that:

* Automatically calculates commissions for salesperson, team leader, and sales director
* Tracks commission payments and allows users to claim their commissions
* Provides dedicated views for salespeople to see their commissions (wallet)
* Includes admin tools for managing and processing commission payments
* Supports manual adjustments and flexible configuration
* Hierarchical visibility: supervisors can view all subordinate commissions recursively

Main Features:
--------------
* Multi-level commission calculation (3 hierarchy levels)
* Automatic commission creation when invoices are paid
* Commission claims and approval workflow
* Payment tracking and history
* Role-based commission percentages
* Hierarchical commission visibility (supervisors see all sub-level commissions)
* Team commission dashboard and statistics
* Integration with Odoo's existing commission and sales modules
    """,

    'author': "Belgogreen",
    'website': "https://www.belgogreen.com",

    'category': 'Sales/Sales',
    'version': '19.0.0.0',
    'license': 'LGPL-3',

    # Dependencies - require Odoo sale_commission module
    'depends': [
        'base',
        'sale_management',
        'purchase',
        'account',
        'hr',
        'mail',
        'sale_commission',  # Odoo's commission module
    ],

    # always loaded
    'data': [
        'security/commission_security.xml',
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'data/product_data.xml',
        'data/sale_commission_role_data.xml',
        'data/cron_data.xml',
        'wizard/commission_claim_wizard_views.xml',
        'views/sale_commission_role_views.xml',
        'views/hr_commission_role_config_views.xml',
        'views/sale_commission_plan_views.xml',
        'views/res_users_views.xml',
        # 'views/team_management_views.xml',  # Disabled - incompatible with plan-based architecture
        'views/commission_deduction_views.xml',
        'views/sale_order_views.xml',
        'views/sale_commission_payment_views.xml',  # Must load BEFORE sale_commission_views
        'views/sale_commission_claim_views.xml',
        'views/sale_commission_views.xml',
        'views/account_move_views.xml',
        'views/commission_dashboard_views.xml',
        'views/menu_views.xml',  # Load menu structure LAST - after all actions are defined
    ],
    'assets': {
        'web.assets_backend': [
            'belgogreen_sales_commission/static/src/js/commission_dashboard.js',
            'belgogreen_sales_commission/static/src/xml/commission_dashboard.xml',
            'belgogreen_sales_commission/static/src/scss/commission_dashboard.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}

