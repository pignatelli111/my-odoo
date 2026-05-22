#!/bin/bash
# Copy to production Odoo.sh shell (works even when tools/ is not deployed yet):
#   curl -sL "https://raw.githubusercontent.com/pignatelli111/my-odoo/production/DIAG_PROD_SHELL.sh" -o /tmp/diag.sh && bash /tmp/diag.sh
# Or paste this file after: cd ~/src/user && git fetch && git checkout origin/production
set -uo pipefail
REPO="${USER_REPO:-/home/odoo/src/user}"
echo "=== Git ==="
git -C "$REPO" log -1 --oneline 2>/dev/null || true
echo "=== Log files ==="
ls -la ~/logs/ 2>/dev/null || true
echo "=== install.log (first + last) ==="
head -4 ~/logs/install.log 2>/dev/null || true
tail -8 ~/logs/install.log 2>/dev/null || true
echo "=== odoo.log test lines ==="
grep -nE 'FAIL:|tests\.result|have the same label|Traceback' ~/logs/odoo.log 2>/dev/null | tail -25 || echo "(none)"
echo "=== Run SBU tests (writes /tmp/sbu-test.log) ==="
if [[ -f "$REPO/tools/odoo_sh_run_tests.sh" ]]; then
  bash "$REPO/tools/odoo_sh_run_tests.sh"
else
  echo "tools/odoo_sh_run_tests.sh missing — deploy a green build or: git fetch && git checkout origin/production"
fi
