# -*- coding: utf-8 -*-
{
    'name': 'PV Simulation & Quotation Report',
    'version': '19.0.1.0.3',
    'category': 'Sales',
    'summary': 'Photovoltaic installation simulation with energy and financial calculations',
    'description': """
        PV Simulation Module
        ====================
        * Simulate photovoltaic installations
        * Calculate energy production, consumption, and storage
        * Compute monthly and annual financial impacts
        * Generate detailed PDF reports with charts
        * Integrate with sale quotations
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': ['base', 'sale_management'],
    'external_dependencies': {
        'python': [
            'matplotlib',
            'requests',
        ],
    },
    'data': [
        # Security
        'security/pv_simulation_security.xml',
        'security/ir.model.access.csv',

        # Data
        'data/solar_api_config.xml',
        'data/pv_production_profile_data.xml',
        'data/pv_battery_config_data.xml',
        'data/pv_tariff_profile_data.xml',

        # Wizard
        'wizard/pv_simulation_wizard_views.xml',

        # Views
        'views/res_company_views.xml',
        'views/product_template_views.xml',
        'views/pv_production_profile_views.xml',
        'views/pv_battery_config_views.xml',
        'views/pv_tariff_profile_views.xml',
        'views/pv_monthly_result_views.xml',
        'views/pv_simulation_views.xml',
        'views/sale_order_views.xml',
        'views/menu_views.xml',

        # Reports
        'report/pv_simulation_report.xml',
        'report/pv_simulation_template.xml',
    ],
    'demo': [
        'demo/pv_simulation_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'bgg_pv_simulation/static/src/css/pv_simulation.css',
            'bgg_pv_simulation/static/src/js/pv_simulation_regenerate.js',
            'bgg_pv_simulation/static/src/js/battery_icon_widget.js',
            'bgg_pv_simulation/static/src/xml/pv_simulation_templates.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
