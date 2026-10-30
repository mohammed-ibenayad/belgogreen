# -*- coding: utf-8 -*-
{
    'name': 'BelGoGreen Custom Development',
    'version': '19.0.2.3.0',
    'category': 'Customizations',
    'summary': 'Custom business logic and automation for BelGoGreen',
    'description': """
        BelGoGreen Custom Development Module
        ====================================

        This module extends core Odoo models with custom business logic.

        Model Extensions:

        **No Enterprise dependency (19.0.2.0.0)**: the rules use the module's
        own fields: RDV type (bgg.rdv.type, with its reference code) and RDV
        status on calendar events, questionnaire answers summary on the event,
        SSS project flag (x_is_sss_project). While Odoo Enterprise is
        installed, the bridge module bgg_custom_dev_ee keeps them in sync with
        Appointments / Field Service and holds the Enterprise-only automations
        listed below (appointment answers, documents folder name).

        **Appointment Management (appointment.answer.input, in bgg_custom_dev_ee)**:
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
        - Document folder naming from sales orders (bgg_custom_dev_ee)
        - Admin project deadlines: project start = order confirmation date,
          project end = field service (SSS) reference end date + end_offset
          (10 business days), the SSS reference dates coming from the
          payment term x product category rules
          (bgg.admin_project_deadline_rules system parameter); task
          deadlines = project end date
        - Admin template tasks listed in bgg.admin_task_deadline_rules
          (Réclamation du solde, Création des commissions, Chargement
          schéma unifilaire, Envoi Belgotest) take their dates from the
          SSS reference dates computed from the same rules
        - Admin projects: project manager and planned dates are computed
          from the order and locked against manual edits
        - "Bloqué" project status (status updates), admin projects only, set
          or removed by the Responsable Dossier group
        - "Bloqué" task state (admin projects, Responsable Dossier group),
          kept when the stage or the dependencies change: a blocked task sets
          its project to Bloqué; once no task is blocked the project gets its
          previous status back
        - Admin projects become Terminé once all their tasks are closed (done
          or cancelled), and get their previous status back if a task is
          reopened or added

        **Sales Orders (sale.order)**:
        - Call Center (Sale Owner) attribution and RDV smart button
        - "Dossier" tab with the "Responsable" of the order (project manager
          of the sale), restricted to the "Responsable Dossier" group
        - The Responsable is propagated to the projects of the order as
          project manager and as assignee of their open tasks
        - "Confirmée au moins une fois" flag (x_was_confirmed): the dashboards
          (Suivi Commercial, Call Center, AMSS) count a cancelled order as a
          cancelled sale only if it was confirmed before; cancelled quotes are
          left out (existing orders filled from the status history)
        - Form warnings: Responsable not assigned on a confirmed order,
          installation product (project-creating service) missing
        - Only the "Responsable Dossier Admin" group may set or change the
          Responsable of an order
        - "Créer tâches SSS" (button for AMSS ADMIN, Action menu): for each
          confirmed order with a (partly) paid invoice, a project flagged SSS
          "<order> - SSS - <client>" linked to the order (manager from the
          bgg.sss_project_manager_login parameter, stages "SSS: À faire" /
          "SSS: Encours/Fait") with one task "<qty> x <product>" per
          consumable product of the "All / Saleable" category; "Tâches" smart
          button; "Recalculate Project deadline" action

        **AMSS Management dashboard (Direction group)**:
        - Direction tab: CA NET, Ventes Confirmées (+ annulées), TX Conversion
          (lists the RDV présents) (same formulas as Suivi Commercial, all
          orders and appointments),
          Chantiers en retard, Dossiers bloqués, CA signé / facturé /
          encaissé (reste à facturer / à encaisser clickable in the bars),
          Reste à facturer / Reste à encaisser / Reste à encaisser – chantiers SSS
          terminés cards (à ce jour), Carnet de commandes (À planifier / Planifiés / En cours /
          Bloqués, today); comparison with the previous period; Excel export
        - Métiers tab: same filters and KPI cards, CA signé par métier (each
          order in one métier: Photovoltaïque = Panneaux / Onduleurs /
          Batteries, Chauffage / PAC = PAC / Boilers, Isolation, Autres
          métiers; Mixte when several)
        - Commercial tab (salesperson filter): BC signés par commercial,
          entonnoir de conversion (RDV posés / tenus / BC signés), qualité
          commerciale (panier moyen global and per métier, annulation après
          signature)

        **Former Odoo Studio customizations (19.0.2.1.0)**: fields (same
        names and tables, data kept), view changes (calendar, sale order,
        contacts, projects, tasks, SMS, logs, payment terms), saved filters,
        "Clôturer les projets Admin/SSS" (projects), "Rappel pour statuer les
        rendez-vous énergétique" (events, Action menu + daily job, inactive)
        and "Créer tâches SSS" now live in this module; the Enterprise parts
        are in bgg_custom_dev_ee.

        **Commercials per RDV type (19.0.2.2.0)**: the staff of each Enterprise
        appointment type is copied to its RDV type (Commerciaux) and kept in
        sync by bgg_custom_dev_ee, so the Community booking can be set up from
        it.

        All business logic includes comprehensive logging for debugging and monitoring.
    """,
    'author': 'BelGoGreen',
    'website': 'https://www.belgogreen.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'calendar',
        'crm',
        'project',
        'sale_project',
        'sale',
        'sms',
        'spreadsheet_dashboard',
    ],
    'data': [
        # Security
        'security/groups.xml',
        'security/calendar_rules.xml',
        'security/ir.model.access.csv',

        # Configuration data
        'data/noshow_config_params.xml',
        'data/admin_project_deadline_params.xml',

        # Views
        'views/bgg_rdv_type_views.xml',
        'views/calendar_event_views.xml',
        'views/commercial_dashboard_views.xml',
        'views/call_center_dashboard_views.xml',
        'views/sale_order_views.xml',
        'views/project_project_views.xml',
        'views/project_task_views.xml',
        'views/amss_dashboard_views.xml',

        # Reports (action must be loaded before menu that references it)
        'report/avis_count_report_views.xml',

        # Menus
        'views/menu_views.xml',
        'views/res_partner_views.xml',
        'views/studio_views.xml',

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
            'bgg_custom_dev/static/src/js/amss_dashboard.js',
            'bgg_custom_dev/static/src/xml/amss_dashboard.xml',
            'bgg_custom_dev/static/src/scss/amss_dashboard.scss',
            'bgg_custom_dev/static/src/js/project_status_blocked.js',
            'bgg_custom_dev/static/src/js/project_task_state_blocked.js',
        ],
    },
    'post_init_hook': 'link_external_groups',
    'installable': True,
    'application': False,
    'auto_install': False,
}
