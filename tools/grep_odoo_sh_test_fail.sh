#!/bin/bash
# Odoo.sh SSH: bash ~/src/user/tools/grep_odoo_sh_test_fail.sh
# (Script lives in the git repo under src/user, not in $HOME.)
set -euo pipefail
LOG="${1:-/home/odoo/logs/install.log}"
USER_REPO="${USER_REPO:-/home/odoo/src/user}"
if [[ ! -f "$LOG" ]]; then
  echo "Missing log: $LOG" >&2
  exit 1
fi
echo "=== Commit on this build ==="
git -C "$USER_REPO" log -1 --oneline 2>/dev/null || echo "(no git at $USER_REPO)"
echo ""
echo "=== Test failures ==="
grep -nE 'FAIL:|ERROR: test_|AssertionError|failures=[1-9]| errors=[1-9]' "$LOG" | tail -30 || echo "(none)"
echo ""
echo "=== Tracebacks / critical ==="
grep -nE 'Traceback|CRITICAL|ParseError|ValidationError' "$LOG" | tail -20 || echo "(none)"
echo ""
echo "=== SBU duplicate field labels (fix these for green build) ==="
grep -n 'have the same label' "$LOG" | grep -E 'sbu\.|Modules: sbu_' | tail -20 || echo "(none)"
echo ""
echo "=== Other SBU WARNING lines (ORM, compute, views) ==="
grep WARNING "$LOG" \
  | grep -v 'missing --http-interface' \
  | grep -v 'werkzeug' \
  | grep -v 'not installable, skipped' \
  | grep -v 'ir_mail_server' \
  | grep -E 'sbu_|/home/odoo/src/user' \
  | tail -30 || echo "(none)"
echo ""
echo "=== SBU test stats ==="
grep -E 'odoo\.addons\.sbu_.*tests|odoo\.tests\.stats: sbu_' "$LOG" | tail -10 || echo "(none)"
echo ""
echo "=== Total WARNING count in install.log (Odoo.sh may flag any) ==="
grep -c WARNING "$LOG" 2>/dev/null || echo 0
