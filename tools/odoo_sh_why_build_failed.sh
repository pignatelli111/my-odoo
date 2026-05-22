#!/bin/bash
# Find why Odoo.sh marks the build failed when grep for FAIL:/ERROR: test_ is empty.
# Usage: bash /home/odoo/src/user/tools/odoo_sh_why_build_failed.sh
set -uo pipefail
INSTALL_LOG="${1:-/home/odoo/logs/install.log}"
ODOO_LOG="${2:-/home/odoo/logs/odoo.log}"
USER_REPO="${USER_REPO:-/home/odoo/src/user}"

echo "=== Git commit on this container ==="
git -C "$USER_REPO" log -1 --oneline 2>/dev/null || echo "(no git)"

echo ""
echo "=== 1) Final lines of install.log (exit reason often here) ==="
tail -25 "$INSTALL_LOG" 2>/dev/null || echo "missing $INSTALL_LOG"

echo ""
echo "=== 2) Test summary lines (any module) ==="
grep -nE 'odoo\.tests\.result:|failures=[1-9]| errors=[1-9]|failed, [1-9]|error\(s\) of [1-9]' \
  "$INSTALL_LOG" "$ODOO_LOG" 2>/dev/null | tail -25 || echo "(none)"

echo ""
echo "=== 3) SBU test stats ==="
grep -nE 'odoo\.tests\.stats: sbu_|addons\.sbu_.*tests' \
  "$INSTALL_LOG" "$ODOO_LOG" 2>/dev/null | tail -20 || echo "(none)"

echo ""
echo "=== 4) Tracebacks / CRITICAL / ParseError / ValidationError ==="
grep -nE 'Traceback \(most recent|CRITICAL|ParseError|ValidationError|Table name .{60,} is too long|Failed to initialize database' \
  "$INSTALL_LOG" "$ODOO_LOG" 2>/dev/null | tail -25 || echo "(none)"

echo ""
echo "=== 5) SBU-related ERROR lines (not only test_) ==="
grep -nE 'ERROR.*sbu_|ERROR.*src/user' "$INSTALL_LOG" "$ODOO_LOG" 2>/dev/null | tail -25 || echo "(none)"

echo ""
echo "=== 6) Duplicate field labels (Odoo.sh may fail build) ==="
grep -n 'have the same label' "$INSTALL_LOG" "$ODOO_LOG" 2>/dev/null | grep -E 'sbu_|src/user' | tail -15 || echo "(none)"

echo ""
echo "=== 7) SBU WARNING lines ==="
grep WARNING "$INSTALL_LOG" 2>/dev/null \
  | grep -v 'missing --http-interface' \
  | grep -v 'werkzeug' \
  | grep -v 'not installable, skipped' \
  | grep -v 'ir_mail_server' \
  | grep -E 'sbu_|src/user' | tail -20 || echo "(none)"
echo "Total WARNING in install.log: $(grep -c WARNING "$INSTALL_LOG" 2>/dev/null || echo 0)"

echo ""
echo "=== 8) Module install failures ==="
grep -nE 'Could not load module|Module .* failed|Unable to install|AssertionError' \
  "$INSTALL_LOG" 2>/dev/null | tail -15 || echo "(none)"

echo ""
echo "=== 9) Reproduce full Odoo.sh SBU install+test (optional, ~2–5 min) ==="
echo "bash $USER_REPO/tools/odoo_sh_test_sbu_install.sh /home/odoo/tmp/sbu-repro.log"
