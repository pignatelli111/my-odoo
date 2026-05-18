#!/bin/bash
# Run on Odoo.sh SSH after a failed build. Finds install/test failures (not only ParseError).
set -euo pipefail
LOG="${1:-/home/odoo/logs/install.log}"
if [[ ! -f "$LOG" ]]; then
  echo "Missing log: $LOG" >&2
  exit 1
fi
echo "=== Commit on this build ==="
git -C /home/odoo/src/user log -1 --oneline 2>/dev/null || true
echo ""
echo "=== Test / assert failures (FAIL: not FAILED) ==="
grep -nE 'FAIL:|ERROR: test_|AssertionError|failures=[1-9]| errors=[1-9]' "$LOG" | tail -40 || true
echo ""
echo "=== Tracebacks / critical ==="
grep -nE 'Traceback|CRITICAL|ParseError|ValidationError' "$LOG" | tail -30 || true
echo ""
echo "=== SBU UserWarnings (Odoo 19 ORM — often cause test: failed) ==="
grep -nE 'UserWarning: sbu\.|sbu_estimate|sbu_sal' "$LOG" | tail -40 || true
echo ""
echo "=== End of install.log (test summary) ==="
tail -25 "$LOG"
