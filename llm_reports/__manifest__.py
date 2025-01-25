{
    'name': 'LLM Reports',
    'version': '1.0.1',
    'summary': 'Generate dynamic reports using natural language queries',
    'description': """
        This module allows users to input natural language queries, which are sent to an LLM to generate Odoo-compatible queries.
        The results are displayed in Odoo's standard views.
    """,
    'author': 'Mohammed Iben Ayad',
    'website': 'https://ibenayad.link/',
    'category': 'Reporting',
    'depends': ['base', 'web', 'base_setup'],
    'data': [
        'security/ir.model.access.csv',
        'views/feedback_views.xml',
        'views/dynamic_query_views.xml',
        'data/demo_user_data.xml'
    ],
    'assets': {
        'web.assets_backend': [
            'llm_reports/static/js/form_controller.js',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}