# Read-only audit of duplicate commissions. Run in an Odoo shell:
#   odoo shell -d <db> --no-http < scripts/check_commission_duplicates.py
# Or paste it into an open shell. Nothing is written to the database.
from collections import defaultdict

FIX_DATE = '2026-09-09 14:31:52'  # commit 2c53475 (anti-duplicate guard widened)

Commission = env['sale.commission'].sudo().with_context(active_test=False)
commissions = Commission.search([('status', '!=', 'cancelled')])

groups = defaultdict(lambda: Commission)
for c in commissions:
    groups[(c.sale_order_id.id, c.user_id.id, c.commission_type)] |= c

dups = {k: v for k, v in groups.items() if len(v) > 1}

print("Latest commission create_date in this DB: %s" % max(commissions.mapped('create_date')))
print("Non-cancelled commissions: %d | duplicate groups: %d" % (len(commissions), len(dups)))

total_excess = 0.0
post_fix = []
rows = []
for (so_id, user_id, ctype), recs in dups.items():
    recs = recs.sorted('id')
    keep, extra = recs[0], recs[1:]
    excess = sum(extra.mapped('commission_amount'))
    total_excess += excess
    is_post_fix = any(str(r.create_date) > FIX_DATE for r in extra)
    if is_post_fix:
        post_fix.append(recs)
    rows.append((recs[0].sale_order_id.name, recs[0].user_id.name, ctype, recs, excess, is_post_fix))

print("\n=== DUPLICATE GROUPS ===")
for so, user, ctype, recs, excess, is_post_fix in sorted(rows, key=lambda r: r[0] or ''):
    print("\n%s | %s | %s | excess %.2f%s" % (
        so, user, ctype, excess, "  <-- POST-FIX" if is_post_fix else ""))
    for r in recs:
        print("   %-11s id=%-5s %-10s %9.2f  plan=%s | role=%s | company=%s | created=%s | claims=%s | PO=%s" % (
            r.name, r.id, r.status, r.commission_amount,
            r.plan_id.name, r.role_id.name, r.company_id.name,
            r.create_date, r.claim_ids.ids, r.purchase_order_id.id or '-'))

print("\n=== SUMMARY ===")
print("Duplicate groups: %d" % len(dups))
print("Approx. excess amount (all but the oldest record per group): %.2f" % total_excess)
print("Groups with a record created AFTER the fix (%s): %d" % (FIX_DATE, len(post_fix)))
by_status = defaultdict(int)
for _so, _u, _t, recs, _e, _p in rows:
    for r in recs[1:]:
        by_status[r.status] += 1
print("Extra records by status: %s" % dict(by_status))
