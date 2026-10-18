# -*- coding: utf-8 -*-
{
    'name': 'BelGoGreen - Prise de RDV call center',
    'version': '19.0.1.0.0',
    'category': 'Customizations',
    'summary': 'Call-centre appointment booking on OCA Resource Booking (replaces Enterprise Appointments)',
    'description': """
        Prise de RDV call center
        ========================

        Replaces the Enterprise Appointments booking form used by the call
        centre, on top of OCA resource_booking (Odoo Community):

        - "Prise de RDV" form: client found by phone (or created), address,
          questionnaire (besoin, conjoint, confirmation SMS, RDV pris à la
          place de), free slots of the day per commercial, booking in one
          click.
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

        Call-centre agents need the "Prise de RDV (call center)" group (all
        bookings); it is added to the "Call Center" role at installation.

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
    'post_init_hook': 'link_call_center_group',
    'installable': True,
    'application': False,
    'auto_install': False,
}
