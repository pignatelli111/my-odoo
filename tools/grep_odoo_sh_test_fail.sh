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
grep -nE 'FAIL:|ERROR: test_|AssertionError|failures=[1-9]| errors=[1-9]|failed, [1-9]|error\(s\) of [1-9]' "$LOG" | tail -30 || echo "(none)"
echo ""
echo "=== Test summary (install.log — any module) ==="
grep -nE 'odoo\.tests\.result:' "$LOG" | tail -10 || echo "(none)"
ZERO_TESTS=$(grep -c '0 failed, 0 error(s) of 0 tests' "$LOG" 2>/dev/null || echo 0)
if [[ "$ZERO_TESTS" -gt 0 ]]; then
  echo ""
  echo ">>> NOT GREEN: 0 tests executed (SBU modules likely uninstalled — -u alone does nothing)."
  echo ">>> Run: bash $USER_REPO/tools/odoo_sh_test_sbu_install.sh"
fi
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
grep -nE 'Traceback|CRITICAL|ParseError|ValidationError|Invalid field|Table name .{60,} is too long' "$LOG" | tail -20 || echo "(none)"
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
echo "=== Re-run SBU install+tests (SSH — auto -i or -u) ==="
echo "bash \$USER_REPO/tools/odoo_sh_test_sbu_install.sh /tmp/sbu-test.log"
echo "grep -E 'odoo.tests.result:|sbu_sal|FAIL:' /tmp/sbu-test.log | tail -20"
echo ""
echo "=== Total WARNING count in install.log (Odoo.sh may flag any) ==="
grep -c WARNING "$LOG" 2>/dev/null || echo 0
echo ""
echo "=== Last 15 lines of install.log (build exit reason) ==="
tail -15 "$LOG" 2>/dev/null || true
echo ""
if [[ -f /tmp/sbu-test.log ]]; then
  echo ""
  echo "=== /tmp/sbu-test.log (last manual repro) ==="
  grep -nE 'FAIL:|ERROR: test_|AssertionError|ParseError|odoo\.tests\.result:|odoo\.tests\.stats: sbu_|0 failed, 0 error' /tmp/sbu-test.log | tail -25 || echo "(no patterns)"
fi
echo ""
echo "=== Full diagnosis (when grep above is empty) ==="
echo "bash $USER_REPO/tools/odoo_sh_why_build_failed.sh"
