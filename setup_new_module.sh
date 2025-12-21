#!/bin/bash

# Colors for better readability
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Odoo 19 Module Setup Script ===${NC}\n"

# Configuration
MODULE_NAME="bgg_custom_dev"
MODULE_TITLE="BelGoGreen Custom Development"
MODULE_DESCRIPTION="Custom development module for BelGoGreen operations and workflows"
MODULE_CATEGORY="Custom"
AUTHOR="Belgogreen"
WEBSITE="https://www.belgogreen.com"
VERSION="19.0.0.0"

echo -e "${YELLOW}Creating module: ${BLUE}$MODULE_NAME${NC}\n"

# Create directory structure
echo -e "${YELLOW}Creating directory structure...${NC}"
mkdir -p "$MODULE_NAME"
mkdir -p "$MODULE_NAME/models"
mkdir -p "$MODULE_NAME/views"
mkdir -p "$MODULE_NAME/security"
mkdir -p "$MODULE_NAME/data"
mkdir -p "$MODULE_NAME/static/description"

# Create __init__.py files
echo -e "${YELLOW}Creating __init__.py files...${NC}"

cat > "$MODULE_NAME/__init__.py" <<'EOF'
# -*- coding: utf-8 -*-

from . import models
EOF

cat > "$MODULE_NAME/models/__init__.py" <<'EOF'
# -*- coding: utf-8 -*-

# Import your models here
# Example:
# from . import custom_model
EOF

# Create __manifest__.py
echo -e "${YELLOW}Creating __manifest__.py...${NC}"

cat > "$MODULE_NAME/__manifest__.py" <<EOF
# -*- coding: utf-8 -*-
{
    'name': "$MODULE_TITLE",

    'summary': "$MODULE_DESCRIPTION",

    'description': """
$MODULE_TITLE
${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}${'='}

This module provides custom development features for BelGoGreen:

* Custom models and business logic
* Custom views and reports
* Integration with existing Odoo modules
* Workflow enhancements

Main Features:
--------------
* Customizable business processes
* Extended functionality for core modules
* Custom reports and dashboards
* Integration utilities
    """,

    'author': "$AUTHOR",
    'website': "$WEBSITE",

    'category': '$MODULE_CATEGORY',
    'version': '$VERSION',
    'license': 'LGPL-3',

    # Dependencies
    'depends': [
        'base',
        'web',
    ],

    # Data files
    'data': [
        'security/ir.model.access.csv',
        'views/menu_views.xml',
    ],

    'assets': {
        # 'web.assets_backend': [
        #     '$MODULE_NAME/static/src/js/**/*',
        #     '$MODULE_NAME/static/src/scss/**/*',
        #     '$MODULE_NAME/static/src/xml/**/*',
        # ],
    },

    'installable': True,
    'application': True,
    'auto_install': False,
}
EOF

# Create security file
echo -e "${YELLOW}Creating security files...${NC}"

cat > "$MODULE_NAME/security/ir.model.access.csv" <<EOF
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
EOF

# Create basic menu view
echo -e "${YELLOW}Creating menu views...${NC}"

cat > "$MODULE_NAME/views/menu_views.xml" <<EOF
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Root Menu -->
    <menuitem id="menu_${MODULE_NAME}_root"
              name="$MODULE_TITLE"
              sequence="100"/>

    <!-- Main Menu Categories -->
    <!-- Uncomment and customize as needed
    <menuitem id="menu_${MODULE_NAME}_config"
              name="Configuration"
              parent="menu_${MODULE_NAME}_root"
              sequence="99"/>
    -->

</odoo>
EOF

# Create README
echo -e "${YELLOW}Creating README.md...${NC}"

cat > "README.md" <<EOF
# $MODULE_TITLE

## Description

$MODULE_DESCRIPTION

This module extends Odoo 19 with custom functionality specific to BelGoGreen operations.

## Features

- Custom business logic and workflows
- Integration with core Odoo modules
- Custom views and reports
- Configurable settings

## Installation

1. Copy this module to your Odoo addons directory
2. Update the app list: \`Settings > Apps > Update Apps List\`
3. Search for "$MODULE_TITLE"
4. Click Install

## Configuration

After installation, configure the module:

1. Go to \`$MODULE_TITLE > Configuration\`
2. Set up your preferences
3. Configure user permissions

## Usage

[Add usage instructions here]

## Technical Details

- **Module Name:** \`$MODULE_NAME\`
- **Version:** $VERSION
- **Odoo Version:** 19.0
- **License:** LGPL-3
- **Author:** $AUTHOR

## Dependencies

- base
- web

## Support

For support, please contact $WEBSITE

## Changelog

### Version 19.0.0.0
- Initial release
- Basic module structure
EOF

# Create .gitignore
echo -e "${YELLOW}Creating .gitignore...${NC}"

cat > ".gitignore" <<'EOF'
# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# C extensions
*.so

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# PyInstaller
*.manifest
*.spec

# Unit test / coverage reports
htmlcov/
.tox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
.hypothesis/
.pytest_cache/

# Translations
*.mo
*.pot

# Django stuff:
*.log
local_settings.py
db.sqlite3

# Flask stuff:
instance/
.webassets-cache

# Scrapy stuff:
.scrapy

# Sphinx documentation
docs/_build/

# PyBuilder
target/

# Jupyter Notebook
.ipynb_checkpoints

# pyenv
.python-version

# celery beat schedule file
celerybeat-schedule

# SageMath parsed files
*.sage.py

# Environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# Spyder project settings
.spyderproject
.spyproject

# Rope project settings
.ropeproject

# mkdocs documentation
/site

# mypy
.mypy_cache/
.dmypy.json
dmypy.json

# IDE
.idea/
.vscode/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Odoo
filestore/
sessions/
addons/
EOF

echo -e "\n${GREEN}✅ Module structure created successfully!${NC}\n"

# Summary
echo -e "${BLUE}Module Summary:${NC}"
echo -e "  Name: ${YELLOW}$MODULE_NAME${NC}"
echo -e "  Title: ${YELLOW}$MODULE_TITLE${NC}"
echo -e "  Version: ${YELLOW}$VERSION${NC}"
echo -e "  Category: ${YELLOW}$MODULE_CATEGORY${NC}"

echo -e "\n${BLUE}Directory Structure:${NC}"
tree -L 3 "$MODULE_NAME" 2>/dev/null || find "$MODULE_NAME" -print | sed -e 's;[^/]*/;|____;g;s;____|;  |;g'

echo -e "\n${BLUE}Files Created:${NC}"
echo -e "  • $MODULE_NAME/__init__.py"
echo -e "  • $MODULE_NAME/__manifest__.py"
echo -e "  • $MODULE_NAME/models/__init__.py"
echo -e "  • $MODULE_NAME/security/ir.model.access.csv"
echo -e "  • $MODULE_NAME/views/menu_views.xml"
echo -e "  • README.md"
echo -e "  • .gitignore"

echo -e "\n${YELLOW}Next Steps:${NC}"
echo -e "  1. Review and customize the module files"
echo -e "  2. Add your models in ${BLUE}$MODULE_NAME/models/${NC}"
echo -e "  3. Add your views in ${BLUE}$MODULE_NAME/views/${NC}"
echo -e "  4. Update security access in ${BLUE}$MODULE_NAME/security/ir.model.access.csv${NC}"
echo -e "  5. Test the module in your Odoo instance"
echo -e "  6. Commit changes: ${BLUE}git add . && git commit -m \"Initial module structure\"${NC}"
echo -e "  7. Push to origin: ${BLUE}git push -u origin main${NC}"

echo -e "\n${GREEN}🎉 Ready to develop!${NC}\n"
