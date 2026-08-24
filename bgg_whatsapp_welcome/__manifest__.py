# -*- coding: utf-8 -*-
{
    'name': 'BelGoGreen WhatsApp Welcome Message',
    'version': '19.0.1.0.0',
    'category': 'Customizations',
    'summary': 'Send the welcome call as a WhatsApp message when the welcome-call task is created',
    'description': """
        BelGoGreen WhatsApp Welcome Message
        ===================================

        Bridge module between the BelGoGreen welcome-call workflow and the Odoo
        **WhatsApp** app (Enterprise).

        When the "Welcom call" project task is created (typically from the
        project template when a sale order is confirmed), this module
        automatically queues a pre-approved WhatsApp template message to the
        customer, so the client receives a welcome message on WhatsApp in
        addition to the phone welcome call.

        Features:

        - Automatic sending on welcome-call task creation (once per task)
        - Manual "Send WhatsApp Welcome" button on the task for retries
        - Template, task name and on/off switch configurable through system
          parameters:

          - ``bgg_whatsapp_welcome.enabled`` (default: True)
          - ``bgg_whatsapp_welcome.template_name`` (default: belgogreen_welcome_call)
          - ``bgg_whatsapp_welcome.task_name`` (default: Welcom call)

        Prerequisites: the WhatsApp Business account must be connected in the
        Odoo WhatsApp app and the welcome template approved by Meta. See the
        module README and ``docs/Guide_Client_WhatsApp_Meta.md`` for the full
        setup path.
    """,
    'author': 'BelGoGreen',
    'website': 'https://www.belgogreen.com',
    'license': 'LGPL-3',
    'depends': [
        'project',
        'sale_project',
        'whatsapp',
    ],
    'data': [
        'views/project_task_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
