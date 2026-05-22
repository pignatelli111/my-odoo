#!/bin/bash
# Reproduce Odoo.sh SBU tests on this database.
# - If SBU modules are uninstalled: -i (install) then tests run on loaded modules.
# - If already installed: -u (upgrade) with --test-enable.
set -euo pipefail
DB="${PGDATABASE:?Set PGDATABASE}"
ADDONS="/home/odoo/src/user,/home/odoo/src/odoo/addons,/home/odoo/src/odoo/odoo/addons"
ODOO="/home/odoo/src/odoo/odoo-bin"
LOG="${1:-/home/odoo/tmp/sbu-install-test.log}"
MODULES="sbu_stock_config,sbu_estimate,sbu_purchase_flow,sbu_sal,sbu_project,sbu_documents,sbu_closure,sbu_integrations,sbu_logikal,sbu_mail_ingest,sbu_qonto,sbu_revolut"
TEST_TAGS="/sbu_estimate,/sbu_purchase_flow,/sbu_sal,/sbu_stock_config,/sbu_closure,/sbu_qonto,/sbu_logikal,/sbu_documents,/sbu_project,/sbu_integrations,/sbu_mail_ingest,/sbu_revolut"
CORE="sbu_estimate,sbu_purchase_flow,sbu_sal,sbu_stock_config"

echo "=== Git commit ==="
git -C /home/odoo/src/user log -1 --oneline

echo "=== Module state BEFORE ==="
STATES=$(python3 "$ODOO" shell -d "$DB" --addons-path="$ADDONS" --stop-after-init <<'PY' 2>/dev/null || true
mods = ['sbu_estimate', 'sbu_purchase_flow', 'sbu_sal', 'sbu_stock_config']
imm = env['ir.module.module'].search([('name', 'in', mods)])
for m in mods:
    rec = imm.filtered(lambda r: r.name == m)[:1]
    print(m, rec.state if rec else 'missing')
PY
)
echo "$STATES"

NEED_INSTALL=0
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  state="${line##* }"
  if [[ "$state" == "uninstalled" || "$state" == "missing" ]]; then
    NEED_INSTALL=1
  fi
done <<< "$STATES"

if [[ "$NEED_INSTALL" -eq 1 ]]; then
  echo "=== SBU install + tests via -i (modules were not installed) ==="
  INSTALL_FLAG="-i"
else
  echo "=== SBU tests via -u (upgrade installed modules) ==="
  INSTALL_FLAG="-u"
fi

python3 "$ODOO" \
  -d "$DB" \
  --addons-path="$ADDONS" \
  "$INSTALL_FLAG" "$MODULES" \
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
    print(m, rec.state if rec else 'missing', rec.latest_version if rec else '')
PY

echo "=== Summary ==="
grep -nE 'FAIL:|ERROR: test_|AssertionError|ParseError|failures=[1-9]| errors=[1-9]|have the same label' "$LOG" | tail -40 || echo "(no failure patterns)"
grep -E 'odoo.tests.result:|odoo.tests.stats: sbu_' "$LOG" | tail -30

ZERO=$(grep -c '0 failed, 0 error(s) of 0 tests' "$LOG" 2>/dev/null || echo 0)
if [[ "$ZERO" -gt 0 ]]; then
  echo ""
  echo ">>> WARNING: 0 tests executed."
  echo ">>> Check log for «loading sbu_» lines. If none, addons path or module names are wrong."
  echo ">>> If install failed, scroll up in $LOG for Traceback / Could not load module."
fi

grep -c 'loading sbu_' "$LOG" 2>/dev/null || echo "sbu_ load lines: 0"
