{
    'name': 'LLM Reports',
    'version': '1.0',
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
        'views/dynamic_query_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}