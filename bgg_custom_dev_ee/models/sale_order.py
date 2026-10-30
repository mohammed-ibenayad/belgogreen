# -*- coding: utf-8 -*-

from odoo import models


class SaleOrder(models.Model):
    """"Créer tâches SSS" while Field Service is installed: the SSS project
    and its tasks are also Field Service ones (as the former Studio action
    made them). Values of fields that do not exist are left out by
    bgg_custom_dev."""
    _inherit = 'sale.order'

    def _bgg_sss_default_worksheet(self):
        if 'worksheet.template' not in self.env:
            return False
        Template = self.env['worksheet.template']
        domain = [('res_model', '=', 'project.task')] if 'res_model' in Template._fields else []
        return Template.search(domain, order='id', limit=1).id

    def _bgg_sss_project_extra_vals(self):
        vals = super()._bgg_sss_project_extra_vals()
        vals.update({
            'is_fsm': True,
            'allow_material': False,
            'allow_worksheets': True,
            'allow_quotations': False,
            'billing_type': 'not_billable',
            'worksheet_template_id': self._bgg_sss_default_worksheet(),
        })
        return vals

    def _bgg_sss_task_extra_vals(self, line):
        vals = super()._bgg_sss_task_extra_vals(line)
        partner = self.partner_id
        vals.update({
            'is_fsm': True,
            'allow_timesheets': True,
            'allow_material': False,
            'allow_worksheets': True,
            'allow_billable': False,
            'allow_milestones': False,
            'allow_quotations': False,
            'allow_task_dependencies': False,
            'pricing_type': 'task_rate',
            'worksheet_template_id': self._bgg_sss_default_worksheet(),
            'timesheet_product_id': line.product_id.id,
            'partner_city': partner.city or '',
            'partner_country_id': partner.country_id.id,
            'partner_phone': partner.phone or '',
            'partner_street': partner.street or '',
            'partner_street2': partner.street2 or '',
            'partner_zip': partner.zip or '',
            'pricelist_id': self.pricelist_id.id,
            'currency_id': self.currency_id.id,
        })
        return vals
