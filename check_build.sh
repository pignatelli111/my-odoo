#!/bin/bash
# Odoo.sh: bash ~/src/user/check_build.sh
# 1) Grep last platform install.log  2) Hint to mirror full CI locally
REPO="$(cd "$(dirname "$0")" && pwd)"
bash "$REPO/tools/grep_odoo_sh_test_fail.sh" "$@" || true
echo ""
echo "If install.log is empty or shows 0 tests, mirror the Odoo.sh build:"
echo "  bash $REPO/tools/odoo_sh_mirror_build.sh"
echo "  grep -E 'FAIL:|odoo.tests.result' /tmp/sbu-mirror-build.log | tail -30"
