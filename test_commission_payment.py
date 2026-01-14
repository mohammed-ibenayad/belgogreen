#!/usr/bin/env python3
"""
Test script to debug commission payment issue for COM/00036 and BILL/2026/01/0003

This script can be run from Odoo shell to:
1. Debug why the commission wasn't automatically marked as paid
2. Manually trigger the payment marking logic
3. Analyze the current state

Usage:
    odoo shell -d your_database -c your_config.conf --shell-interface=ipython
    Then run: %run test_commission_payment.py
"""

import logging

# Set up detailed logging
logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger(__name__)

def test_commission_payment_logic():
    """Test the commission payment logic for the specific case"""

    # Commission and Bill IDs from the user's data
    COMMISSION_ID = 36
    BILL_ID = 4832
    PAYMENT_ID = 1964

    print("\n" + "=" * 80)
    print("COMMISSION PAYMENT DEBUG TEST")
    print("=" * 80)

    # Get the models
    AccountMove = env['account.move']
    Commission = env['sale.commission']
    Payment = env['account.payment']
    PurchaseOrder = env['purchase.order']

    # 1. Check Commission Status
    print("\n1. COMMISSION ANALYSIS")
    print("-" * 80)
    commission = Commission.browse(COMMISSION_ID)
    if not commission.exists():
        print(f"ERROR: Commission {COMMISSION_ID} not found!")
        return

    print(f"Commission: {commission.name} (ID: {commission.id})")
    print(f"  - Status: {commission.status}")
    print(f"  - Amount: {commission.commission_amount}")
    print(f"  - User: {commission.user_id.name}")
    print(f"  - Payment Date: {commission.payment_date}")
    print(f"  - Payment ID: {commission.payment_id.id if commission.payment_id else 'None'}")
    print(f"  - Purchase Order: {commission.purchase_order_id.name if commission.purchase_order_id else 'None'}")

    # 2. Check Vendor Bill Status
    print("\n2. VENDOR BILL ANALYSIS")
    print("-" * 80)
    bill = AccountMove.browse(BILL_ID)
    if not bill.exists():
        print(f"ERROR: Bill {BILL_ID} not found!")
        return

    print(f"Bill: {bill.name} (ID: {bill.id})")
    print(f"  - Type: {bill.move_type}")
    print(f"  - State: {bill.state}")
    print(f"  - Payment State: {bill.payment_state}")
    print(f"  - Invoice Origin: {bill.invoice_origin}")
    print(f"  - Amount Total: {bill.amount_total}")
    print(f"  - Has Reconciled Entries: {bill.has_reconciled_entries}")

    # 3. Check Purchase Order
    print("\n3. PURCHASE ORDER ANALYSIS")
    print("-" * 80)
    if bill.invoice_origin:
        po = PurchaseOrder.search([('name', '=', bill.invoice_origin)], limit=1)
        if po:
            print(f"PO: {po.name} (ID: {po.id})")
            print(f"  - Claims: {len(po.claim_ids)}")
            print(f"  - Direct Commissions: {len(po.commission_ids)}")

            all_commissions = po.claim_ids.mapped('commission_ids') | po.commission_ids
            print(f"  - Total Commissions: {len(all_commissions)}")

            for comm in all_commissions:
                print(f"    * {comm.name}: Status={comm.status}, Amount={comm.commission_amount}")
        else:
            print(f"ERROR: No PO found with name '{bill.invoice_origin}'")
    else:
        print("ERROR: Bill has no invoice_origin")

    # 4. Check Payment
    print("\n4. PAYMENT ANALYSIS")
    print("-" * 80)
    payment = Payment.browse(PAYMENT_ID)
    if payment.exists():
        print(f"Payment: {payment.name} (ID: {payment.id})")
        print(f"  - State: {payment.state}")
        print(f"  - Is Reconciled: {payment.is_reconciled}")
        print(f"  - Amount: {payment.amount}")
        print(f"  - Partner: {payment.partner_id.name}")
        print(f"  - Move: {payment.move_id.name if payment.move_id else 'None'}")
    else:
        print(f"ERROR: Payment {PAYMENT_ID} not found!")

    # 5. Check Reconciliation
    print("\n5. RECONCILIATION ANALYSIS")
    print("-" * 80)
    payable_lines = bill.line_ids.filtered(
        lambda line: line.account_id.account_type in ('liability_payable', 'asset_receivable')
    )
    print(f"Payable Lines: {len(payable_lines)}")

    if payable_lines:
        for line in payable_lines:
            print(f"  - Line {line.id}: Account={line.account_id.name}, Amount={line.debit - line.credit}")
            print(f"    Matched Debits: {len(line.matched_debit_ids)}")
            print(f"    Matched Credits: {len(line.matched_credit_ids)}")

        matched_lines = payable_lines.mapped('matched_debit_ids.debit_move_id') | \
                       payable_lines.mapped('matched_credit_ids.credit_move_id')
        print(f"  Total Matched Lines: {len(matched_lines)}")

        payment_moves = matched_lines.mapped('move_id')
        payments = Payment.search([('move_id', 'in', payment_moves.ids)])
        print(f"  Payments from Reconciliation: {len(payments)}")
        for p in payments:
            print(f"    * {p.name} (ID: {p.id}, State: {p.state})")

    # 6. Test the _mark_commissions_paid logic
    print("\n6. TESTING _mark_commissions_paid() LOGIC")
    print("-" * 80)
    print("Calling bill.action_debug_commission_payment()...")
    bill.action_debug_commission_payment()

    # 7. Ask if user wants to manually trigger payment
    print("\n7. MANUAL TRIGGER OPTIONS")
    print("-" * 80)
    print("To manually mark the commission as paid, run:")
    print(f"    bill = env['account.move'].browse({BILL_ID})")
    print("    bill._mark_commissions_paid()")
    print("\nOr use the manual action:")
    print("    bill.action_mark_commissions_paid_manually()")

    # 8. Simulate payment state change to test trigger
    print("\n8. SIMULATING PAYMENT STATE CHANGE")
    print("-" * 80)
    print("Testing if write() would trigger _mark_commissions_paid()...")

    # Check current state
    current_state = bill.payment_state
    print(f"Current payment_state: {current_state}")

    if current_state in ['paid', 'in_payment']:
        print("Bill is already marked as paid/in_payment")
        print("Manually triggering _mark_commissions_paid()...")
        try:
            bill._mark_commissions_paid()
            print("SUCCESS: _mark_commissions_paid() completed")

            # Check commission status after
            commission.invalidate_recordset()
            print(f"\nCommission status after update: {commission.status}")
            print(f"Payment date: {commission.payment_date}")
            print(f"Payment ID: {commission.payment_id.id if commission.payment_id else 'None'}")
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 80)
    print("TEST COMPLETE - Check logs above for details")
    print("=" * 80 + "\n")

# Run the test if executed in Odoo shell
if __name__ == '__main__' or 'env' in globals():
    if 'env' in globals():
        test_commission_payment_logic()
    else:
        print("This script must be run from Odoo shell where 'env' is available")
