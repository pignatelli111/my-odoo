#!/bin/bash
# Reproduce Odoo.sh build: install SBU apps + run their tests (same as install.log -i … --test-enable).
set -euo pipefail
DB="${PGDATABASE:?Set PGDATABASE}"
ADDONS="/home/odoo/src/user,/home/odoo/src/odoo/addons,/home/odoo/src/odoo/odoo/addons"
ODOO="/home/odoo/src/odoo/odoo-bin"
LOG="${1:-/home/odoo/tmp/sbu-install-test.log}"
MODULES="sbu_stock_config,sbu_estimate,sbu_purchase_flow,sbu_sal,sbu_project,sbu_documents,sbu_closure,sbu_integrations,sbu_logikal,sbu_mail_ingest,sbu_qonto,sbu_revolut"

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

echo "=== Install + test (this matches Odoo.sh build) ==="
python3 "$ODOO" \
  -d "$DB" \
  --addons-path="$ADDONS" \
  -i "$MODULES" \
  --test-enable \
  --stop-after-init \
  --log-level=test \
  --test-tags "/sbu_estimate,/sbu_purchase_flow,/sbu_sal,/sbu_stock_config,/sbu_closure,/sbu_qonto,/sbu_logikal,/sbu_documents,/sbu_project,/sbu_integrations,/sbu_mail_ingest,/sbu_revolut" \
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
echo ""
echo "If purchase_flow/sal stats are missing above, those modules did not install or had no tests."
