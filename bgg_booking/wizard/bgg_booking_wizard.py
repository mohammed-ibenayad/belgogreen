# -*- coding: utf-8 -*-

import datetime

import babel.dates
import pytz

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

BGG_TZ = 'Europe/Brussels'
# Phone numbers are compared on their last digits (same rule as the calendar
# event customer deduplication of bgg_custom_dev).
PHONE_MATCH_DIGITS = 8
# The steps of the form, as the Appointments booking pages the call centre
# used: type, commercial, date & time, details, booked.
STEPS = [
    ('type', 'Type de RDV'),
    ('operator', 'Commercial'),
    ('slot', 'Date & heure'),
    ('details', 'Coordonnées'),
    ('done', 'Réservé'),
]
# How far ahead the next free day is looked for.
SEARCH_DAYS = 60


def phone_key(phone):
    digits = ''.join(ch for ch in phone or '' if ch.isdigit())
    return digits[-PHONE_MATCH_DIGITS:] if len(digits) >= PHONE_MATCH_DIGITS else ''


class BggBookingWizard(models.TransientModel):
    """"Prise de RDV": the call-centre booking form, in the steps of the
    Appointments booking pages: the RDV type, the commercial (or all their
    availabilities), the day and the time, the client's details and the
    questionnaire, then the booking."""
    _name = 'bgg.booking.wizard'
    _description = 'Prise de RDV (call center)'

    state = fields.Selection(STEPS, string='Étape', default='type', required=True)

    # 1. Type
    allowed_type_ids = fields.Many2many('resource.booking.type', compute='_compute_allowed_type_ids')
    type_id = fields.Many2one('resource.booking.type', string='Type de RDV',
                              domain="[('id', 'in', allowed_type_ids)]")
    allowed_need_ids = fields.Many2many(related='type_id.x_need_ids')
    need_multiple = fields.Boolean(related='type_id.x_need_multiple')
    ask_solar_since = fields.Boolean(related='type_id.x_ask_solar_since')
    ask_sms_confirmation = fields.Boolean(related='type_id.x_ask_sms_confirmation')
    ask_on_behalf = fields.Boolean(related='type_id.x_ask_on_behalf')
    duration = fields.Float(related='type_id.duration', string='Durée')

    # 2. Commercial (empty: all the commercials of the type)
    allowed_combination_ids = fields.Many2many('resource.booking.combination',
                                               compute='_compute_allowed_combination_ids')
    combination_id = fields.Many2one('resource.booking.combination', string='Commercial',
                                     domain="[('id', 'in', allowed_combination_ids)]")

    # 3. Date & time
    date = fields.Date(string='Jour',
                       default=lambda self: fields.Date.context_today(self) + datetime.timedelta(days=1))
    slot_ids = fields.One2many('bgg.booking.wizard.slot', 'wizard_id', string='Heures libres')
    start = fields.Datetime(string='Début du RDV', readonly=True)
    slot_combination_id = fields.Many2one('resource.booking.combination', string='Commercial du RDV',
                                          readonly=True)
    start_label = fields.Char(string='Date et heure', compute='_compute_start_label')
    date_label = fields.Char(compute='_compute_date_label')

    # 4. Details: client
    partner_name = fields.Char(string='Nom complet')
    email = fields.Char(string='Email')
    phone = fields.Char(string='Téléphone')
    partner_id = fields.Many2one('res.partner', string='Client existant')
    street = fields.Char(string='Adresse')
    zip = fields.Char(string='Code postal')
    city = fields.Char(string='Ville')
    country_id = fields.Many2one('res.country', string='Pays',
                                 default=lambda self: self.env.ref('base.be', raise_if_not_found=False))
    # 4. Details: questionnaire (the questions asked depend on the type)
    solar_since = fields.Char(string='Depuis combien de temps les clients ont-ils des panneaux solaires ?')
    is_owner = fields.Selection([('yes', 'Oui'), ('no', 'Non')],
                                string='Les clients sont-ils bien les propriétaires du bien ?')
    spouse_name = fields.Char(string='Nom du conjoint')
    spouse_phone = fields.Char(string='Numéro de téléphone du conjoint')
    need_ids = fields.Many2many('bgg.rdv.need', string='Besoin',
                                domain="[('id', 'in', allowed_need_ids)]")
    comments = fields.Text(string='Commentaires')
    on_behalf_id = fields.Many2one('res.partner', string='Rendez-vous pris à la place de',
                                   domain="[('category_id.name', '=', 'Call Center')]")
    sms_confirmation = fields.Boolean(string='Confirmation du RDV par SMS')

    # 5. Booked
    meeting_id = fields.Many2one('calendar.event', string='RDV', readonly=True)

    def _locale(self):
        return (self.env.lang or 'fr_BE').replace('-', '_')

    @api.depends('start', 'type_id')
    def _compute_start_label(self):
        """The chosen time in the RDV time zone (Brussels), not the browser's."""
        for wizard in self:
            wizard.start_label = wizard.start and babel.dates.format_datetime(
                pytz.utc.localize(wizard.start), "EEEE d MMMM yyyy, HH:mm",
                tzinfo=wizard._booking_tz(), locale=wizard._locale()) or False

    @api.depends('date')
    def _compute_date_label(self):
        for wizard in self:
            wizard.date_label = wizard.date and babel.dates.format_date(
                wizard.date, "EEEE d MMMM yyyy", locale=wizard._locale()).capitalize() or False

    @api.depends_context('uid')
    def _compute_allowed_type_ids(self):
        """The types the user books ("Réservable par"); all for the booking
        managers."""
        types = self.env['resource.booking.type'].search([('x_rdv_type_id', '!=', False)])
        if not self.env.user.has_group('resource_booking.group_manager'):
            groups = self.env.user.all_group_ids
            types = types.filtered(lambda t: not t.x_group_ids or t.x_group_ids & groups)
        for wizard in self:
            wizard.allowed_type_ids = types

    @api.depends('type_id')
    def _compute_allowed_combination_ids(self):
        for wizard in self:
            wizard.allowed_combination_ids = wizard.type_id.combination_rel_ids.combination_id

    @api.onchange('phone')
    def _onchange_phone(self):
        key = phone_key(self.phone)
        if not key or (self.partner_id and phone_key(self.partner_id.phone) == key):
            return
        partner = self._find_partner_by_phone(key)
        if partner:
            self.partner_id = partner

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        partner = self.partner_id
        if not partner:
            return
        # the client's data, without erasing what was already typed
        self.partner_name = partner.name
        self.email = partner.email or self.email
        self.phone = self.phone or partner.phone
        self.street = partner.street or self.street
        self.zip = partner.zip or self.zip
        self.city = partner.city or self.city
        self.country_id = partner.country_id or self.country_id

    @api.onchange('type_id')
    def _onchange_type_id(self):
        self.need_ids = self.need_ids & self.type_id.x_need_ids
        if self.combination_id not in self.type_id.combination_rel_ids.combination_id:
            self.combination_id = False

    @api.model
    def _find_partner_by_phone(self, key):
        """Oldest non-internal contact whose phone ends with the same digits
        (spaces, dots, country prefix... ignored)."""
        self.env['res.partner'].flush_model(['phone'])
        self.env.cr.execute(
            "SELECT id FROM res_partner WHERE active AND phone IS NOT NULL "
            "AND right(regexp_replace(phone, '[^0-9]', '', 'g'), %s) = %s ORDER BY create_date, id",
            [PHONE_MATCH_DIGITS, key])
        partners = self.env['res.partner'].browse([row[0] for row in self.env.cr.fetchall()])
        return partners.filtered(lambda p: not p.user_ids.filtered(lambda u: not u.share))[:1]

    # ------------------------------------------------------------------
    # Free slots
    # ------------------------------------------------------------------

    def _booking_tz(self):
        return pytz.timezone(self.type_id.resource_calendar_id.tz or self.env.user.tz or BGG_TZ)

    def _available_slots(self, first_day, days=1):
        """[(start (UTC, naive), combination)] free from first_day, for
        `days` days, for the chosen commercial or all those of the type."""
        self.ensure_one()
        tz = self._booking_tz()
        range_start = tz.localize(datetime.datetime.combine(first_day, datetime.time.min))
        range_end = range_start + datetime.timedelta(days=days)
        # With all rights, as the check made when the booking is saved: the
        # call centre does not see all the commercials' events (e.g. RDV
        # types hidden from it) but must not book over them.
        Booking = self.env['resource.booking'].sudo()
        combinations = (self.combination_id or self.type_id._get_combinations_priorized()).sudo()
        slots = []
        for combination in combinations:
            booking = Booking.new({
                'type_id': self.type_id.id,
                'combination_id': combination.id,
                'combination_auto_assign': False,
                'duration': self.type_id.duration,
            })
            for starts in booking._get_available_slots(range_start, range_end).values():
                for start in starts:
                    if start < range_end:
                        slots.append((start.astimezone(pytz.utc).replace(tzinfo=None), combination))
        return sorted(slots, key=lambda slot: (slot[0], slot[1].id))

    def _local_day(self, start):
        return pytz.utc.localize(start).astimezone(self._booking_tz()).date()

    @api.onchange('date')
    def _onchange_date(self):
        if self.state == 'slot' and self.type_id and self.date:
            self._show_day(self.date)

    def _show_day(self, day):
        """The free times of `day`."""
        self.date = day
        self.slot_ids = [Command.clear()] + [
            Command.create({'start': start, 'combination_id': combination.id})
            for start, combination in self._available_slots(day)]

    def _show_next_free_day(self, from_day):
        """The first day with a free time from `from_day` on (the day itself
        when nothing is free in the next SEARCH_DAYS days)."""
        slots = self._available_slots(from_day, SEARCH_DAYS)
        self._show_day(self._local_day(slots[0][0]) if slots else from_day)

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'name': self.env._('Prise de RDV'),
        }

    def action_choose_type(self):
        self.ensure_one()
        if not self.type_id:
            raise UserError(self.env._("Choisissez le type de rendez-vous."))
        if self.type_id not in self.allowed_type_ids:
            raise UserError(self.env._("Ce type de rendez-vous n'est pas réservable par vous."))
        if not self.type_id.combination_rel_ids:
            raise UserError(self.env._("Aucun commercial pour ce type de rendez-vous."))
        self.state = 'operator'
        return self._reopen()

    def action_choose_operator(self):
        self.ensure_one()
        if not self.combination_id:
            raise UserError(self.env._("Choisissez un commercial, ou affichez toutes les disponibilités."))
        return self._goto_slots()

    def action_all_availabilities(self):
        self.ensure_one()
        self.combination_id = False
        return self._goto_slots()

    def _goto_slots(self):
        self._show_next_free_day(max(self.date or fields.Date.context_today(self), fields.Date.context_today(self)))
        self.state = 'slot'
        return self._reopen()

    def action_previous_day(self):
        self.ensure_one()
        self._show_day(max(self.date - datetime.timedelta(days=1), fields.Date.context_today(self)))
        return self._reopen()

    def action_next_day(self):
        self.ensure_one()
        self._show_day(self.date + datetime.timedelta(days=1))
        return self._reopen()

    def action_next_free_day(self):
        self.ensure_one()
        self._show_next_free_day(self.date + datetime.timedelta(days=1))
        return self._reopen()

    def action_show_day(self):
        self.ensure_one()
        self._show_day(self.date)
        return self._reopen()

    def _choose_slot(self, slot):
        self.ensure_one()
        self.write({'start': slot.start, 'slot_combination_id': slot.combination_id.id, 'state': 'details'})
        return self._reopen()

    def action_back(self):
        self.ensure_one()
        previous = {'operator': 'type', 'slot': 'operator', 'details': 'slot'}
        self.state = previous.get(self.state, self.state)
        if self.state == 'slot':
            self._show_day(self.date)
        return self._reopen()

    def action_confirm(self):
        """Book the chosen time."""
        self.ensure_one()
        if not self.start or not self.slot_combination_id:
            raise UserError(self.env._("Choisissez d'abord une heure."))
        booking = self._book()
        self.write({'meeting_id': booking.meeting_id.id, 'state': 'done'})
        return self._reopen()

    def action_open_meeting(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'calendar.event',
            'res_id': self.meeting_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_new_booking(self):
        return self.env['ir.actions.act_window']._for_xml_id('bgg_booking.bgg_booking_wizard_action')

    # ------------------------------------------------------------------
    # Booking
    # ------------------------------------------------------------------

    def _get_or_create_partner(self):
        """The client of the booking. Created / completed in sudo, as
        Appointments did: the call centre books without contact rights."""
        self.ensure_one()
        partner = self.partner_id.sudo()
        if not partner:
            partner = partner.create({
                'name': self.partner_name,
                'phone': self.phone,
                'email': self.email,
                'street': self.street,
                'zip': self.zip,
                'city': self.city,
                'country_id': self.country_id.id,
            })
            self.partner_id = partner
        else:
            missing = {key: value for key, value in (('phone', self.phone), ('email', self.email))
                       if value and not partner[key]}
            if missing:
                partner.write(missing)
        return partner.with_env(self.env)

    def _check_questionnaire(self):
        """The questions the Appointments form made mandatory (the email is
        not: the call centre had to type a fake one)."""
        self.ensure_one()
        labels = self._fields
        missing = [labels[name].string for name in ('phone', 'street', 'zip', 'city', 'country_id', 'is_owner',
                                                    'need_ids')
                   if not self[name]]
        if self.ask_solar_since and not self.solar_since:
            missing.append(labels['solar_since'].string)
        if not self.partner_id and not self.partner_name:
            missing.insert(0, labels['partner_name'].string)
        if missing:
            raise UserError(self.env._("À compléter avant de réserver :\n- %s", "\n- ".join(missing)))
        if not self.need_multiple and len(self.need_ids) > 1:
            raise UserError(self.env._("Un seul besoin pour ce type de rendez-vous."))

    def _book(self):
        self.ensure_one()
        self._check_questionnaire()
        partner = self._get_or_create_partner()
        return self.env['resource.booking'].create({
            'type_id': self.type_id.id,
            'partner_ids': [Command.set(partner.ids)],
            'combination_auto_assign': False,
            'combination_id': self.slot_combination_id.id,
            'start': self.start,
            'x_street': self.street,
            'x_zip': self.zip,
            'x_city': self.city,
            'x_country_id': self.country_id.id,
            'x_solar_since': self.ask_solar_since and self.solar_since or False,
            'x_is_owner': self.is_owner,
            'x_need_ids': [Command.set(self.need_ids.ids)],
            'x_spouse_name': self.spouse_name,
            'x_spouse_phone': self.spouse_phone,
            'x_sms_confirmation': self.ask_sms_confirmation and self.sms_confirmation,
            'x_comments': self.comments,
            'x_on_behalf_id': self.ask_on_behalf and self.on_behalf_id.id or False,
        })


class BggBookingWizardSlot(models.TransientModel):
    _name = 'bgg.booking.wizard.slot'
    _description = 'Heure libre (prise de RDV)'
    _order = 'start, id'

    wizard_id = fields.Many2one('bgg.booking.wizard', required=True, ondelete='cascade')
    start = fields.Datetime(string='Début', required=True)
    combination_id = fields.Many2one('resource.booking.combination', string='Commercial', required=True)
    time_label = fields.Char(string='Heure', compute='_compute_time_label')

    @api.depends('start')
    def _compute_time_label(self):
        for slot in self:
            tz = slot.wizard_id._booking_tz() if slot.wizard_id.type_id else pytz.timezone(BGG_TZ)
            slot.time_label = pytz.utc.localize(slot.start).astimezone(tz).strftime('%H:%M') if slot.start else ''

    def action_choose(self):
        self.ensure_one()
        return self.wizard_id._choose_slot(self)
