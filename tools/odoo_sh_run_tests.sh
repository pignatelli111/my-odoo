#!/bin/bash
# One command: module check → force upgrade → SBU tests → print failures.
# Usage: bash /home/odoo/src/user/tools/odoo_sh_run_tests.sh
set -uo pipefail
DB="${PGDATABASE:?Set PGDATABASE}"
REPO="${USER_REPO:-/home/odoo/src/user}"
ADDONS="/home/odoo/src/user,/home/odoo/src/odoo/addons,/home/odoo/src/odoo/odoo/addons"
if [[ -d /home/odoo/src/enterprise ]]; then
  ADDONS="/home/odoo/src/enterprise,${ADDONS}"
fi
ODOO="/home/odoo/src/odoo/odoo-bin"
LOG="/tmp/sbu-test.log"
MODULES="sbu_stock_config,sbu_estimate,sbu_purchase_flow,sbu_sal,sbu_project,sbu_documents,sbu_closure,sbu_integrations,sbu_logikal,sbu_mail_ingest,sbu_qonto,sbu_revolut"
TEST_TAGS="/sbu_estimate,/sbu_purchase_flow,/sbu_sal,/sbu_stock_config,/sbu_closure,/sbu_qonto,/sbu_logikal,/sbu_documents,/sbu_project,/sbu_integrations,/sbu_mail_ingest,/sbu_revolut"

echo "=== Commit ==="
git -C "$REPO" log -1 --oneline

echo "=== SBU module state ==="
python3 "$ODOO" shell -d "$DB" --addons-path="$ADDONS" --stop-after-init <<'PY'
mods = [
    'sbu_estimate', 'sbu_purchase_flow', 'sbu_sal', 'sbu_stock_config',
    'sbu_project', 'sbu_documents', 'sbu_closure',
]
imm = env['ir.module.module'].search([('name', 'in', mods)])
for name in mods:
    rec = imm.filtered(lambda r: r.name == name)[:1]
    print(name, rec.state if rec else 'missing', rec.latest_version if rec else '')
# Force upgrade so --test-enable runs post_install tests (not only when version changed).
to_upgrade = imm.filtered(lambda m: m.state == 'installed')
if to_upgrade:
    to_upgrade.write({'state': 'to upgrade'})
    print('marked_to_upgrade', ','.join(to_upgrade.mapped('name')))
PY

echo "=== Running upgrade + tests (log: $LOG) ==="
python3 "$ODOO" \
  -d "$DB" \
  --addons-path="$ADDONS" \
  -i "$MODULES" \
  --test-enable \
  --stop-after-init \
  --log-level=test \
  --test-tags "$TEST_TAGS" \
  2>&1 | tee "$LOG"

echo ""
echo "=== FAILURES ==="
grep -nE 'FAIL:|ERROR: test_|AssertionError|ParseError|Could not load module|cannot be located|CRITICAL' "$LOG" | tail -40 || echo "(none)"

echo ""
echo "=== TEST SUMMARY ==="
grep -E 'odoo\.tests\.result:|odoo\.tests\.stats: sbu_' "$LOG" | tail -25 || echo "(none)"

ZERO=$(grep -c '0 failed, 0 error(s) of 0 tests' "$LOG" 2>/dev/null | tr -d '\n' || echo 0)
ZERO=${ZERO:-0}
if [[ "${ZERO:-0}" -gt 0 ]]; then
  echo ""
  echo ">>> 0 tests ran. See loading sbu_ lines:"
  grep -c 'loading sbu_' "$LOG" 2>/dev/null || echo 0
fi

echo ""
echo "Log file: $LOG"
