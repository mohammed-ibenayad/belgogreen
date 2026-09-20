# -*- coding: utf-8 -*-
{
    'name': 'BelGoGreen Custom Development',
    'version': '19.0.1.7.0',
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
        - Admin project deadlines: project start = order confirmation date,
          project end = start + delay from the payment term x product
          category rules (bgg.admin_project_deadline_rules system
          parameter), task deadlines = project end date
        - Admin projects: project manager and planned dates are computed
          from the order and locked against manual edits

        **Sales Orders (sale.order)**:
        - Call Center (Sale Owner) attribution and RDV smart button
        - "Dossier" tab with the "Responsable" of the order (project manager
          of the sale), restricted to the "Responsable Dossier" group
        - The Responsable is propagated to the projects of the order as
          project manager and as assignee of their open tasks
        - Form warnings: Responsable not assigned on a confirmed order,
          installation product (project-creating service) missing

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
        'security/groups.xml',
        'security/ir.model.access.csv',

        # Configuration data
        'data/noshow_config_params.xml',
        'data/admin_project_deadline_params.xml',

        # Views
        'views/calendar_event_views.xml',
        'views/commercial_dashboard_views.xml',
        'views/call_center_dashboard_views.xml',
        'views/sale_order_views.xml',
        'views/project_project_views.xml',

        # Reports (action must be loaded before menu that references it)
        'report/avis_count_report_views.xml',

        # Menus
        'views/menu_views.xml',
        'views/res_partner_views.xml',

        # Server actions
        'data/sale_order_server_actions.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'bgg_custom_dev/static/src/js/commercial_dashboard.js',
            'bgg_custom_dev/static/src/xml/commercial_dashboard.xml',
            'bgg_custom_dev/static/src/scss/commercial_dashboard.scss',
            'bgg_custom_dev/static/src/js/call_center_dashboard.js',
            'bgg_custom_dev/static/src/xml/call_center_dashboard.xml',
            'bgg_custom_dev/static/src/scss/call_center_dashboard.scss',
        ],
    },
    'post_init_hook': 'link_external_groups',
    'installable': True,
    'application': False,
    'auto_install': False,
}
