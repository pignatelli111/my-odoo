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
echo "=== Test failures (install.log) ==="
grep -nE 'FAIL:|ERROR: test_|AssertionError|failures=[1-9]| errors=[1-9]' "$LOG" | tail -30 || echo "(none)"
echo ""
echo "=== Test failures (odoo.log — Odoo.sh often logs tests here) ==="
ODOO_LOG="${2:-/home/odoo/logs/odoo.log}"
if [[ -f "$ODOO_LOG" ]]; then
  grep -nE 'FAIL:|ERROR: test_|AssertionError|Traceback \(most recent' "$ODOO_LOG" | tail -30 || echo "(none)"
else
  echo "(no $ODOO_LOG)"
fi
echo ""
echo "=== Tracebacks / critical ==="
grep -nE 'Traceback|CRITICAL|ParseError|ValidationError|Invalid field' "$LOG" | tail -20 || echo "(none)"
echo ""
echo "=== Odoo 19 invalid XML fields (e.g. groups_id on act_window) ==="
grep -nE "Invalid field 'groups_id'|Invalid field .groups_id" "$LOG" "$ODOO_LOG" 2>/dev/null | tail -10 || echo "(none)"
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
echo "=== SBU test stats (look for failures=N errors=N) ==="
grep -E 'odoo\.addons\.sbu_.*tests|odoo\.tests\.stats: sbu_|failures=[1-9]| errors=[1-9]' "$LOG" | tail -15 || echo "(none)"
echo ""
echo "=== Re-run SBU tests only (SSH) ==="
echo "python3 /home/odoo/src/odoo/odoo-bin -d \"\$PGDATABASE\" --addons-path=/home/odoo/src/user,/home/odoo/src/odoo/addons,/home/odoo/src/odoo/odoo/addons --test-enable --stop-after-init --log-level=test --test-tags /sbu_estimate,/sbu_purchase_flow,/sbu_sal 2>&1 | tail -80"
echo ""
echo "=== Total WARNING count in install.log (Odoo.sh may flag any) ==="
grep -c WARNING "$LOG" 2>/dev/null || echo 0
