# -*- coding: utf-8 -*-

import datetime

import pytz

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

BGG_TZ = 'Europe/Brussels'
# Phone numbers are compared on their last digits (same rule as the calendar
# event customer deduplication of bgg_custom_dev).
PHONE_MATCH_DIGITS = 8


def phone_key(phone):
    digits = ''.join(ch for ch in phone or '' if ch.isdigit())
    return digits[-PHONE_MATCH_DIGITS:] if len(digits) >= PHONE_MATCH_DIGITS else ''


class BggBookingWizard(models.TransientModel):
    """"Prise de RDV": the call-centre booking form. The client is looked up
    by phone (or created), the questionnaire is filled in, then the free slots
    of the chosen day are listed per commercial and one is booked."""
    _name = 'bgg.booking.wizard'
    _description = 'Prise de RDV (call center)'

    # Client
    phone = fields.Char(string='Téléphone', required=True)
    partner_id = fields.Many2one('res.partner', string='Client existant')
    partner_name = fields.Char(string='Nom du client')
    email = fields.Char(string='Email')
    street = fields.Char(string='Adresse')
    zip = fields.Char(string='Code postal')
    city = fields.Char(string='Ville')
    country_id = fields.Many2one('res.country', string='Pays',
                                 default=lambda self: self.env.ref('base.be', raise_if_not_found=False))
    # Questionnaire
    need_ids = fields.Many2many('bgg.rdv.need', string='Besoin')
    spouse_name = fields.Char(string='Nom du conjoint')
    spouse_phone = fields.Char(string='Téléphone du conjoint')
    sms_confirmation = fields.Boolean(string='Confirmation du RDV par SMS')
    on_behalf_id = fields.Many2one('res.partner', string='RDV pris à la place de',
                                   domain="[('category_id.name', '=', 'Call Center')]")
    note = fields.Text(string='Remarque')
    # Slot
    type_id = fields.Many2one('resource.booking.type', string='Type de RDV', required=True,
                              domain="[('x_rdv_type_id', '!=', False)]")
    date = fields.Date(string='Jour', required=True,
                       default=lambda self: fields.Date.context_today(self) + datetime.timedelta(days=1))
    slot_ids = fields.One2many('bgg.booking.wizard.slot', 'wizard_id', string='Créneaux libres')
    slots_searched = fields.Boolean()

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
        self.partner_name = partner.name
        self.email = partner.email
        self.street = partner.street
        self.zip = partner.zip
        self.city = partner.city
        self.country_id = partner.country_id or self.country_id

    @api.onchange('type_id', 'date')
    def _onchange_slot_criteria(self):
        self.slot_ids = [Command.clear()]
        self.slots_searched = False

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

    def _booking_tz(self):
        return pytz.timezone(self.type_id.resource_calendar_id.tz or self.env.user.tz or BGG_TZ)

    def _available_slots(self):
        """[(start (UTC, naive), combination)] free on the chosen day."""
        self.ensure_one()
        tz = self._booking_tz()
        day_start = tz.localize(datetime.datetime.combine(self.date, datetime.time.min))
        day_end = day_start + datetime.timedelta(days=1)
        Booking = self.env['resource.booking']
        slots = []
        for combination in self.type_id._get_combinations_priorized():
            booking = Booking.new({
                'type_id': self.type_id.id,
                'combination_id': combination.id,
                'combination_auto_assign': False,
                'duration': self.type_id.duration,
            })
            for starts in booking._get_available_slots(day_start, day_end).values():
                for start in starts:
                    if start < day_end:
                        slots.append((start.astimezone(pytz.utc).replace(tzinfo=None), combination))
        return sorted(slots, key=lambda slot: (slot[0], slot[1].id))

    def action_search_slots(self):
        self.ensure_one()
        self.slot_ids = [Command.clear()] + [
            Command.create({'start': start, 'combination_id': combination.id})
            for start, combination in self._available_slots()]
        self.slots_searched = True
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'name': self.env._('Prise de RDV'),
        }

    def _get_or_create_partner(self):
        """The client of the booking. Created / completed in sudo, as
        Appointments did: the call centre books without contact rights."""
        self.ensure_one()
        partner = self.partner_id.sudo()
        if not partner:
            if not self.partner_name:
                raise UserError(self.env._("Indiquez le nom du client."))
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

    def _book(self, slot):
        self.ensure_one()
        partner = self._get_or_create_partner()
        booking = self.env['resource.booking'].create({
            'type_id': self.type_id.id,
            'partner_ids': [Command.set(partner.ids)],
            'combination_auto_assign': False,
            'combination_id': slot.combination_id.id,
            'start': slot.start,
            'description': self.note and f'<p>{self.note}</p>',
            'x_street': self.street,
            'x_zip': self.zip,
            'x_city': self.city,
            'x_country_id': self.country_id.id,
            'x_need_ids': [Command.set(self.need_ids.ids)],
            'x_spouse_name': self.spouse_name,
            'x_spouse_phone': self.spouse_phone,
            'x_sms_confirmation': self.sms_confirmation,
            'x_on_behalf_id': self.on_behalf_id.id,
        })
        return booking


class BggBookingWizardSlot(models.TransientModel):
    _name = 'bgg.booking.wizard.slot'
    _description = 'Créneau libre (prise de RDV)'
    _order = 'start, id'

    wizard_id = fields.Many2one('bgg.booking.wizard', required=True, ondelete='cascade')
    start = fields.Datetime(string='Heure', required=True)
    combination_id = fields.Many2one('resource.booking.combination', string='Commercial', required=True)

    def action_book(self):
        self.ensure_one()
        booking = self.wizard_id._book(self)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'calendar.event',
            'res_id': booking.meeting_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
