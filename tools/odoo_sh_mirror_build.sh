#!/bin/bash
# Reproduce the Odoo.sh dev build: fresh -i of ALL sbu_* modules + SBU test-tags.
# Usage: bash /home/odoo/src/user/tools/odoo_sh_mirror_build.sh
set -uo pipefail
DB="${PGDATABASE:?Set PGDATABASE}"
REPO="${USER_REPO:-/home/odoo/src/user}"
ADDONS="/home/odoo/src/user,/home/odoo/src/odoo/addons,/home/odoo/src/odoo/odoo/addons"
if [[ -d /home/odoo/src/enterprise ]]; then
  ADDONS="/home/odoo/src/enterprise,${ADDONS}"
fi
ODOO="/home/odoo/src/odoo/odoo-bin"
LOG="/tmp/sbu-mirror-build.log"
# Same module set as Odoo.sh install.log «Executed command» (dev branch).
MODULES="sbu_closure,sbu_documents,sbu_estimate,sbu_integrations,sbu_logikal,sbu_mail_ingest,sbu_project,sbu_purchase_flow,sbu_qonto,sbu_revolut,sbu_sal,sbu_stock_config"
TAGS="/sbu_closure,/sbu_documents,/sbu_estimate,/sbu_integrations,/sbu_logikal,/sbu_mail_ingest,/sbu_project,/sbu_purchase_flow,/sbu_qonto,/sbu_revolut,/sbu_sal,/sbu_stock_config"

echo "=== Commit ==="
git -C "$REPO" log -1 --oneline

echo "=== Odoo.sh-style: -i $MODULES + test-tags ==="
echo "Log: $LOG"
python3 "$ODOO" \
  -d "$DB" \
  --addons-path="$ADDONS" \
  -i "$MODULES" \
  --test-enable \
  --stop-after-init \
  --log-level=test \
  --test-tags "$TAGS" \
  2>&1 | tee "$LOG"
EXIT=$?

echo ""
echo "=== exit code: $EXIT ==="
grep -nE 'FAIL:|ERROR: test_|AssertionError|ParseError|Could not load module|cannot be located|CRITICAL.*Failed' "$LOG" | tail -40 || echo "(no failure patterns)"
grep -E 'odoo\.tests\.result:|odoo\.tests\.stats: sbu_' "$LOG" | tail -25 || echo "(no test summary)"
grep -c '0 failed, 0 error(s) of 0 tests' "$LOG" 2>/dev/null || true

exit "$EXIT"
