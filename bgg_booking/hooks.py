# -*- coding: utf-8 -*-

import logging

from odoo import Command

_logger = logging.getLogger(__name__)

# Opening hours of the study RDVs, as the Appointments types had them
# (Monday to Saturday 9:00-21:00, the commercials' working hours not used).
BOOKING_CALENDAR_NAME = 'RDV études (lun-sam 9h-21h)'
BOOKING_TZ = 'Europe/Brussels'
BOOKING_DAYS = ['0', '1', '2', '3', '4', '5']
BOOKING_HOURS = (9.0, 21.0)

# "Besoin" answers, in the Appointments order.
NEEDS = ['Panneau', 'Batterie', 'Boileur', 'Pompe à chaleur', 'Toiture', 'Isolation', 'Ballon']

# Questionnaire of each study type, from the former Appointments types.
_ENERGY = {'needs': ['Panneau', 'Batterie', 'Boileur', 'Pompe à chaleur'],
           'multiple': False, 'solar': True, 'sms': False}
BOOKING_TYPES = {
    'APT-ENERG-CNT': dict(_ENERGY, on_behalf=True),
    'APT-ENERG-COM': dict(_ENERGY, on_behalf=False),
    'APT-NISOL-CNT': {'needs': ['Panneau', 'Toiture', 'Isolation', 'Ballon', 'Pompe à chaleur'],
                      'multiple': True, 'solar': False, 'sms': True, 'on_behalf': True},
    'APT-NISOL-COM': {'needs': ['Panneau', 'Batterie', 'Boileur', 'Ballon', 'Pompe à chaleur'],
                      'multiple': True, 'solar': False, 'sms': True, 'on_behalf': False},
}
BOOKING_DURATION = 2.0
# Who books each type in "Prise de RDV" (as the Appointments pages showed
# the call centre its CNT types only): code suffix -> role (found by name).
BOOKING_TYPE_ROLES = {'-CNT': 'Call Center', '-COM': 'Commercial'}


# Top-level menus made by hand on production to open the Enterprise booking
# pages: module xmlid -> end of the URL they opened. Adopted before the
# module's data loads, so menu_views.xml repoints them to "Prise de RDV".
HAND_MADE_MENUS = {
    'menu_call_center_booking': '/book/callcenter',
    'menu_commercial_booking': '/book/commercial',
}


def adopt_booking_menus(cr):
    for xmlid, url in HAND_MADE_MENUS.items():
        cr.execute("SELECT 1 FROM ir_model_data WHERE module = 'bgg_booking' AND name = %s", [xmlid])
        if cr.fetchone():
            continue
        cr.execute("""SELECT m.id FROM ir_ui_menu m
                        JOIN ir_act_url a ON m.action = 'ir.actions.act_url,' || a.id
                       WHERE m.parent_id IS NULL AND a.url LIKE %s
                         AND NOT EXISTS (SELECT 1 FROM ir_model_data d WHERE d.model = 'ir.ui.menu' AND d.res_id = m.id
                                            AND d.module NOT IN ('__custom__', '__export__'))
                       ORDER BY m.id LIMIT 1""", ['%' + url])
        row = cr.fetchone()
        if row:
            cr.execute("""INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
                          VALUES ('bgg_booking', %s, 'ir.ui.menu', %s, false)""", [xmlid, row[0]])
            _logger.info("bgg_booking: menu %s (id %s, link to %s) adopted, now opens Prise de RDV",
                         xmlid, row[0], url)


def pre_init(env):
    adopt_booking_menus(env.cr)


def link_booking_groups(env):
    """The "Call Center" and "Commercial" roles (created by hand, found by
    name) get the booking right: the call centre books the CNT types, the
    commercials the COM ones."""
    agent = env.ref('bgg_booking.group_booking_agent')
    for name in ('Call Center', 'Commercial'):
        group = env['calendar.event']._find_group_by_name(name)
        if group:
            group.implied_ids |= agent
            _logger.info("bgg_booking: '%s' group now includes 'Prise de RDV (call center)'", name)
        else:
            _logger.warning("bgg_booking: group '%s' not found, give 'Prise de RDV (call center)' by hand", name)


def _booking_calendar(env):
    Calendar = env['resource.calendar']
    calendar = Calendar.search([('name', '=', BOOKING_CALENDAR_NAME)], limit=1)
    if not calendar:
        calendar = Calendar.create({
            'name': BOOKING_CALENDAR_NAME,
            'tz': BOOKING_TZ,
            'company_id': False,
            'attendance_ids': [Command.clear()] + [Command.create({
                'name': f'RDV {day}', 'dayofweek': day, 'day_period': 'morning',
                'hour_from': BOOKING_HOURS[0], 'hour_to': BOOKING_HOURS[1],
            }) for day in BOOKING_DAYS],
        })
    return calendar


def _commercial_combination(env, user, calendar):
    """A combination with one resource: the commercial, on the booking
    calendar (one per commercial, shared by the types)."""
    resource = env['resource.resource'].search([
        ('user_id', '=', user.id), ('resource_type', '=', 'user'), ('calendar_id', '=', calendar.id)], limit=1)
    if not resource:
        resource = env['resource.resource'].create({
            'name': user.name, 'resource_type': 'user', 'user_id': user.id,
            'calendar_id': calendar.id, 'tz': BOOKING_TZ, 'company_id': False,
        })
    combination = env['resource.booking.combination'].search(
        [('resource_ids', '=', resource.id)]).filtered(lambda c: c.resource_ids == resource)[:1]
    return combination or env['resource.booking.combination'].create({'resource_ids': [Command.set(resource.ids)]})


def setup_booking_types(env):
    """Create the booking types of the study RDV types (one per RDV type
    with a known code and no booking type yet), with their questionnaire and
    the commercials listed on the RDV type (copied from Appointments)."""
    Need = env['bgg.rdv.need'].with_context(active_test=False)
    needs = {}
    for sequence, name in enumerate(NEEDS, start=1):
        needs[name] = Need.search([('name', '=', name)], limit=1) or Need.create({'name': name, 'sequence': sequence})
    calendar = _booking_calendar(env)
    BookingType = env['resource.booking.type']
    rdv_types = env['bgg.rdv.type'].search([('code', 'in', list(BOOKING_TYPES))])
    for rdv_type in rdv_types.filtered(lambda t: not BookingType.search_count([('x_rdv_type_id', '=', t.id)])):
        config = BOOKING_TYPES[rdv_type.code]
        commercials = rdv_type.user_ids.filtered(lambda u: u.active and not u.share)
        BookingType.create({
            'name': rdv_type.name,
            'x_rdv_type_id': rdv_type.id,
            'company_id': False,
            'resource_calendar_id': calendar.id,
            'duration': BOOKING_DURATION,
            'slot_duration': BOOKING_DURATION,
            'modifications_deadline': 0,
            'x_need_ids': [Command.set([needs[name].id for name in config['needs']])],
            'x_need_multiple': config['multiple'],
            'x_ask_solar_since': config['solar'],
            'x_ask_sms_confirmation': config['sms'],
            'x_ask_on_behalf': config['on_behalf'],
            'x_create_opportunity': True,
            'combination_rel_ids': [Command.create({'combination_id': _commercial_combination(env, user, calendar).id})
                                    for user in commercials],
        })
        _logger.info("bgg_booking: booking type '%s' created with %s commercial(s)", rdv_type.name, len(commercials))


def set_booking_type_roles(env):
    """"Réservable par" of the study types without one: the call centre for
    the CNT types, the commercials for the COM types."""
    types = env['resource.booking.type'].with_context(active_test=False).search(
        [('x_rdv_type_id.code', '!=', False), ('x_group_ids', '=', False)])
    for booking_type in types:
        for suffix, name in BOOKING_TYPE_ROLES.items():
            if booking_type.x_rdv_type_id.code.endswith(suffix):
                group = env['calendar.event']._find_group_by_name(name)
                if group:
                    booking_type.x_group_ids = group
                else:
                    _logger.warning("bgg_booking: group '%s' not found, set 'Réservable par' of '%s' by hand",
                                    name, booking_type.name)


def give_amss_admin_booking(env):
    """AMSS ADMIN books the call-centre types (CNT) as the call centre, with
    "pris à la place de", without being in the Call Center role: in
    Enterprise the booking page was a link anyone could open. Its group gets
    "Prise de RDV (call center)" and is added to "Réservable par" of the CNT
    types (the COM types stay with the commercials)."""
    admin = env.ref('bgg_custom_dev.group_amss_admin', raise_if_not_found=False)
    if not admin:
        _logger.warning("bgg_booking: group AMSS ADMIN not found, give it 'Prise de RDV' by hand")
        return
    admin.implied_ids |= env.ref('bgg_booking.group_booking_agent')
    types = env['resource.booking.type'].with_context(active_test=False).search(
        [('x_rdv_type_id.code', '=like', '%-CNT')])
    for booking_type in types.filtered(lambda t: admin not in t.x_group_ids):
        booking_type.x_group_ids |= admin
    _logger.info("bgg_booking: AMSS ADMIN books the call-centre types (%s)", ', '.join(types.mapped('name')))


def share_booking_records(env):
    """The booking types, their calendar and the commercials' resources are
    shared by all companies (the call centre books for AMSS and Natur'Isol):
    created without company, else the multi-company rules hide them from the
    users working in another company."""
    types = env['resource.booking.type'].with_context(active_test=False).search([('x_rdv_type_id', '!=', False)])
    resources = types.combination_rel_ids.combination_id.resource_ids
    calendars = types.resource_calendar_id | resources.calendar_id
    for records in (types, resources, calendars):
        records.filtered('company_id').write({'company_id': False})


def post_init(env):
    link_booking_groups(env)
    setup_booking_types(env)
    share_booking_records(env)
    set_booking_type_roles(env)
    give_amss_admin_booking(env)
