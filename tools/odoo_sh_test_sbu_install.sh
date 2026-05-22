#!/bin/bash
# Reproduce Odoo.sh SBU tests on this database.
# Use -u (upgrade) when modules are already installed; -i alone runs 0 tests.
set -euo pipefail
DB="${PGDATABASE:?Set PGDATABASE}"
ADDONS="/home/odoo/src/user,/home/odoo/src/odoo/addons,/home/odoo/src/odoo/odoo/addons"
ODOO="/home/odoo/src/odoo/odoo-bin"
LOG="${1:-/home/odoo/tmp/sbu-install-test.log}"
MODULES="sbu_stock_config,sbu_estimate,sbu_purchase_flow,sbu_sal,sbu_project,sbu_documents,sbu_closure,sbu_integrations,sbu_logikal,sbu_mail_ingest,sbu_qonto,sbu_revolut"
TEST_TAGS="/sbu_estimate,/sbu_purchase_flow,/sbu_sal,/sbu_stock_config,/sbu_closure,/sbu_qonto,/sbu_logikal,/sbu_documents,/sbu_project,/sbu_integrations,/sbu_mail_ingest,/sbu_revolut"

echo "=== Git commit ==="
git -C /home/odoo/src/user log -1 --oneline

echo "=== Module state BEFORE ==="
python3 "$ODOO" shell -d "$DB" --addons-path="$ADDONS" --stop-after-init <<'PY' 2>/dev/null | tail -20 || true
mods = ['sbu_estimate', 'sbu_purchase_flow', 'sbu_sal', 'sbu_stock_config']
imm = env['ir.module.module'].search([('name', 'in', mods)])
for m in mods:
    rec = imm.filtered(lambda r: r.name == m)[:1]
    print(m, rec.state if rec else 'missing')
PY

MODE="upgrade"
echo "=== SBU tests via -u (upgrade) — required when modules are already installed ==="
python3 "$ODOO" \
  -d "$DB" \
  --addons-path="$ADDONS" \
  -u "$MODULES" \
  --test-enable \
  --stop-after-init \
  --log-level=test \
  --test-tags "$TEST_TAGS" \
  2>&1 | tee "$LOG"

echo ""
echo "=== Module state AFTER ==="
python3 "$ODOO" shell -d "$DB" --addons-path="$ADDONS" --stop-after-init <<'PY' 2>/dev/null | tail -20 || true
mods = ['sbu_estimate', 'sbu_purchase_flow', 'sbu_sal', 'sbu_stock_config']
imm = env['ir.module.module'].search([('name', 'in', mods)])
for m in mods:
    rec = imm.filtered(lambda r: r.name == m)[:1]
    print(m, rec.state if rec else 'missing')
PY

echo "=== Summary ==="
grep -nE 'FAIL:|ERROR: test_|AssertionError|ParseError|failures=[1-9]| errors=[1-9]|have the same label' "$LOG" | tail -40 || echo "(no failure patterns)"
grep -E 'odoo.tests.result:|odoo.tests.stats: sbu_' "$LOG" | tail -30

ZERO=$(grep -c '0 failed, 0 error(s) of 0 tests' "$LOG" 2>/dev/null || echo 0)
if [[ "$ZERO" -gt 0 ]]; then
  echo ""
  echo ">>> WARNING: 0 tests executed. Modules were not upgraded or test-tags matched nothing."
  echo ">>> Re-run: odoo-bin -d \"\$PGDATABASE\" --addons-path=\"$ADDONS\" -u sbu_sal,sbu_purchase_flow,sbu_estimate --test-enable --stop-after-init --log-level=test --test-tags /sbu_sal,/sbu_purchase_flow,/sbu_estimate"
fi
