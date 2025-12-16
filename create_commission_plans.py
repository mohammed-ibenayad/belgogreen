#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to create hierarchical commission plans for AMSS MANAGEMENT SRL and NATUR'ISOL SRL
Execute this script on Odoo.sh using the shell command.

Usage on Odoo.sh:
    odoo-bin shell -d <database_name> < create_commission_plans.py
"""

def create_hierarchical_commission_plans(env):
    """
    Create two hierarchical commission plans:
    1. Plan de Commission Standard - AMSS MANAGEMENT SRL
    2. Plan de Commission Standard - NaturIsol (NATUR'ISOL SRL)
    """

    print("\n" + "="*80)
    print("Starting Commission Plan Creation")
    print("="*80 + "\n")

    # ========================================================================
    # STEP 1: Find Companies
    # ========================================================================
    print("STEP 1: Finding companies...")

    # Using company IDs directly (more reliable than name search)
    company_amss = env['res.company'].browse(2)  # AMSS MANAGEMENT SRL
    if not company_amss.exists():
        print("ERROR: Company with ID 2 (AMSS MANAGEMENT SRL) not found!")
        return False
    print(f"✓ Found {company_amss.name} (ID: {company_amss.id})")

    company_naturisol = env['res.company'].browse(3)  # NATUR'ISOL SRL
    if not company_naturisol.exists():
        print("ERROR: Company with ID 3 (NATUR'ISOL SRL) not found!")
        return False
    print(f"✓ Found {company_naturisol.name} (ID: {company_naturisol.id})")

    # ========================================================================
    # STEP 2: Define user mapping
    # ========================================================================
    print("\nSTEP 2: Defining user structure...")

    # AMSS users
    amss_users = {
        'frederic.adam@belgogreen.be': 'Directeur de Sales',
        'corine.detilleux@belgogreen.be': 'Chef d\'equipe',
        'alexandre.emond@belgogreen.be': 'Commerciale',
        'ali.lmoughit@belgogreen.be': 'Commerciale',
        'ayman.toulfiha@belgogreen.be': 'Commerciale',
        'chrystel.slongo@belgogreen.be': 'Commerciale',
        'frederic.jansemme@belgogreen.be': 'Commerciale',
        'm.bennari@belgogreen.be': 'Commerciale',
        'selim.belmeddah@belgogreen.be': 'Commerciale',
        'thierry.grommen@belgogreen.be': 'Commerciale',
        'veronique.lerho@belgogreen.be': 'Commerciale',
        'walter.noweta@belgogreen.be': 'Commerciale',
        'younes.jamali@belgogreen.be': 'Commerciale',
    }

    # NaturIsol users
    naturisol_users = {
        'frederic.adam@belgogreen.be': 'Directeur de Sales',  # Same person, different company plan
        'contact@naturisol.be': 'Chef d\'equipe',  # Youssef Ouazzani-Chahdi
        'a.chekroun@naturisol.be': 'Commerciale',
        'd.isenge@naturisol.be': 'Commerciale',
        'f.zannou@naturisol.be': 'Commerciale',
        'm.belmeddah@naturisol.be': 'Commerciale',
    }

    print(f"✓ AMSS users: {len(amss_users)} users defined")
    print(f"✓ NaturIsol users: {len(naturisol_users)} users defined")

    # ========================================================================
    # STEP 3: Create or find roles for each company
    # ========================================================================
    print("\nSTEP 3: Creating/finding commission roles...")

    def get_or_create_role(company, role_name, code, sequence, requires_manager, can_manage, is_base):
        """Get or create a commission role"""
        role = env['sale.commission.role'].search([
            ('name', '=', role_name),
            ('company_id', '=', company.id)
        ], limit=1)

        if not role:
            role = env['sale.commission.role'].create({
                'name': role_name,
                'code': code,
                'sequence': sequence,
                'company_id': company.id,
                'requires_manager': requires_manager,
                'can_manage_subordinates': can_manage,
                'is_base_role': is_base,
                'active': True,
            })
            print(f"  ✓ Created role: {role_name} (sequence: {sequence}) for {company.name}")
        else:
            print(f"  ✓ Found existing role: {role_name} (ID: {role.id}) for {company.name}")

        return role

    # Create roles for AMSS
    print("\n  Creating roles for AMSS MANAGEMENT SRL:")
    role_directeur_amss = get_or_create_role(
        company_amss, 'Directeur de Sales', 'DS_AMSS', 30,
        requires_manager=False, can_manage=True, is_base=False
    )
    role_chef_amss = get_or_create_role(
        company_amss, 'Chef d\'equipe', 'CE_AMSS', 20,
        requires_manager=True, can_manage=True, is_base=False
    )
    role_commercial_amss = get_or_create_role(
        company_amss, 'Commerciale', 'COM_AMSS', 10,
        requires_manager=True, can_manage=False, is_base=True
    )

    # Create roles for NaturIsol
    print("\n  Creating roles for NATUR'ISOL SRL:")
    role_directeur_naturisol = get_or_create_role(
        company_naturisol, 'Directeur de Sales', 'DS_NAT', 30,
        requires_manager=False, can_manage=True, is_base=False
    )
    role_chef_naturisol = get_or_create_role(
        company_naturisol, 'Chef d\'equipe', 'CE_NAT', 20,
        requires_manager=True, can_manage=True, is_base=False
    )
    role_commercial_naturisol = get_or_create_role(
        company_naturisol, 'Commerciale', 'COM_NAT', 10,
        requires_manager=True, can_manage=False, is_base=True
    )

    # ========================================================================
    # STEP 4: Create Commission Plans
    # ========================================================================
    print("\nSTEP 4: Creating commission plans...")

    # Plan for AMSS
    plan_amss = env['sale.commission.plan'].search([
        ('name', '=', 'Plan de Commission Standard'),
        ('company_id', '=', company_amss.id)
    ], limit=1)

    if not plan_amss:
        plan_amss = env['sale.commission.plan'].create({
            'name': 'Plan de Commission Standard',
            'type': 'hierarchical',
            'company_id': company_amss.id,
            'periodicity': 'month',
            'state': 'draft',
            'require_invoice_paid': True,
        })
        print(f"  ✓ Created plan: Plan de Commission Standard for AMSS (ID: {plan_amss.id})")
    else:
        print(f"  ✓ Found existing plan for AMSS (ID: {plan_amss.id})")

    # Plan for NaturIsol
    plan_naturisol = env['sale.commission.plan'].search([
        ('name', '=', 'Plan de Commission Standard'),
        ('company_id', '=', company_naturisol.id)
    ], limit=1)

    if not plan_naturisol:
        plan_naturisol = env['sale.commission.plan'].create({
            'name': 'Plan de Commission Standard',
            'type': 'hierarchical',
            'company_id': company_naturisol.id,
            'periodicity': 'month',
            'state': 'draft',
            'require_invoice_paid': True,
        })
        print(f"  ✓ Created plan: Plan de Commission Standard for NaturIsol (ID: {plan_naturisol.id})")
    else:
        print(f"  ✓ Found existing plan for NaturIsol (ID: {plan_naturisol.id})")

    # ========================================================================
    # STEP 5: Create Role Configurations (Commission Percentages)
    # ========================================================================
    print("\nSTEP 5: Setting up role configurations (commission percentages)...")

    def create_role_config(plan, role, direct_pct, override_pct):
        """Create or update role configuration"""
        config = env['hr.commission.role.config'].search([
            ('plan_id', '=', plan.id),
            ('role_id', '=', role.id)
        ], limit=1)

        if not config:
            config = env['hr.commission.role.config'].create({
                'plan_id': plan.id,
                'role_id': role.id,
                'direct_sale_percentage': direct_pct,
                'override_percentage': override_pct,
            })
            print(f"    ✓ Created config for {role.name}: Direct={direct_pct}%, Override={override_pct}%")
        else:
            config.write({
                'direct_sale_percentage': direct_pct,
                'override_percentage': override_pct,
            })
            print(f"    ✓ Updated config for {role.name}: Direct={direct_pct}%, Override={override_pct}%")

        return config

    # AMSS role configurations
    print("\n  Configuring AMSS plan:")
    create_role_config(plan_amss, role_directeur_amss, 10.0, 5.0)  # Directeur: 10% direct, 5% override
    create_role_config(plan_amss, role_chef_amss, 10.0, 2.0)       # Chef: 10% direct, 2% override
    create_role_config(plan_amss, role_commercial_amss, 10.0, 0.0) # Commercial: 10% direct, 0% override

    # NaturIsol role configurations
    print("\n  Configuring NaturIsol plan:")
    create_role_config(plan_naturisol, role_directeur_naturisol, 10.0, 5.0)  # Directeur: 10% direct, 5% override
    create_role_config(plan_naturisol, role_chef_naturisol, 10.0, 2.0)       # Chef: 10% direct, 2% override
    create_role_config(plan_naturisol, role_commercial_naturisol, 10.0, 0.0) # Commercial: 10% direct, 0% override

    # ========================================================================
    # STEP 6: Assign Roles and Hierarchy to Users
    # ========================================================================
    print("\nSTEP 6: Assigning roles and setting up hierarchy...")

    def assign_user_role_and_manager(login, role, manager_login=None):
        """Find user and assign role and manager"""
        user = env['res.users'].search([('login', '=', login)], limit=1)
        if not user:
            print(f"    ⚠ WARNING: User {login} not found!")
            return None

        manager = None
        if manager_login:
            manager = env['res.users'].search([('login', '=', manager_login)], limit=1)
            if not manager:
                print(f"    ⚠ WARNING: Manager {manager_login} not found for user {login}!")

        # Update user
        update_vals = {'commission_role_id': role.id}
        if manager:
            update_vals['commission_manager_id'] = manager.id
        else:
            # Clear manager if this is a top-level role
            update_vals['commission_manager_id'] = False

        user.write(update_vals)

        manager_name = manager.name if manager else "None (Top Level)"
        print(f"    ✓ {user.name} ({login}) -> Role: {role.name}, Manager: {manager_name}")

        return user

    # AMSS hierarchy
    print("\n  Setting up AMSS hierarchy:")
    print("    Directeur de Sales:")
    frederic_amss = assign_user_role_and_manager('frederic.adam@belgogreen.be', role_directeur_amss)

    print("\n    Chef d'equipe (reporting to Directeur):")
    corine = assign_user_role_and_manager('corine.detilleux@belgogreen.be', role_chef_amss, 'frederic.adam@belgogreen.be')

    print("\n    Commerciales (reporting to Chef d'equipe):")
    for login in amss_users:
        if login not in ['frederic.adam@belgogreen.be', 'corine.detilleux@belgogreen.be']:
            assign_user_role_and_manager(login, role_commercial_amss, 'corine.detilleux@belgogreen.be')

    # NaturIsol hierarchy
    print("\n  Setting up NaturIsol hierarchy:")
    print("    Directeur de Sales:")
    frederic_nat = assign_user_role_and_manager('frederic.adam@belgogreen.be', role_directeur_naturisol)

    print("\n    Chef d'equipe (reporting to Directeur):")
    youssef = assign_user_role_and_manager('contact@naturisol.be', role_chef_naturisol, 'frederic.adam@belgogreen.be')

    print("\n    Commerciales (reporting to Chef d'equipe):")
    for login in naturisol_users:
        if login not in ['frederic.adam@belgogreen.be', 'contact@naturisol.be']:
            assign_user_role_and_manager(login, role_commercial_naturisol, 'contact@naturisol.be')

    # ========================================================================
    # STEP 7: Commit and Summary
    # ========================================================================
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"\n✓ Created/Updated 2 commission plans:")
    print(f"  - AMSS MANAGEMENT SRL: {plan_amss.name} (ID: {plan_amss.id})")
    print(f"  - NATUR'ISOL SRL: {plan_naturisol.name} (ID: {plan_naturisol.id})")

    print(f"\n✓ Created/Updated 6 roles (3 per company):")
    print(f"  AMSS: Directeur de Sales, Chef d'equipe, Commerciale")
    print(f"  NaturIsol: Directeur de Sales, Chef d'equipe, Commerciale")

    print(f"\n✓ Set up hierarchies:")
    print(f"  AMSS: 1 Directeur -> 1 Chef -> 11 Commerciales")
    print(f"  NaturIsol: 1 Directeur -> 1 Chef -> 4 Commerciales")

    print(f"\n✓ Commission percentages:")
    print(f"  - Directeur de Sales: 10% direct sales, 5% override")
    print(f"  - Chef d'equipe: 10% direct sales, 2% override")
    print(f"  - Commerciale: 10% direct sales, 0% override")

    print(f"\n⚠ IMPORTANT: Plans are in DRAFT state.")
    print(f"   Please review and APPROVE them in Odoo UI before they take effect.")

    print("\n" + "="*80)
    print("Script completed successfully!")
    print("="*80 + "\n")

    # Commit the transaction
    env.cr.commit()

    return True


# ============================================================================
# Main execution
# ============================================================================
if __name__ == '__main__':
    # This will be executed when running through odoo-bin shell
    try:
        result = create_hierarchical_commission_plans(env)
        if result:
            print("\n✓✓✓ SUCCESS! All commission plans created successfully! ✓✓✓\n")
        else:
            print("\n✗✗✗ FAILED! Check error messages above. ✗✗✗\n")
    except Exception as e:
        print(f"\n✗✗✗ ERROR: {str(e)} ✗✗✗\n")
        import traceback
        traceback.print_exc()
        env.cr.rollback()
