# -*- coding: utf-8 -*-

import datetime

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestEnterpriseSync(TransactionCase):
    """The bridge keeps bgg_custom_dev's own fields in sync with Enterprise."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.atype = cls.env['appointment.type'].create({
            'name': 'Bridge Test Etude',
            'x_appointment_ref': 'APT-TEST-BRIDGE',
        })

    def _event(self, **vals):
        start = datetime.datetime(2026, 11, 2, 9, 0)
        return self.env['calendar.event'].create(dict({
            'name': 'Bridge RDV',
            'start': start,
            'stop': start + datetime.timedelta(hours=1),
        }, **vals))

    def test_appointment_type_gets_rdv_type(self):
        rdv_type = self.atype.x_rdv_type_id
        self.assertTrue(rdv_type)
        self.assertEqual(rdv_type.code, 'APT-TEST-BRIDGE')
        self.assertEqual(rdv_type.name, 'Bridge Test Etude')
        self.atype.x_appointment_ref = 'APT-TEST-BRIDGE-2'
        self.assertEqual(rdv_type.code, 'APT-TEST-BRIDGE-2')

    def test_event_type_and_status_copied(self):
        event = self._event(appointment_type_id=self.atype.id, appointment_status='booked')
        self.assertEqual(event.x_rdv_type_id, self.atype.x_rdv_type_id)
        self.assertEqual(event.x_rdv_status, 'booked')
        event.appointment_status = 'attended'
        self.assertEqual(event.x_rdv_status, 'attended')

    def test_own_status_written_back_to_enterprise(self):
        event = self._event(appointment_type_id=self.atype.id, appointment_status='no_show')
        event.x_rdv_status = 'booked'
        self.assertEqual(event.appointment_status, 'booked')

    def test_fsm_project_flagged_sss(self):
        project = self.env['project.project'].create({'name': 'Bridge SSS', 'is_fsm': True})
        self.assertTrue(project.x_is_sss_project)
        project.is_fsm = False
        self.assertFalse(project.x_is_sss_project)
