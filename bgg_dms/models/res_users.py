# -*- coding: utf-8 -*-

from odoo import api, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        self.env['dms.access.group']._bgg_refresh_users()
        return users

    def write(self, vals):
        result = super().write(vals)
        if {'group_ids', 'active'} & set(vals):
            self.env['dms.access.group']._bgg_refresh_users()
        return result


class ResGroups(models.Model):
    _inherit = 'res.groups'

    def write(self, vals):
        result = super().write(vals)
        if {'implied_ids', 'user_ids'} & set(vals):
            self.env['dms.access.group']._bgg_refresh_users()
        return result
