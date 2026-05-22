#!/bin/bash
# Odoo.sh: quick diagnosis for dev vs production test failure.
# Usage: bash ~/src/user/tools/odoo_sh_branch_diag.sh
set -uo pipefail
REPO="${USER_REPO:-/home/odoo/src/user}"
echo "=== Branch / commit ==="
git -C "$REPO" branch --show-current 2>/dev/null || true
git -C "$REPO" log -1 --oneline 2>/dev/null || true
echo "PGDATABASE=${PGDATABASE:-?}"
echo ""
bash "$REPO/tools/grep_odoo_sh_test_fail.sh" 2>/dev/null || true
