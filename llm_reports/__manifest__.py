{
    'name': 'Natural Query',
    'version': '18.0.1.0.3',
    'summary': 'Multilingual AI-Powered Natural Language Reports',
    'description': """
        Transform data access across language barriers with AI-powered natural language queries.
        
        Key Features:
        - Query in 95+ languages including Arabic, Spanish, French, German, Chinese
        - Get instant reports and filtered views in your language
        - AI understands context across languages
        - Save frequently used queries as filters
        - Seamless integration with Odoo views
        
        Perfect for:
        - International teams
        - Multilingual organizations
        - Global businesses
        - Non-technical users

        [Note]: This module uses AI to interpret natural language search queries. Search queries are processed externally to convert them into Odoo filters. No database content or sensitive data is transmitted - only the search query text.

    """,
    'author': 'BS Improvement Consulting',
    'website': 'https://www.bsimprovement.com/',
    'support': 'mohammed.ibenayad@gmail.com',
    'license': 'OPL-1',
    'price': 189.99,
    'currency': 'EUR',
    'category': 'Reporting',
    'depends': ['base', 'web', 'base_setup'],
    'data': [
        'security/ir.model.access.csv',
        'views/feedback_views.xml',
        'views/dynamic_query_views.xml',
        'data/system_param_data.xml',
        'data/demo_user_data.xml'
    ],
    'assets': {
        'web.assets_backend': [
            'llm_reports/static/src/js/form_controller.js',
        ],
    },
    'images': [
        'static/description/main_screenshot.gif',
        'static/description/main_1.png',
        'static/description/main_2.png'
    ],
    'installable': True,
    'application': True,
    'live_test_url': 'https://query.odoo.com',
}