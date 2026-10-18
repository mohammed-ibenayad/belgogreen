# -*- coding: utf-8 -*-
{
    'name': 'BelGoGreen Custom Development - Enterprise bridge',
    'version': '19.0.1.2.0',
    'category': 'Customizations',
    'summary': 'Keeps bgg_custom_dev in sync with the Enterprise apps until they are removed',
    'description': """
        Enterprise bridge for bgg_custom_dev
        ====================================

        bgg_custom_dev no longer depends on Odoo Enterprise: its business rules
        use its own fields (RDV type and status on calendar events, SSS project
        flag). While the Enterprise apps are still installed, this bridge keeps
        those fields in sync with them:

        - Appointments: appointment_type_id / appointment_status on calendar
          events <-> x_rdv_type_id / x_rdv_status (both directions for the
          status), each appointment type linked to its RDV type, booking
          questionnaire automations (spouse contact, address, title, "pris à
          la place de") and the questionnaire summary on the event.
        - Field Service: is_fsm on projects -> x_is_sss_project.
        - Documents: project folder named "<order> - Projet - <client>".
        - "Créer tâches SSS": the SSS project and tasks are also Field Service
          ones (worksheet, customer address on the task).
        - The Odoo Studio view changes made on Enterprise screens (appointment
          buttons, list columns and type form).

        Installed automatically with Enterprise; removed together with the
        Enterprise apps when moving to Odoo Community. Holds no data of its own.
    """,
    'author': 'BelGoGreen',
    'website': 'https://www.belgogreen.com',
    'license': 'LGPL-3',
    'depends': [
        'bgg_custom_dev',
        'appointment',
        'documents_project',
        'industry_fsm',
    ],
    'data': [
        'views/calendar_event_views.xml',
        'views/studio_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': True,
}
