# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

RESPONSABLE_DOSSIER_GROUP = 'bgg_custom_dev.group_responsable_dossier'


@tagged('post_install', '-at_install')
class TestSaleOrderResponsableDossier(TransactionCase):
    """Dossier tab on sale.order: the Responsable must be an internal user of
    the "Responsable Dossier" group.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group = cls.env.ref(RESPONSABLE_DOSSIER_GROUP)

        cls.customer = cls.env['res.partner'].create({
            'name': 'Client Dossier',
        })
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.customer.id,
        })

        cls.responsable = cls.env['res.users'].create({
            'name': 'Responsable Dossier User',
            'login': 'responsable.dossier@test.bgg',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.group.id,
            ])],
        })
        cls.internal_user = cls.env['res.users'].create({
            'name': 'Internal User',
            'login': 'internal.user@test.bgg',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        cls.portal_user = cls.env['res.users'].create({
            'name': 'Portal User',
            'login': 'portal.user@test.bgg',
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })

    def test_group_exists(self):
        self.assertEqual(self.group.name, 'Responsable Dossier')

    def test_field_definition(self):
        field = self.env['sale.order']._fields['x_responsable_dossier_id']
        self.assertEqual(field.comodel_name, 'res.users')
        self.assertEqual(field.string, 'Responsable')
        self.assertTrue(field.tracking)

    def test_domain_restricts_to_group_members(self):
        domain = self.env['sale.order']._responsable_dossier_domain()
        users = self.env['res.users'].search(domain)
        self.assertIn(self.responsable, users)
        self.assertNotIn(self.internal_user, users)
        self.assertNotIn(self.portal_user, users)

    def test_assign_group_member(self):
        self.order.x_responsable_dossier_id = self.responsable
        self.assertEqual(self.order.x_responsable_dossier_id, self.responsable)

    def test_reject_internal_user_outside_group(self):
        with self.assertRaises(ValidationError):
            self.order.x_responsable_dossier_id = self.internal_user

    def test_reject_portal_user(self):
        with self.assertRaises(ValidationError):
            self.order.x_responsable_dossier_id = self.portal_user

    def test_clearing_is_allowed(self):
        self.order.x_responsable_dossier_id = self.responsable
        self.order.x_responsable_dossier_id = False
        self.assertFalse(self.order.x_responsable_dossier_id)

    def _flush_tracking(self):
        """Run the precommit hooks that write mail tracking values."""
        self.env.flush_all()
        self.env.cr.precommit.run()

    def test_assignment_is_tracked_in_chatter(self):
        # mail.thread disables tracking on a record for the rest of the
        # transaction that created it, until precommit runs. The order was
        # created in setUpClass, so flush once before the tracked write.
        self._flush_tracking()
        self.order.x_responsable_dossier_id = self.responsable
        self._flush_tracking()
        tracking = self.env['mail.tracking.value'].search([
            ('mail_message_id.model', '=', 'sale.order'),
            ('mail_message_id.res_id', '=', self.order.id),
            ('field_id.name', '=', 'x_responsable_dossier_id'),
        ])
        self.assertTrue(tracking)
