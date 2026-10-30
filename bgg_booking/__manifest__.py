# -*- coding: utf-8 -*-
{
    'name': 'BelGoGreen - Prise de RDV call center',
    'version': '19.0.1.4.0',
    'category': 'Customizations',
    'summary': 'Call-centre appointment booking on OCA Resource Booking (replaces Enterprise Appointments)',
    'description': """
        Prise de RDV call center
        ========================

        Replaces the Enterprise Appointments booking form used by the call
        centre, on top of OCA resource_booking (Odoo Community):

        - "Prise de RDV" form, in the steps of the Appointments booking pages
          the call centre used: RDV type, commercial (or all their
          availabilities), day and time (month calendar of the free days,
          then the free times of the day as buttons), the client's details and the questionnaire of the type in the
          same order (client found by phone or created; besoin - one or
          several -, propriétaires, panneaux depuis, conjoint, commentaires,
          RDV pris à la place de, confirmation SMS), then booked.
        - Booking types, their calendar and the commercials' resources are
          shared by all companies.
        - "Réservable par" on each booking type: the call centre sees the
          call-centre types (CNT), the commercials the "par commercial" ones
          (COM), as the Appointments pages showed them; booking managers see
          all.
        - A CRM opportunity is created for each RDV and linked to it (sale
          order attribution, organizer of the RDV).
        - Each booking type is linked to a bgg_custom_dev RDV type. The
          meeting created by the booking carries the RDV type, the "Réservé"
          status, the questionnaire summary and the "pris à la place de"
          partner; its organizer is the booked commercial and its title is
          "<client>/<code postal>/<téléphone>/<besoins>/<commercial>"
          (📞 first when an SMS confirmation is asked), as with Appointments.
        - The questionnaire updates the client (address) and creates the
          spouse contact.
        - Cancelling a booking keeps its meeting, with the "Annulé" status
          (dashboards and reports count it); cancelled RDVs do not block the
          commercial's slot.

        Installation: the study booking types are created from the RDV types
        and their commercials (Mon-Sat 9:00-21:00, 2 h RDVs, questionnaire of
        each type); the "Prise de RDV (call center)" group (all bookings) is
        added to the "Call Center" and "Commercial" roles.

        Requires the OCA modules resource_booking (OCA/calendar) and
        web_calendar_slot_duration (OCA/web). Not for Odoo.sh: installed on
        the Community server only.
    """,
    'author': 'BelGoGreen',
    'website': 'https://www.belgogreen.com',
    'license': 'LGPL-3',
    'depends': [
        'bgg_custom_dev',
        'resource_booking',
    ],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'views/bgg_rdv_need_views.xml',
        'views/resource_booking_type_views.xml',
        'views/resource_booking_views.xml',
        'wizard/bgg_booking_wizard_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'bgg_booking/static/src/month_calendar/*',
        ],
    },
    'pre_init_hook': 'pre_init',
    'post_init_hook': 'post_init',
    'installable': True,
    'application': False,
    'auto_install': False,
}
