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
    ],
    'data': [
        # Security
        # 'security/ir.model.access.csv',

        # Views
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
