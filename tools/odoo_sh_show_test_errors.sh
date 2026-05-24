#!/bin/bash
# Print the 4 test ERROR tracebacks from install.log (Odoo.sh shell).
# Usage: bash ~/src/user/tools/odoo_sh_show_test_errors.sh
set -uo pipefail
LOG="${1:-/home/odoo/logs/install.log}"

echo "=== Test summary ==="
grep -n 'odoo.tests.result:' "$LOG" | tail -5

echo ""
echo "=== ERROR: test_ lines ==="
grep -nE 'ERROR: test_|ERROR: setUpClass|ERROR: tearDownClass' "$LOG" | tail -20

echo ""
echo "=== Traceback line numbers ==="
grep -n 'Traceback (most recent call last)' "$LOG" | tail -10

echo ""
echo "=== First ERROR block (adjust START if needed) ==="
START=$(grep -n 'Traceback (most recent call last)' "$LOG" | tail -4 | head -1 | cut -d: -f1)
if [[ -n "${START:-}" ]]; then
  sed -n "${START},$((START + 55))p" "$LOG"
else
  echo "(no Traceback found)"
fi
