# -*- coding: utf-8 -*-
{
    'name': 'BelGoGreen Custom Development',
    'version': '19.0.1.1.0',
    'category': 'Customizations',
    'summary': 'Custom business logic and automation for BelGoGreen',
    'description': """
        BelGoGreen Custom Development Module
        ====================================

        This module extends core Odoo models with custom business logic.

        Model Extensions:

        **Appointment Management (appointment.answer.input)**:
        - Automatic spouse contact creation/update
        - Partner address information updates
        - Dynamic appointment title building
        - Clickable phone number generation
        - Call center partner assignment

        **Calendar Events (calendar.event)**:
        - Automatic organizer assignment
        - NoShow activity management on rescheduling
        - Clickable address and phone links
        - Client attendee information sync
        - Internal email protection (call center email replacement)
        - Customer deduplication by phone number

        **Project Management (project.project, project.task)**:
        - Document folder naming from sales orders
        - Welcome call deadline calculation (order date + 2 days)

        All business logic includes comprehensive logging for debugging and monitoring.
    """,
    'author': 'BelGoGreen',
    'website': 'https://www.belgogreen.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'calendar',
        'appointment',
        'crm',
        'project',
        'documents',
        'sale_project',
        'sale',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',

        # Views
        'views/calendar_event_views.xml',
        'views/commercial_dashboard_views.xml',

        # Reports (action must be loaded before menu that references it)
        'report/avis_count_report_views.xml',

        # Menus
        'views/menu_views.xml',
        'views/res_partner_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'bgg_custom_dev/static/src/js/commercial_dashboard.js',
            'bgg_custom_dev/static/src/xml/commercial_dashboard.xml',
            'bgg_custom_dev/static/src/scss/commercial_dashboard.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'post_init_hook': '_assign_admin_group_to_menus',
}
