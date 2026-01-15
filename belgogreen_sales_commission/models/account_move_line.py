# -*- coding: utf-8 -*-

import logging
from odoo import models, api

_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def reconcile(self):
        """Override reconcile to trigger commission payment marking"""
        # Track vendor bills before reconciliation
        vendor_bills_before = {}
        for line in self:
            if line.move_id.move_type == 'in_invoice' and line.move_id.invoice_origin:
                vendor_bills_before[line.move_id.id] = {
                    'move': line.move_id,
                    'payment_state_before': line.move_id.payment_state,
                }
                _logger.info(
                    "Commission Payment: [RECONCILE BEFORE] Bill %s - payment_state: %s",
                    line.move_id.name, line.move_id.payment_state
                )

        # Perform reconciliation
        result = super(AccountMoveLine, self).reconcile()

        # Check vendor bills after reconciliation
        for bill_id, bill_data in vendor_bills_before.items():
            bill = bill_data['move']
            previous_state = bill_data['payment_state_before']

            # Refresh from database to get updated payment_state
            bill.invalidate_recordset(['payment_state'])
            current_state = bill.payment_state

            _logger.info(
                "Commission Payment: [RECONCILE AFTER] Bill %s - Previous: %s, Current: %s",
                bill.name, previous_state, current_state
            )

            # Check if payment state changed to paid
            if previous_state not in ['paid', 'in_payment'] and current_state in ['paid', 'in_payment']:
                _logger.info(
                    "Commission Payment: ✅ Reconciliation changed payment state! Triggering _mark_commissions_paid for %s",
                    bill.name
                )
                bill._mark_commissions_paid()

        return result
