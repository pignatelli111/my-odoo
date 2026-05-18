#!/bin/bash
# Run on Odoo.sh SSH (bash, not Python). Shows custom-module WARNING lines from install.log.
set -euo pipefail
LOG="${1:-/home/odoo/logs/install.log}"
if [[ ! -f "$LOG" ]]; then
  echo "Missing log: $LOG" >&2
  exit 1
fi
echo "=== SBU / user addon WARNING lines (excluding Odoo core noise) ==="
grep WARNING "$LOG" \
  | grep -v 'odoo.tools.config: missing --http-interface' \
  | grep -v 'werkzeug' \
  | grep -E 'sbu_|/home/odoo/src/user|Fields with the same label|compute method|should not be' \
  | tail -80
echo ""
echo "=== Count ==="
grep WARNING "$LOG" \
  | grep -v 'odoo.tools.config: missing --http-interface' \
  | grep -E 'sbu_|/home/odoo/src/user|Fields with the same label|compute method|should not be' \
  | wc -l
