# -*- coding: utf-8 -*-

from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestAccessGroupUsers(TransactionCase):
    """A DMS folder opened to "Internal User" is visible to the users who
    are internal through a role, not only to the direct members."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.role = env['res.groups'].create({
            'name': 'Role (test)',
            'implied_ids': [Command.set((env.ref('base.group_user') | env.ref('dms.group_dms_user')).ids)],
        })
        cls.access = env['dms.access.group'].create({
            'name': 'Tous les internes (test)', 'perm_create': True, 'perm_write': True, 'perm_unlink': True,
            'group_ids': [Command.set(env.ref('base.group_user').ids)],
        })
        storage = env['dms.storage'].create({'name': 'Test', 'save_type': 'database'})
        cls.directory = env['dms.directory'].create({
            'name': 'Projets', 'is_root_directory': True, 'storage_id': storage.id,
            'group_ids': [Command.set(cls.access.ids)],
        })

    def _user(self, login):
        return self.env['res.users'].create({'name': login, 'login': login, 'group_ids': [Command.set(self.role.ids)]})

    def test_user_internal_through_a_role(self):
        user = self._user('role_user_dms')
        self.assertNotIn(user, self.env.ref('base.group_user').user_ids, "not a direct member")
        self.assertIn(user, self.access.users)
        self.assertTrue(self.env['dms.directory'].with_user(user).search([('id', '=', self.directory.id)]))

    def test_role_removed(self):
        user = self._user('role_user_dms2')
        portal = self.env.ref('base.group_portal')
        user.write({'group_ids': [Command.set(portal.ids)]})
        self.assertNotIn(user, self.access.users)

    def test_role_given_later(self):
        other = self.env['res.groups'].create({'name': 'Autre (test)'})
        user = self.env['res.users'].create({'name': 'later', 'login': 'later_dms',
                                             'group_ids': [Command.set(self.env.ref('base.group_portal').ids)]})
        self.assertNotIn(user, self.access.users)
        other.write({'implied_ids': [Command.set(self.role.ids)]})
        user.write({'group_ids': [Command.set(other.ids)]})
        self.assertIn(user, self.access.users)
