# -*- coding: utf-8 -*-

import datetime

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase

from odoo.addons.bgg_booking.hooks import BOOKING_CALENDAR_NAME, setup_booking_types

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
        Need = env['bgg.rdv.need']
        cls.panel, cls.battery, cls.insulation = (Need.create({'name': n}) for n in ('Panneau', 'Batterie', 'Isolation'))
        RdvType = env['bgg.rdv.type']

        def booking_type(code, name, **settings):
            rdv_type = RdvType.search([('code', '=', code)]) or RdvType.create({'name': name, 'code': code})
            return env['resource.booking.type'].create(dict({
                'name': name, 'resource_calendar_id': cls.calendar.id,
                'duration': 1.0, 'slot_duration': 1.0, 'x_rdv_type_id': rdv_type.id,
                'combination_rel_ids': [Command.create({'combination_id': cls.combination.id})],
            }, **settings))
        cls.energy = booking_type('APT-ENERG-CNT', 'Etude énergétique', x_ask_solar_since=True, x_ask_on_behalf=True,
                                  x_need_ids=[Command.set((cls.panel | cls.battery).ids)])
        cls.isolation = booking_type('APT-NISOL-CNT', 'Etude isolation (par call center)', x_need_multiple=True,
                                     x_ask_sms_confirmation=True, x_ask_on_behalf=True,
                                     x_need_ids=[Command.set((cls.panel | cls.insulation).ids)])
        cc_tag = (env['res.partner.category'].search([('name', '=', 'Call Center')], limit=1)
                  or env['res.partner.category'].create({'name': 'Call Center'}))
        cls.agency = env['res.partner'].create({'name': 'Call Center Tunis', 'category_id': [Command.set(cc_tag.ids)]})
        cls.client = env['res.partner'].create({'name': 'Marie Dupont', 'phone': '+32 470 12 34 56'})

    def _wizard(self, booking_type=None, **values):
        values = dict({'phone': '0470123456', 'street': 'Rue Neuve 1', 'zip': '1000', 'city': 'Bruxelles',
                       'is_owner': 'yes'}, **values)
        form = Form(self.env['bgg.booking.wizard'].with_user(self.call_center))
        form.type_id = booking_type or self.energy
        form.date = DAY
        for name, value in values.items():
            setattr(form, name, value)
        return form.save()

    def _slots_local(self, wizard):
        return [(s.start + datetime.timedelta(hours=1)).strftime('%H:%M') for s in wizard.slot_ids]

    def _book(self, wizard, index=0):
        wizard.action_search_slots()
        return self.env['calendar.event'].browse(wizard.slot_ids[index].action_book()['res_id'])

    def test_book_energy_study_existing_client(self):
        wizard = self._wizard(phone='0470/123456', solar_since='3 ans', spouse_name='Paul Dupont',
                              spouse_phone='0470 99 88 77', on_behalf_id=self.agency, comments='Rappeler le soir')
        self.assertEqual(wizard.partner_id, self.client, "client found by the last digits of the phone")
        wizard.need_ids = self.panel
        wizard.action_search_slots()
        self.assertEqual(self._slots_local(wizard), ['09:00', '10:00', '11:00'])
        self.assertEqual(wizard.slot_ids.combination_id, self.combination)

        meeting = self.env['calendar.event'].browse(wizard.slot_ids[1].action_book()['res_id'])
        booking = meeting.resource_booking_ids
        self.assertEqual(booking.create_uid, self.call_center)
        self.assertEqual(meeting.user_id, self.commercial, "organizer = booked commercial, as with Appointments")
        self.assertIn(self.commercial.partner_id, meeting.partner_ids)
        self.assertIn(self.client, meeting.partner_ids)
        self.assertEqual((meeting.x_rdv_type_id, meeting.x_rdv_status), (self.energy.x_rdv_type_id, 'booked'))
        self.assertEqual(meeting.x_appointment_ref, 'APT-ENERG-CNT')
        self.assertEqual(meeting.name, 'Marie Dupont/1000/+32 470 12 34 56/Panneau/Karim Commercial')
        self.assertEqual(meeting.x_studio_rendez_vous_pris_la_place_de, self.agency)
        self.assertEqual(meeting.x_rdv_answers.splitlines(), [
            'Adresse : Rue Neuve 1', 'Code Postale : 1000', 'Ville : Bruxelles', 'Pays : Belgium',
            'Depuis combien de temps les clients ont-ils des panneaux solaires ? : 3 ans',
            'Les clients sont-ils bien les propriétaires du bien ? : Oui',
            'Nom du conjoint : Paul Dupont', 'Numéro de téléphone du conjoint : 0470 99 88 77',
            'Besoin : Panneau', 'Commentaires : Rappeler le soir',
            'Rendez-vous pris à la place de : Call Center Tunis'])
        self.assertIn('Rue Neuve 1', meeting.x_studio_customer_address or '')
        # the client and the spouse contact
        self.assertEqual((self.client.street, self.client.zip, self.client.city), ('Rue Neuve 1', '1000', 'Bruxelles'))
        self.assertEqual(self.client.child_ids.filtered(lambda p: p.name == 'Paul Dupont').phone, '0470 99 88 77')
        # the opportunity: the sale order finds the RDV through it
        lead = meeting.opportunity_id
        self.assertEqual((lead.type, lead.partner_id, lead.user_id), ('opportunity', self.client, self.commercial))
        order = self.env['sale.order'].create({'partner_id': self.client.id, 'opportunity_id': lead.id})
        self.assertEqual(order.x_studio_organisateur_du_rendez_vous, self.call_center)
        self.assertEqual(order.x_studio_rendez_vous_pris_la_place_de, self.agency)
        # the slot is taken
        wizard.action_search_slots()
        self.assertEqual(self._slots_local(wizard), ['09:00', '11:00'])

    def test_isolation_study_several_needs_and_sms(self):
        wizard = self._wizard(self.isolation, sms_confirmation=True)
        wizard.need_ids = self.panel | self.insulation
        meeting = self._book(wizard)
        self.assertEqual(meeting.name, '📞 Marie Dupont/1000/+32 470 12 34 56/Panneau+Isolation/Karim Commercial')
        self.assertIn('Confirmation du rendez-vous par SMS : Oui', meeting.x_rdv_answers)
        self.assertNotIn('panneaux solaires', meeting.x_rdv_answers)

    def test_questionnaire_checks(self):
        wizard = self._wizard(street=False, is_owner=False)
        wizard.action_search_slots()
        with self.assertRaisesRegex(UserError, 'Adresse(.|\n)*propriétaires(.|\n)*Besoin(.|\n)*panneaux solaires'):
            wizard.slot_ids[0].action_book()
        wizard.write({'street': 'Rue Neuve 1', 'is_owner': 'no', 'solar_since': '2 ans',
                      'need_ids': [Command.set((self.panel | self.battery).ids)]})
        with self.assertRaisesRegex(UserError, 'Un seul besoin'):
            wizard.slot_ids[0].action_book()

    def test_new_client(self):
        wizard = self._wizard(phone='0490 11 22 33', solar_since='1 an')
        wizard.need_ids = self.battery
        self.assertFalse(wizard.partner_id)
        wizard.action_search_slots()
        with self.assertRaisesRegex(UserError, 'Nom du client'):
            wizard.slot_ids[0].action_book()
        wizard.partner_name = 'Nouveau Client'
        meeting = self.env['calendar.event'].browse(wizard.slot_ids[0].action_book()['res_id'])
        client = meeting.resource_booking_ids.partner_id
        self.assertEqual((client.name, client.phone, client.street), ('Nouveau Client', '0490 11 22 33', 'Rue Neuve 1'))
        self.assertTrue(meeting.name.startswith('Nouveau Client/1000/'))

    def test_cancel_keeps_the_rdv_and_frees_the_slot(self):
        wizard = self._wizard(solar_since='1 an')
        wizard.need_ids = self.panel
        meeting = self._book(wizard)
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
        wizard = self._wizard()
        wizard.action_search_slots()
        self.assertEqual(self._slots_local(wizard), ['09:00', '11:00'])

    def test_no_slot_on_a_closed_day(self):
        wizard = self._wizard(date=DAY + datetime.timedelta(days=1))
        wizard.action_search_slots()
        self.assertTrue(wizard.slots_searched)
        self.assertFalse(wizard.slot_ids)


@tagged('post_install', '-at_install')
class TestBookingSetup(TransactionCase):
    """At installation, the study booking types are built from the RDV types
    and their commercials (copied from Appointments)."""

    def test_setup_from_rdv_types(self):
        commercial = self.env['res.users'].create({'name': 'Commercial Isolation', 'login': 'iso_setup'})
        RdvType = self.env['bgg.rdv.type']
        rdv_type = RdvType.search([('code', '=', 'APT-NISOL-COM')]) or RdvType.create(
            {'name': 'Etude isolation (par commercial)', 'code': 'APT-NISOL-COM'})
        rdv_type.user_ids = commercial
        self.env['resource.booking.type'].search([('x_rdv_type_id', '=', rdv_type.id)]).unlink()

        setup_booking_types(self.env)
        btype = self.env['resource.booking.type'].search([('x_rdv_type_id', '=', rdv_type.id)])
        self.assertEqual(len(btype), 1)
        self.assertEqual((btype.duration, btype.slot_duration), (2.0, 2.0))
        self.assertEqual(btype.resource_calendar_id.name, BOOKING_CALENDAR_NAME)
        self.assertEqual(sorted({a.dayofweek for a in btype.resource_calendar_id.attendance_ids}),
                         ['0', '1', '2', '3', '4', '5'])
        self.assertCountEqual(btype.x_need_ids.mapped('name'), ['Panneau', 'Batterie', 'Boileur', 'Pompe à chaleur', 'Ballon'])
        self.assertTrue(btype.x_need_multiple and btype.x_ask_sms_confirmation and btype.x_create_opportunity)
        self.assertFalse(btype.x_ask_on_behalf or btype.x_ask_solar_since)
        self.assertEqual(btype.combination_rel_ids.combination_id.resource_ids.user_id, commercial)

        setup_booking_types(self.env)
        self.assertEqual(self.env['resource.booking.type'].search_count([('x_rdv_type_id', '=', rdv_type.id)]), 1)
