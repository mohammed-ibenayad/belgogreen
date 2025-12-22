# -*- coding: utf-8 -*-

from odoo import models, api


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _visible_menu_ids(self, debug=False):
        """Override to hide Dashboard and My Commissions menus for users without plan assignments"""
        visible = super()._visible_menu_ids(debug=debug)

        # Check if current user has any commission plan assignment
        user = self.env.user
        has_plan_assignment = self.env['sale.commission.plan.user'].search_count([
            ('user_id', '=', user.id)
        ]) > 0

        if not has_plan_assignment:
            # User has no plan assignment - hide Dashboard and My Commissions menus
            menus_to_hide = self.search([
                ('id', 'in', visible),
                '|',
                ('id', '=', self.env.ref('belgogreen_sales_commission.menu_commission_dashboard', raise_if_not_found=False).id),
                ('id', '=', self.env.ref('belgogreen_sales_commission.menu_my_commission', raise_if_not_found=False).id),
            ])

            if menus_to_hide:
                visible = [menu_id for menu_id in visible if menu_id not in menus_to_hide.ids]

        return visible
