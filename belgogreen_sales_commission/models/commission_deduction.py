# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class CommissionDeduction(models.Model):
    _name = 'commission.deduction'
    _description = 'Commission Deduction'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )

    user_id = fields.Many2one(
        'res.users',
        string='Salesperson',
        required=True,
        tracking=True,
        help='Salesperson to whom this deduction applies'
    )

    deduction_type = fields.Selection([
        ('down_payment', 'Acompte / Avance'),
        ('service_fee', 'Frais de service'),
        ('appointment', 'Planification de rendez-vous'),
        ('leads', 'Génération de prospects'),
        ('materials', 'Matériel marketing'),
        ('training', 'Formation'),
        ('other', 'Autre')
    ], string='Type', required=True, tracking=True)

    deduction_category = fields.Selection([
        ('mandatory', 'Obligatoire'),
        ('optional', 'Optionnelle'),
    ], string='Category', default='mandatory', required=True, tracking=True,
       help="Obligatoire: Appliquée automatiquement aux réclamations\nOptionnelle: Le vendeur peut choisir de l'inclure")

    amount = fields.Monetary(
        string='Amount',
        required=True,
        currency_field='currency_id',
        tracking=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )

    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.today,
        tracking=True
    )

    description = fields.Text(
        string='Description',
        required=True,
        tracking=True
    )

    reference = fields.Char(
        string='External Reference',
        help='PO number, payment reference, invoice number, etc.'
    )

    state = fields.Selection([
        ('pending', 'En attente'),
        ('applied', 'Appliquée au paiement'),
        ('waived', 'Annulée'),
        ('cancelled', 'Annulée')
    ], string='Status', default='pending', required=True, tracking=True)

    # Relations
    claim_id = fields.Many2one(
        'sale.commission.claim',
        string='Commission Claim',
        readonly=True,
        help='Claim where this deduction was applied'
    )

    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        readonly=True,
        help='Purchase order where this deduction was applied'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )

    # Waiver tracking
    waived_by = fields.Many2one(
        'res.users',
        string='Waived By',
        readonly=True,
        tracking=True
    )

    waive_reason = fields.Text(
        string='Waiver Reason',
        readonly=True
    )

    waive_date = fields.Datetime(
        string='Waived Date',
        readonly=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('commission.deduction') or _('New')
        return super(CommissionDeduction, self).create(vals_list)

    def action_waive(self):
        """Manager can waive a deduction"""
        self.ensure_one()
        return {
            'name': _('Waive Deduction'),
            'type': 'ir.actions.act_window',
            'res_model': 'commission.deduction.waive.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_deduction_id': self.id},
        }

    def action_apply_to_claim(self):
        """Mark deduction as applied"""
        self.write({'state': 'applied'})

    def action_cancel(self):
        """Cancel deduction"""
        self.ensure_one()
        if self.state == 'applied':
            raise UserError(_('Cannot cancel a deduction that has been applied to a payment.'))
        self.write({'state': 'cancelled'})

    def action_set_to_pending(self):
        """Reset to pending"""
        self.write({'state': 'pending'})

    @api.constrains('amount')
    def _check_amount(self):
        for deduction in self:
            if deduction.amount <= 0:
                raise ValidationError(_('Deduction amount must be greater than zero.'))

    def name_get(self):
        result = []
        for deduction in self:
            name = f"{deduction.name} - {deduction.user_id.name} ({deduction.amount})"
            result.append((deduction.id, name))
        return result
