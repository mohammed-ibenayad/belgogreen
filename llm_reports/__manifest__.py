{
    'name': 'LLM Reports',  # Name of the module
    'version': '1.0',  # Version of the module
    'summary': 'Generate dynamic reports using natural language queries',
    'description': """
        This module allows users to input natural language queries, which are sent to an LLM to generate Odoo-compatible queries.
        The results are displayed in Odoo's standard views.
    """,
    'author': 'Your Name',  # Your name or company name
    'website': 'https://yourwebsite.com',  # Your website URL
    'category': 'Uncategorized',  # Category of the module (e.g., Tools, Sales, Accounting)
    'depends': ['base', 'web'],  # Dependencies: base and web are required
    'data': [
        # XML files to load
        'views/dynamic_query_views.xml',  # Contains the form view and action
    ],
    'assets': {
        'web.assets_backend': [
            # JavaScript files to load in the backend
            'llm_reports/static/src/js/dynamic_query_popup.js',
        ],
    },
    'installable': True,  # Whether the module can be installed
    'application': True,  # This is an application, not just a module
    'license': 'LGPL-3',  # License type (LGPL-3 is standard for Odoo modules)
}