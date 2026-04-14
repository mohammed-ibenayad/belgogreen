# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # Deprecated - kept for backwards compatibility, use claim_ids instead
    commission_claim_id = fields.Many2one(
        'sale.commission.claim',
        string='Commission Claim',
        readonly=True,
        compute='_compute_commission_claim_id',
        store=True,
        help='Commission claim that generated this purchase order (deprecated, use claim_ids)'
    )

    claim_ids = fields.One2many(
        'sale.commission.claim',
        'purchase_order_id',
        string='Commission Claims',
        readonly=True,
        help='Commission claims associated with this purchase order'
    )

    commission_ids = fields.Many2many(
        'sale.commission',
        'purchase_order_commission_rel',
        'purchase_order_id',
        'commission_id',
        string='Direct Commissions',
        readonly=True,
        help='Commissions paid directly via this PO (without claims)'
    )

    @api.depends('claim_ids')
    def _compute_commission_claim_id(self):
        """Compute single claim for backwards compatibility"""
        for po in self:
            claims = po.sudo().claim_ids
            po.commission_claim_id = claims[0] if claims else False

    # Fields that can be safely modified on commission PO lines
    # without affecting commission amounts
    _COMMISSION_LINE_ALLOWED_FIELDS = {
        'taxes_id', 'tax_ids',          # VAT / tax correction
        'name',                          # Description
        'date_planned',                  # Scheduled date
        'analytic_distribution',         # Cost center / analytic accounting
    }

    def write(self, vals):
        """Protect commission PO lines from amount changes, but allow safe edits"""
        for po in self:
            if po.sudo().claim_ids and po.state == 'draft' and 'order_line' in vals:
                deduction_product = self.env.ref(
                    'belgogreen_sales_commission.product_commission_deduction',
                    raise_if_not_found=False
                )
                for line_op in vals.get('order_line', []):
                    if not isinstance(line_op, (list, tuple)) or len(line_op) == 0:
                        continue
                    # Allow delete operations (for deduction lines)
                    if line_op[0] in (2, 3):
                        continue
                    # Block adding new lines
                    if line_op[0] == 0:
                        raise UserError(_(
                            'Impossible d\'ajouter de nouvelles lignes aux bons de commande de commission.\n\n'
                            'Pour modifier :\n'
                            '1. Annulez ce bon de commande\n'
                            '2. Ajustez les déductions de la réclamation\n'
                            '3. Recréez l\'approbation de la réclamation'
                        ))
                    # Update operation — check what's being changed
                    if line_op[0] == 1:
                        line = self.env['purchase.order.line'].browse(line_op[1])
                        # Allow all modifications on deduction lines
                        if deduction_product and line.product_id == deduction_product:
                            continue
                        # On commission lines, only allow safe field changes
                        changed_fields = set(line_op[2].keys()) if line_op[2] else set()
                        blocked_fields = changed_fields - self._COMMISSION_LINE_ALLOWED_FIELDS
                        if blocked_fields:
                            raise UserError(_(
                                'Impossible de modifier les montants de commission.\n\n'
                                'Vous pouvez modifier : les taxes, la description, la date et la distribution analytique.\n'
                                'Pour modifier les montants de commission :\n'
                                '1. Annulez ce bon de commande\n'
                                '2. Ajustez les déductions de la réclamation\n'
                                '3. Recréez l\'approbation de la réclamation'
                            ))
        return super(PurchaseOrder, self).write(vals)

    def button_confirm(self):
        """Override to update commission status when PO is confirmed"""
        res = super(PurchaseOrder, self).button_confirm()

        for po in self:
            po_sudo = po.sudo()
            # Handle claim-based commissions
            if po_sudo.claim_ids:
                # Get all commissions from all claims
                all_commissions = po_sudo.claim_ids.mapped('commission_ids')
                # Update commission status to processing
                all_commissions.write({'status': 'processing'})

            # Handle direct commissions (no claims)
            if po_sudo.commission_ids:
                # Already in processing status from action_create_po_from_commissions
                # Just ensure consistency
                po_sudo.commission_ids.filtered(lambda c: c.status != 'processing').write({'status': 'processing'})

        return res

    def button_cancel(self):
        """Override to handle claim cancellation and reset deductions"""
        # Store claims and direct commissions before cancellation
        claims_to_reset = {}
        direct_commissions_to_reset = {}

        for po in self:
            po_sudo = po.sudo()
            # Handle claim-based commissions
            if po_sudo.claim_ids:
                # Store claims and their deductions
                claims_to_reset[po.id] = {
                    'claims': po_sudo.claim_ids,
                    'deductions': po_sudo.claim_ids.mapped('all_deduction_ids').filtered(
                        lambda d: d.state == 'applied' and d.purchase_order_id == po
                    )
                }

            # Handle direct commissions (no claims)
            if po_sudo.commission_ids:
                direct_commissions_to_reset[po.id] = po_sudo.commission_ids

        res = super(PurchaseOrder, self).button_cancel()

        # Reset claims and deductions after cancellation
        for po in self:
            if po.id in claims_to_reset:
                data = claims_to_reset[po.id]

                # Reset deductions to pending
                if data['deductions']:
                    data['deductions'].write({
                        'state': 'pending',
                        'claim_id': False,
                        'purchase_order_id': False
                    })

                # Reset claims to pending state
                data['claims'].write({
                    'state': 'pending',
                    'purchase_order_id': False,
                    'processed_by': False,
                    'processed_date': False
                })

                # Notify manager
                for claim in data['claims']:
                    claim.message_post(
                        body=_('Le bon de commande %s a été annulé. La réclamation et les déductions ont été réinitialisées en attente.') % po.name,
                        subject=_('BC annulé - Réclamation réinitialisée'),
                    )

            # Reset direct commissions to unpaid
            if po.id in direct_commissions_to_reset:
                commissions = direct_commissions_to_reset[po.id]
                commissions.write({'status': 'unpaid'})

                # Log message on first commission
                if commissions:
                    commissions[0].message_post(
                        body=_('Le bon de commande %s a été annulé. %s commission(s) réinitialisée(s) à non payée.') % (po.name, len(commissions)),
                        subject=_('BC annulé - Commissions réinitialisées'),
                    )

        return res


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def unlink(self):
        """Override to reset deductions to pending when deduction lines are removed from PO"""
        # Get the commission deduction product
        deduction_product = self.env.ref('belgogreen_sales_commission.product_commission_deduction', raise_if_not_found=False)

        if deduction_product:
            # Find deduction lines being deleted
            deduction_lines = self.filtered(lambda line: line.product_id == deduction_product)

            for line in deduction_lines:
                # Find the corresponding deduction by searching for deductions linked to this PO
                # and matching the amount (negative in PO line)
                deductions = self.env['commission.deduction'].sudo().search([
                    ('purchase_order_id', '=', line.order_id.id),
                    ('amount', '=', -line.price_unit),  # Deduction amount is negative in PO
                    ('state', '=', 'applied')
                ])

                # If multiple matches, try to match by name in the line description
                if len(deductions) > 1:
                    for deduction in deductions:
                        if deduction.name in line.name:
                            deductions = deduction
                            break

                # Reset deduction(s) to pending
                if deductions:
                    deductions.sudo().write({
                        'state': 'pending',
                        'claim_id': False,
                        'purchase_order_id': False
                    })

                    # Log message
                    for deduction in deductions:
                        deduction.sudo().message_post(
                            body=_('Déduction retirée du bon de commande %s. Statut réinitialisé en attente.') % line.order_id.name,
                            subject=_('Déduction retirée du BC'),
                        )

        return super(PurchaseOrderLine, self).unlink()
