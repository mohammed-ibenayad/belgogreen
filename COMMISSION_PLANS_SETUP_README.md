# Commission Plans Setup Script

This script creates hierarchical commission plans for AMSS MANAGEMENT SRL and NATUR'ISOL SRL.

## What This Script Does

The script creates:

### 1. Two Commission Plans
- **Plan de Commission Standard** for AMSS MANAGEMENT SRL
- **Plan de Commission Standard** for NATUR'ISOL SRL

### 2. Commission Roles (3 per company)

#### AMSS MANAGEMENT SRL:
- **Directeur de Sales** (Sequence 30) - Top level
  - Frederic Adam
- **Chef d'equipe** (Sequence 20) - Middle level
  - Corine Detilleux
- **Commerciale** (Sequence 10) - Base level
  - Alexandre Emond, Ali Lmoughit, Ayman Toulfiha, Chrystel Slongo
  - Frederic Jansemme, Mohamed Bennari, Selim Belmeddah
  - Thierry Grommen, Veronique Lerho, Walter Noweta, Younes Jamali

#### NATUR'ISOL SRL:
- **Directeur de Sales** (Sequence 30) - Top level
  - Frederic Adam
- **Chef d'equipe** (Sequence 20) - Middle level
  - Youssef Ouazzani-Chahdi
- **Commerciale** (Sequence 10) - Base level
  - Abdoullah Chekroun, Deni Isenge, Farida Zannou, Mehdi Belmeddah

### 3. Commission Percentages

| Role               | Direct Sales | Override |
|--------------------|--------------|----------|
| Directeur de Sales | 10%          | 5%       |
| Chef d'equipe      | 10%          | 2%       |
| Commerciale        | 10%          | 0%       |

**Note:** Commerciales (base level) don't have override commission since they're at the bottom of the hierarchy.

### 4. Hierarchical Structure

#### AMSS:
```
Frederic Adam (Directeur de Sales)
└── Corine Detilleux (Chef d'equipe)
    ├── Alexandre Emond (Commerciale)
    ├── Ali Lmoughit (Commerciale)
    ├── Ayman Toulfiha (Commerciale)
    ├── Chrystel Slongo (Commerciale)
    ├── Frederic Jansemme (Commerciale)
    ├── Mohamed Bennari (Commerciale)
    ├── Selim Belmeddah (Commerciale)
    ├── Thierry Grommen (Commerciale)
    ├── Veronique Lerho (Commerciale)
    ├── Walter Noweta (Commerciale)
    └── Younes Jamali (Commerciale)
```

#### NaturIsol:
```
Frederic Adam (Directeur de Sales)
└── Youssef Ouazzani-Chahdi (Chef d'equipe)
    ├── Abdoullah Chekroun (Commerciale)
    ├── Deni Isenge (Commerciale)
    ├── Farida Zannou (Commerciale)
    └── Mehdi Belmeddah (Commerciale)
```

## How to Execute on Odoo.sh

### Method 1: Using Odoo Shell (Recommended)

1. Upload the script to your Odoo.sh instance
2. SSH into your Odoo.sh server
3. Run the following command:

```bash
odoo-bin shell -d <your_database_name> < create_commission_plans.py
```

Replace `<your_database_name>` with your actual database name.

### Method 2: Copy-Paste into Odoo Shell

1. SSH into your Odoo.sh server
2. Start the Odoo shell:
```bash
odoo-bin shell -d <your_database_name>
```

3. Copy and paste the entire content of `create_commission_plans.py` (excluding the shebang line)
4. The script will execute automatically

### Method 3: Using Odoo Web UI (Developer Mode)

1. Enable developer mode in Odoo
2. Go to Settings → Technical → Automation → Python Code
3. Paste the function content and execute

## After Running the Script

1. **Review the Plans**: Go to Sales → Configuration → Commission Plans
2. **Verify Users**: Check that all users have the correct roles assigned
3. **Check Hierarchy**: Verify the manager relationships are correct
4. **Approve Plans**: The plans are created in DRAFT state. You must APPROVE them before they take effect:
   - Open each plan
   - Click "Approve" button

## Important Notes

- All users are set as **commission users only** (not commission managers)
- The commission manager role can be assigned to another user separately
- Plans require paid invoices before calculating commissions (`require_invoice_paid = True`)
- The script is idempotent: running it multiple times will update existing records instead of creating duplicates

## Troubleshooting

If you encounter errors:

1. **Company not found**: Ensure company names match exactly:
   - `AMSS MANAGEMENT SRL`
   - `NATUR'ISOL SRL`

2. **User not found**: Check that user logins match the table provided:
   - Verify email addresses in Odoo match the script

3. **Permission errors**: Ensure you have admin rights or proper permissions

## Questions?

Contact the system administrator or refer to the commission module documentation.
