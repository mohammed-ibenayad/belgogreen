# Commission Payment Logic - Debugging Guide

## Overview

This document explains the commission payment mechanism and how to debug issues where commissions are not automatically marked as "paid" when the vendor bill is paid.

## How It Should Work

### 1. **Commission Generation** (Client Payment Check)
- **Trigger**: When `sale_order._generate_commissions()` is called
- **Check**: Customer invoice `payment_state` in `['paid', 'in_payment']`
- **Result**: Creates commission records with `status='unpaid'`
- **File**: `belgogreen_sales_commission/models/sale_order.py:98-107`

### 2. **Commission Payment** (Vendor Payment Check)
- **Trigger**: When vendor bill `payment_state` changes to `'paid'` or `'in_payment'`
- **Check**: `account_move.write()` detects payment state change
- **Result**: Updates commission `status='paid'` with payment details
- **File**: `belgogreen_sales_commission/models/account_move.py:30-78`

## The Bug Scenario

**Commission ID 36 (COM/00036)** should be marked as "paid" because:
- ✅ Vendor bill (BILL/2026/01/0003) has `payment_state = "paid"`
- ✅ Vendor bill is reconciled (`has_reconciled_entries = true`)
- ✅ Commission is linked to Purchase Order P00004
- ❌ **BUT** commission is stuck in `status = "processing"`

## Root Cause Identified ✅

**THE BUG**: The `payment_state` field on `account.move` is a **computed field** that gets recalculated based on reconciliation. When a payment is registered and reconciled:

1. Odoo calls `write()` with reconciliation data
2. `payment_state` is **NOT** in the `vals` dict (it's computed, not written)
3. The original code only tracked moves when `'line_ids' in vals or 'payment_state' in vals`
4. `previous_states` dict remained empty
5. Payment state changed from `not_paid` → `paid` **BUT** our hook didn't detect it
6. `_mark_commissions_paid()` was never triggered ❌

**Evidence from logs**:
```
Commission Payment: Move BILL/2026/01/0012 - Previous: N/A, Current: paid, Changed: False
```
- `Previous: N/A` = The bill wasn't tracked
- `Current: paid` = Bill is now paid
- `Changed: False` = Logic failed to detect the change

### The Fix

Changed the tracking logic to **always monitor vendor bills** regardless of what's in `vals`:

```python
# OLD (BUGGY):
if 'line_ids' in vals or 'payment_state' in vals:
    for move in self:
        previous_states[move.id] = move.payment_state

# NEW (FIXED):
for move in self:
    if move.move_type == 'in_invoice':  # Always track vendor bills
        previous_states[move.id] = move.payment_state
```

This ensures we catch computed field changes during reconciliation.

## Debugging Tools Added

### 1. **Comprehensive Logging**

We've added detailed logging at every step:

```python
# In account_move.py
_logger.info("Commission Payment: [message]")
```

**What gets logged:**
- ✅ When `write()` is called with payment state changes
- ✅ Previous and current payment states
- ✅ Whether `_mark_commissions_paid()` is triggered
- ✅ PO search results
- ✅ Commissions found
- ✅ Payments found and their states
- ✅ Commission update operations

**View logs:**
```bash
# Follow the Odoo log file
tail -f /var/log/odoo/odoo-server.log | grep "Commission Payment"
```

### 2. **Debug Action**

Added `action_debug_commission_payment()` method:

**Use in Odoo Shell:**
```python
bill = env['account.move'].browse(4832)  # BILL/2026/01/0003
bill.action_debug_commission_payment()
```

**What it does:**
- Analyzes bill, PO, commissions, and payments
- Logs complete state to server logs
- Shows notification to check logs

### 3. **Test Script**

Run the comprehensive test script:

```bash
# From Odoo shell
odoo shell -d your_database -c /etc/odoo/odoo.conf

# Then in the shell
%run /home/user/belgogreen_sales_commission_mod/test_commission_payment.py
```

**The script will:**
1. Analyze commission COM/00036
2. Analyze vendor bill BILL/2026/01/0003
3. Check purchase order P00004
4. Analyze payment reconciliation
5. Test the `_mark_commissions_paid()` logic
6. Provide manual trigger options

## How to Fix the Specific Issue

### Option 1: Manual Trigger via Odoo Shell

```python
# Connect to Odoo shell
odoo shell -d your_database -c /etc/odoo/odoo.conf

# In the shell
bill = env['account.move'].browse(4832)
bill._mark_commissions_paid()
env.cr.commit()

# Verify
commission = env['sale.commission'].browse(36)
print(f"Status: {commission.status}")
print(f"Payment Date: {commission.payment_date}")
print(f"Payment ID: {commission.payment_id.id if commission.payment_id else 'None'}")
```

### Option 2: Manual Action from UI

We've updated the manual action to support direct commissions:

1. Open the vendor bill BILL/2026/01/0003
2. Find the "Mark Commissions Paid" button (if available in UI)
3. Click it to manually trigger the payment logic

### Option 3: Trigger Write Hook

```python
# Force a write operation that triggers the hook
bill = env['account.move'].browse(4832)
bill.write({'payment_state': bill.payment_state})  # Write same value
env.cr.commit()
```

## Investigating the Root Cause

### Step 1: Check if write() was ever called

Search logs for:
```bash
grep "Commission Payment: Move BILL/2026/01/0003" /var/log/odoo/odoo-server.log
```

**If found**: The write hook was triggered, proceed to Step 2
**If not found**: The write hook never triggered (this is the bug)

### Step 2: Check if _mark_commissions_paid() was called

Search logs for:
```bash
grep "Commission Payment: _mark_commissions_paid called for bill BILL/2026/01/0003" /var/log/odoo/odoo-server.log
```

**If found**: The method was called, check for subsequent errors
**If not found**: The condition check in `write()` prevented it from running

### Step 3: Check for errors

Search for:
```bash
grep -A 10 "Commission Payment.*BILL/2026/01/0003" /var/log/odoo/odoo-server.log | grep -i error
```

### Step 4: Analyze payment state transitions

Check what payment states were involved:
```bash
grep "Commission Payment.*4832" /var/log/odoo/odoo-server.log
```

Look for lines showing:
- `Previous: X, Current: Y, Changed: True/False`

## Expected Log Output (When Working)

```
INFO Commission Payment: Tracking move BILL/2026/01/0003 (Type: in_invoice, Previous state: not_paid)
INFO Commission Payment: Move BILL/2026/01/0003 - Type: in_invoice, Previous: not_paid, Current: paid, Changed: True, Invoice Origin: P00004
INFO Commission Payment: Triggering _mark_commissions_paid for vendor bill BILL/2026/01/0003 (Origin: P00004)
INFO Commission Payment: _mark_commissions_paid called for bill BILL/2026/01/0003 (ID: 4832)
INFO Commission Payment: Searching for PO with name 'P00004'
INFO Commission Payment: Found PO P00004 (ID: 4), Claims: 0, Direct Commissions: 1
INFO Commission Payment: Found 1 payable/receivable line(s) for bill BILL/2026/01/0003
INFO Commission Payment: Found 2 matched line(s) from reconciliation
INFO Commission Payment: Found 1 payment(s): PBNK1/2026/00005 (States: in_process)
INFO Commission Payment: Found 1 commission(s) to mark as paid: COM/00036
INFO Commission Payment: Commission COM/00036 (ID: 36) - Current status: processing, Amount: 1255, User: Ahmed Aden
INFO Commission Payment: Updating commissions to paid - Payment ID: 1964, Payment Date: 2026-01-11
INFO Commission Payment: Successfully updated 1 commission(s) to paid status
```

## Key Differences: Paid vs In Payment

The system accepts both `'paid'` and `'in_payment'` states:

- **`'paid'`**: Invoice is fully paid and reconciled
- **`'in_payment'`**: Payment is in progress (e.g., bank transfer pending)

Both should trigger commission payment marking because the company has initiated payment to the employee.

## Account Payment State: Does it Matter?

**Current observation**: The `account.payment` record has `state='in_process'`

**Analysis**:
- The payment state on the **move** (bill) is what matters for the trigger
- The payment **record** state can be different:
  - `'draft'`: Not yet confirmed
  - `'in_process'`: Being processed (electronic payment pending)
  - `'posted'`: Move is posted and reconciled
  - `'sent'`: Sent to bank/processor
  - `'reconciled'`: Deprecated, check `is_reconciled` field

**Verdict**: The payment record being "in_process" **should not block** commission payment marking. The bill's `payment_state='paid'` and `has_reconciled_entries=true` are sufficient.

## Next Steps

1. **Enable logging**: The changes are in `account_move.py`
2. **Restart Odoo**: `sudo systemctl restart odoo`
3. **Test with next commission payment**: Create a new commission and pay it
4. **Monitor logs**: Watch for the "Commission Payment" log messages
5. **Analyze timing**: Check if there's a delay between payment and commission update

## Recommended Fix

Based on the investigation, we should:

1. **Add retry logic**: If the write hook fires before reconciliation is complete
2. **Add scheduled action**: Periodically check for paid bills with unpaid commissions
3. **Add validation**: On commission status transitions, verify vendor bill is actually paid

Would you like me to implement any of these fixes?

## Files Modified

1. `belgogreen_sales_commission/models/account_move.py`:
   - Added logging import
   - Added comprehensive logging to `write()` and `_mark_commissions_paid()`
   - Added `action_debug_commission_payment()` method
   - Updated `action_mark_commissions_paid_manually()` to support direct commissions

## Testing the Logging

To test the logging system:

```python
# Create a test scenario
bill = env['account.move'].browse(4832)

# Check current state
print(f"Current payment_state: {bill.payment_state}")
print(f"Commission count: {len(bill.invoice_origin and env['purchase.order'].search([('name', '=', bill.invoice_origin)]).commission_ids or [])}")

# Trigger the debug action
bill.action_debug_commission_payment()

# Check server logs
# tail -f /var/log/odoo/odoo-server.log | grep "Commission Payment"
```

## Contact

For questions or issues, check the project repository or contact the development team.
