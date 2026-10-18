# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AppointmentType(models.Model):
    """Each Enterprise appointment type is linked to an RDV type of
    bgg_custom_dev (same id for the types that existed at migration time)."""
    _inherit = 'appointment.type'

    x_appointment_ref = fields.Char(
        string='Appointment Reference',
        help='Business reference code for this appointment type (e.g., APT-ENERG-CNT, APT-NISOL-COM)',
        index=True,
    )
    x_rdv_type_id = fields.Many2one(
        'bgg.rdv.type',
        string='Type de RDV',
        copy=False,
        ondelete='set null',
        help='RDV type used by the BelGoGreen rules (bgg_custom_dev).',
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            record._bgg_ensure_rdv_type()
        return records

    def write(self, vals):
        result = super().write(vals)
        if {'name', 'x_appointment_ref', 'active'} & set(vals):
            for record in self:
                record._bgg_ensure_rdv_type()
        return result

    def _bgg_ensure_rdv_type(self):
        """Create or update the linked RDV type (name, code, active)."""
        self.ensure_one()
        RdvType = self.env['bgg.rdv.type'].sudo().with_context(active_test=False)
        values = {
            'name': self.name,
            'code': self.x_appointment_ref or False,
            'active': self.active,
        }
        rdv_type = self.sudo().x_rdv_type_id
        if not rdv_type and self.x_appointment_ref:
            rdv_type = RdvType.search([('code', '=', self.x_appointment_ref)], limit=1)
        if rdv_type:
            rdv_type.write({k: v for k, v in values.items() if rdv_type[k] != v})
        else:
            rdv_type = RdvType.create(values)
        if self.sudo().x_rdv_type_id != rdv_type:
            self.sudo().x_rdv_type_id = rdv_type
        return rdv_type
