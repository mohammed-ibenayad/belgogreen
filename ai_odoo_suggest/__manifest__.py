{
    'name': 'AI Odoo Suggest',
    'version': '18.0.1.0.0',
    'category': 'Discuss',
    'summary': 'AI-powered audio transcription and action suggestions',
    'description': """
        This module intercepts audio messages in discuss, transcribes them using AI,
        and suggests actions to create, update, or delete records in Odoo.
    """,
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/ai_suggest_views.xml',
        'views/mail_message_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ai_odoo_suggest/static/src/js/ai_suggest.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
    'external_dependencies': {
        'python': [
            'openai',
        ],
        #'bin': [
        #'ffmpeg',  # System binary dependency
        #],
    },
}