# -*- coding: utf-8 -*-

from odoo import api, models


class DmsAccessGroup(models.Model):
    _inherit = 'dms.access.group'

    @api.depends(
        'group_ids.user_ids',
        'group_ids.all_implied_by_ids.user_ids',
        'group_ids.user_ids.active',
        'explicit_user_ids',
        'parent_group_id.users',
    )
    def _compute_users(self):
        """Members of the Odoo groups, including the users who get them
        through another group (all_user_ids), not only the direct ones."""
        for record in self:
            users = (
                record.group_ids.all_user_ids
                | record.explicit_user_ids
                | record.parent_group_id.users
            )
            record.update({'users': users, 'count_users': len(users)})

    @api.model
    def _bgg_refresh_users(self):
        """Recompute the members of the access groups given Odoo groups."""
        groups = self.sudo().with_context(active_test=False).search([])
        groups._compute_users()
        groups.flush_recordset(['users', 'count_users'])
