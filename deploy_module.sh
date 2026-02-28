#!/bin/bash

# Colors for better readability
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Claude Branch Merge & Deploy Script ===${NC}\n"

# Auto-detect module name from origin remote
origin_url=$(git remote get-url origin 2>/dev/null)

if [ -z "$origin_url" ]; then
    echo -e "${RED}❌ Error: No origin remote found${NC}"
    exit 1
fi

# Extract module name from URL (e.g., belgogreen_sales_commission_mod -> belgogreen_sales_commission)
# This works for URLs like: https://github.com/user/belgogreen_sales_commission_mod.git
module_name=$(echo "$origin_url" | sed -E 's|.*/([^/]+)\.git$|\1|' | sed 's/_mod$//')

echo -e "${BLUE}📦 Detected module: ${YELLOW}$module_name${NC}\n"

# Verify upstream exists
if ! git remote get-url upstream >/dev/null 2>&1; then
    echo -e "${RED}❌ Error: No upstream remote found${NC}"
    echo -e "${YELLOW}ℹ️  Add upstream with: git remote add upstream https://github.com/bsimprovement/belgogreen.git${NC}"
    exit 1
fi

# Ask for Claude branch name
read -p "Enter the Claude branch name: " claude_branch

if [ -z "$claude_branch" ]; then
    echo -e "${RED}❌ Error: Branch name cannot be empty${NC}"
    exit 1
fi

echo -e "\n${YELLOW}Fetching latest branches from origin...${NC}"
git fetch origin

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Error: Failed to fetch from origin${NC}"
    exit 1
fi

# Validate branch exists
if ! git rev-parse --verify "$claude_branch" >/dev/null 2>&1; then
    if ! git rev-parse --verify "origin/$claude_branch" >/dev/null 2>&1; then
        echo -e "${RED}❌ Error: Branch '$claude_branch' does not exist locally or on origin${NC}"
        exit 1
    else
        echo -e "${YELLOW}Branch exists on origin, checking out...${NC}"
        git checkout "$claude_branch"
        if [ $? -ne 0 ]; then
            echo -e "${RED}❌ Error: Failed to checkout branch${NC}"
            exit 1
        fi
    fi
fi

echo -e "\n${YELLOW}Switching to main branch...${NC}"
git checkout main

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Error: Failed to checkout main branch${NC}"
    exit 1
fi

echo -e "\n${YELLOW}Pulling latest from origin main...${NC}"
git pull origin main

if [ $? -ne 0 ]; then
    echo -e "${YELLOW}⚠️  Warning: Failed to pull from origin main (this is okay if it's a new branch)${NC}"
fi

echo -e "\n${YELLOW}Merging $claude_branch into main...${NC}"
git merge "$claude_branch"

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Error: Merge failed. Please resolve conflicts manually.${NC}"
    exit 1
fi

echo -e "\n${YELLOW}Pushing to origin main...${NC}"
git push origin main

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Error: Failed to push to origin${NC}"
    exit 1
fi

echo -e "\n${GREEN}✅ Successfully merged and pushed to origin!${NC}\n"

# Ask if user wants to push to upstream
read -p "Do you want to push to upstream (original repo: $module_name branch)? (yes/no): " push_upstream

if [[ "$push_upstream" == "yes" || "$push_upstream" == "y" ]]; then
    echo -e "\n${YELLOW}Fetching from upstream to check if branch exists...${NC}"
    git fetch upstream

    echo -e "\n${YELLOW}Pushing to upstream:${BLUE}$module_name${NC} branch...${NC}"
    git push upstream main:$module_name

    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Error: Failed to push to upstream${NC}"
        echo -e "${YELLOW}ℹ️  Make sure the branch '$module_name' exists on upstream or you have permission to create it${NC}"
        exit 1
    fi

    echo -e "\n${GREEN}✅ Successfully pushed to upstream:$module_name!${NC}"
else
    echo -e "\n${BLUE}ℹ️  Skipped pushing to upstream${NC}"
fi

# Clean up merged branch
read -p "Do you want to delete the merged Claude branch? (yes/no): " delete_branch

if [[ "$delete_branch" == "yes" || "$delete_branch" == "y" ]]; then
    echo -e "\n${YELLOW}Deleting local branch $claude_branch...${NC}"
    git branch -d "$claude_branch"

    echo -e "${YELLOW}Deleting remote branch $claude_branch...${NC}"
    git push origin --delete "$claude_branch"

    echo -e "${GREEN}✅ Branch cleanup complete!${NC}"
fi

echo -e "\n${GREEN}🎉 All done!${NC}"
echo -e "${BLUE}Summary:${NC}"
echo -e "  • Module: ${YELLOW}$module_name${NC}"
echo -e "  • Merged: ${YELLOW}$claude_branch${NC} → main"
echo -e "  • Pushed to: origin/main"
if [[ "$push_upstream" == "yes" || "$push_upstream" == "y" ]]; then
    echo -e "  • Pushed to: ${YELLOW}upstream/$module_name${NC}"
fi
echo ""
