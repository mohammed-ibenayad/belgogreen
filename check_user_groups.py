#!/usr/bin/env python3
"""
Quick script to check if a user has the Commission User security group.
Run this in Odoo shell or adapt for your Odoo instance.

Usage in Odoo shell:
    python3 odoo-bin shell -d <database_name> --addons-path=<addons_path>

Then run:
    exec(open('/home/user/belgogreen_sales_commission_mod/check_user_groups.py').read())
"""

# Get user login (change this to the actual user login)
user_login = input("Enter user login/email: ")

# Find the user
user = env['res.users'].search([('login', '=', user_login)], limit=1)

if not user:
    print(f"❌ User '{user_login}' not found!")
else:
    print(f"\n✅ Found user: {user.name} (ID: {user.id})")
    print(f"   Login: {user.login}")
    print(f"\n📋 Security Groups:")

    # Check for commission-related groups
    commission_user_group = env.ref('belgogreen_sales_commission.group_commission_user', raise_if_not_found=False)
    commission_manager_group = env.ref('belgogreen_sales_commission.group_commission_manager', raise_if_not_found=False)
    commission_user_only_group = env.ref('belgogreen_sales_commission.group_commission_user_only', raise_if_not_found=False)

    has_commission_user = commission_user_group and commission_user_group in user.groups_id
    has_commission_manager = commission_manager_group and commission_manager_group in user.groups_id
    has_commission_user_only = commission_user_only_group and commission_user_only_group in user.groups_id

    print(f"   {'✅' if has_commission_user else '❌'} Commission User (group_commission_user)")
    print(f"   {'✅' if has_commission_manager else '❌'} Commission Manager (group_commission_manager)")
    print(f"   {'✅' if has_commission_user_only else '❌'} Commission User Only (group_commission_user_only)")

    if not has_commission_user:
        print(f"\n⚠️  WARNING: User does NOT have 'Commission User' group!")
        print(f"   This is required to see the 'Claim Commission Payment' action.")
        print(f"\n   To fix this:")
        print(f"   1. Go to Settings → Users & Companies → Users")
        print(f"   2. Open user: {user.name}")
        print(f"   3. Go to 'Access Rights' tab")
        print(f"   4. Under 'Other', enable 'Commission User'")
        print(f"   5. Save")
    else:
        print(f"\n✅ User has the required security group!")

    print(f"\n📊 All groups for this user:")
    for group in user.groups_id:
        print(f"   - {group.full_name}")
