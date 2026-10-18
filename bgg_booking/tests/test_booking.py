# -*- coding: utf-8 -*-

import datetime

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase

# A Monday far enough in the future: no booking deadline involved.
DAY = datetime.date(2027, 3, 1)


@tagged('post_install', '-at_install')
class TestCallCenterBooking(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        # Mondays 9:00-12:00 (Brussels: UTC+1 in March), 1 h RDVs every hour
        cls.calendar = env['resource.calendar'].create({
            'name': 'Commerciaux (test)', 'tz': 'Europe/Brussels',
            'attendance_ids': [Command.create({'name': 'Lundi', 'dayofweek': '0', 'hour_from': 9,
                                               'hour_to': 12, 'day_period': 'morning'})],
        })
        base = env.ref('base.group_user')
        cls.commercial = env['res.users'].create({
            'name': 'Karim Commercial', 'login': 'karim_booking', 'email': 'karim@example.com',
            'group_ids': [Command.set([base.id])],
        })
        cls.call_center = env['res.users'].create({
            'name': 'Agent Call Center', 'login': 'agent_booking', 'email': 'agent@example.com',
            'tz': 'Europe/Brussels',
            'group_ids': [Command.set([base.id, env.ref('bgg_booking.group_booking_agent').id])],
        })
        resource = env['resource.resource'].create({
            'name': cls.commercial.name, 'resource_type': 'user', 'user_id': cls.commercial.id,
            'calendar_id': cls.calendar.id, 'tz': 'Europe/Brussels',
        })
        cls.combination = env['resource.booking.combination'].create({'resource_ids': [Command.set(resource.ids)]})
        RdvType = env['bgg.rdv.type']
        cls.rdv_type = RdvType.search([('code', '=', 'APT-ENERG-CNT')]) or RdvType.create(
            {'name': 'Etude énergétique (par call center)', 'code': 'APT-ENERG-CNT'})
        cls.type = env['resource.booking.type'].create({
            'name': 'Etude énergétique (call center)', 'resource_calendar_id': cls.calendar.id,
            'duration': 1.0, 'slot_duration': 1.0, 'x_rdv_type_id': cls.rdv_type.id,
            'combination_rel_ids': [Command.create({'combination_id': cls.combination.id})],
        })
        cls.panels = env['bgg.rdv.need'].create({'name': 'Panneaux'})
        cls.battery = env['bgg.rdv.need'].create({'name': 'Batterie'})
        cc_tag = (env['res.partner.category'].search([('name', '=', 'Call Center')], limit=1)
                  or env['res.partner.category'].create({'name': 'Call Center'}))
        cls.agency = env['res.partner'].create({'name': 'Agence Partenaire', 'category_id': [Command.set(cc_tag.ids)]})
        cls.client = env['res.partner'].create({'name': 'Marie Dupont', 'phone': '+32 470 12 34 56'})

    def _wizard(self, **values):
        form = Form(self.env['bgg.booking.wizard'].with_user(self.call_center))
        for name, value in values.items():
            setattr(form, name, value)
        return form.save()

    def _slots_local(self, wizard):
        return [(s.start + datetime.timedelta(hours=1)).strftime('%H:%M') for s in wizard.slot_ids]

    def test_book_existing_client(self):
        wizard = self._wizard(phone='0470/123456', type_id=self.type, date=DAY, zip='1000', street='Rue Neuve 1',
                              city='Bruxelles', sms_confirmation=True, spouse_name='Paul Dupont',
                              spouse_phone='0470 99 88 77', on_behalf_id=self.agency)
        self.assertEqual(wizard.partner_id, self.client, "client found by the last digits of the phone")
        wizard.need_ids = self.panels | self.battery
        wizard.action_search_slots()
        self.assertEqual(self._slots_local(wizard), ['09:00', '10:00', '11:00'])
        self.assertEqual(wizard.slot_ids.combination_id, self.combination)

        action = wizard.slot_ids[1].action_book()
        meeting = self.env['calendar.event'].browse(action['res_id'])
        booking = meeting.resource_booking_ids
        self.assertEqual(booking.create_uid, self.call_center)
        self.assertEqual(meeting.user_id, self.commercial, "organizer = booked commercial, as with Appointments")
        self.assertIn(self.commercial.partner_id, meeting.partner_ids)
        self.assertIn(self.client, meeting.partner_ids)
        self.assertEqual((meeting.x_rdv_type_id, meeting.x_rdv_status), (self.rdv_type, 'booked'))
        self.assertEqual(meeting.x_appointment_ref, 'APT-ENERG-CNT')
        self.assertEqual(meeting.name, '📞 Marie Dupont/1000/+32 470 12 34 56/Panneaux+Batterie/Karim Commercial')
        self.assertEqual(meeting.x_studio_rendez_vous_pris_la_place_de, self.agency)
        self.assertIn('Besoin : Panneaux + Batterie', meeting.x_rdv_answers)
        self.assertIn('Confirmation du rendez-vous par SMS : Oui', meeting.x_rdv_answers)
        self.assertIn('Rue Neuve 1', meeting.x_studio_customer_address or '')
        # the client and the spouse contact
        self.assertEqual((self.client.street, self.client.zip, self.client.city), ('Rue Neuve 1', '1000', 'Bruxelles'))
        spouse = self.client.child_ids.filtered(lambda p: p.name == 'Paul Dupont')
        self.assertEqual(spouse.phone, '0470 99 88 77')

        # the slot is taken
        wizard.action_search_slots()
        self.assertEqual(self._slots_local(wizard), ['09:00', '11:00'])

    def test_new_client(self):
        wizard = self._wizard(phone='0490 11 22 33', type_id=self.type, date=DAY)
        self.assertFalse(wizard.partner_id)
        wizard.action_search_slots()
        with self.assertRaises(UserError):
            wizard.slot_ids[0].action_book()
        wizard.partner_name = 'Nouveau Client'
        action = wizard.slot_ids[0].action_book()
        meeting = self.env['calendar.event'].browse(action['res_id'])
        client = meeting.resource_booking_ids.partner_id
        self.assertEqual((client.name, client.phone), ('Nouveau Client', '0490 11 22 33'))
        self.assertTrue(meeting.name.startswith('Nouveau Client/'))

    def test_cancel_keeps_the_rdv_and_frees_the_slot(self):
        wizard = self._wizard(phone='0470123456', type_id=self.type, date=DAY)
        wizard.action_search_slots()
        meeting = self.env['calendar.event'].browse(wizard.slot_ids[0].action_book()['res_id'])
        booking = meeting.resource_booking_ids
        booking.with_user(self.call_center).action_cancel()
        self.assertEqual(booking.state, 'canceled')
        self.assertTrue(meeting.exists(), "the RDV stays in the history")
        self.assertEqual(meeting.x_rdv_status, 'cancelled')
        wizard.action_search_slots()
        self.assertEqual(self._slots_local(wizard), ['09:00', '10:00', '11:00'])

    def test_commercial_busy_with_another_event(self):
        self.env['calendar.event'].create({
            'name': 'RDV pris hors call center', 'user_id': self.commercial.id,
            'partner_ids': [Command.set(self.commercial.partner_id.ids)],
            'start': datetime.datetime(2027, 3, 1, 9, 0), 'stop': datetime.datetime(2027, 3, 1, 10, 0),
        })
        wizard = self._wizard(phone='0470123456', type_id=self.type, date=DAY)
        wizard.action_search_slots()
        self.assertEqual(self._slots_local(wizard), ['09:00', '11:00'])

    def test_no_slot_on_a_closed_day(self):
        wizard = self._wizard(phone='0470123456', type_id=self.type, date=DAY + datetime.timedelta(days=1))
        wizard.action_search_slots()
        self.assertTrue(wizard.slots_searched)
        self.assertFalse(wizard.slot_ids)
