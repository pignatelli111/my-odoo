#!/bin/bash
# Run on Odoo.sh SSH (bash, not Python). Shows custom-module WARNING lines from install.log.
set -euo pipefail
LOG="${1:-/home/odoo/logs/install.log}"
if [[ ! -f "$LOG" ]]; then
  echo "Missing log: $LOG" >&2
  exit 1
fi
echo "=== SBU / user addon WARNING lines (excluding Odoo core noise) ==="
SBU_LINES=$(grep WARNING "$LOG" \
  | grep -v 'odoo.tools.config: missing --http-interface' \
  | grep -v 'werkzeug' \
  | grep -E 'sbu_|/home/odoo/src/user|Fields with the same label|have the same label|compute method|should not be' \
  | tail -80)
if [[ -n "$SBU_LINES" ]]; then
  echo "$SBU_LINES"
else
  echo "(none — SBU looks clean)"
fi
echo ""
echo "=== Counts ==="
echo -n "SBU/custom WARNING: "
grep WARNING "$LOG" \
  | grep -v 'odoo.tools.config: missing --http-interface' \
  | grep -v 'werkzeug' \
  | grep -E 'sbu_|/home/odoo/src/user|Fields with the same label|have the same label|compute method|should not be' \
  | wc -l
echo -n "Total WARNING in log: "
grep -c WARNING "$LOG" 2>/dev/null || echo 0
echo ""
echo "If SBU=0 but Odoo.sh is yellow, run: bash ~/src/user/tools/odoo_sh_why_build_warning.sh"
