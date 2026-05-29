#!/bin/bash
# Odoo.sh marks a build YELLOW when install.log contains WARNING lines (even if tests pass).
# SBU may be clean while core Odoo / pip still emit warnings → almost-successful build.
#
# Usage on Odoo.sh shell:
#   bash ~/src/user/tools/odoo_sh_why_build_warning.sh
#   bash ~/src/user/tools/odoo_sh_why_build_warning.sh ~/logs/install.log
set -uo pipefail

INSTALL_LOG="${1:-}"
if [[ -z "$INSTALL_LOG" ]]; then
  for candidate in ~/logs/install.log /home/odoo/logs/install.log; do
    if [[ -f "$candidate" ]]; then
      INSTALL_LOG="$candidate"
      break
    fi
  done
fi
if [[ -z "$INSTALL_LOG" || ! -f "$INSTALL_LOG" ]]; then
  echo "No install.log found. Pass path: bash $0 ~/logs/install.log" >&2
  exit 1
fi

echo "=== Log file ==="
echo "$INSTALL_LOG"
echo "Commit: $(git -C ~/src/user log -1 --oneline 2>/dev/null || echo '?')"
echo ""

echo "=== Test result (must be 0 failed for a healthy SBU run) ==="
grep 'odoo.tests.result:' "$INSTALL_LOG" | tail -3 || echo "(no test summary in this log)"
echo ""

TOTAL=$(grep -c WARNING "$INSTALL_LOG" 2>/dev/null || echo 0)
NOISE=$(grep WARNING "$INSTALL_LOG" 2>/dev/null \
  | grep -cE 'werkzeug|missing --http-interface|not installable, skipped|ir_mail_server' || echo 0)
SBU=$(grep WARNING "$INSTALL_LOG" 2>/dev/null \
  | grep -v 'missing --http-interface' \
  | grep -v 'werkzeug' \
  | grep -cE 'sbu_|/home/odoo/src/user|Fields with the same label|have the same label|compute method|should not be' || echo 0)

echo "=== WARNING counts ==="
echo "Total WARNING lines:     $TOTAL"
echo "Likely noise (filtered): $NOISE"
echo "SBU / custom-module:     $SBU"
echo ""

if [[ "$SBU" -eq 0 ]]; then
  echo "VERDICT: SBU tests and custom-module warnings look CLEAN in this log."
  echo "Odoo.sh yellow badge = at least one WARNING somewhere in the build (often core Odoo)."
  echo "Open Builds → latest build → compare Install vs Test step logs in the browser."
else
  echo "VERDICT: Fix SBU/custom WARNING lines below, then rebuild."
fi
echo ""

echo "=== SBU / duplicate-label WARNING lines ==="
grep WARNING "$INSTALL_LOG" \
  | grep -v 'missing --http-interface' \
  | grep -v 'werkzeug' \
  | grep -E 'sbu_|/home/odoo/src/user|have the same label|Fields with the same|compute method|should not be' \
  | tail -40 || echo "(none)"
echo ""

echo "=== Remaining WARNING lines (core Odoo / pip — cause yellow if any) ==="
grep WARNING "$INSTALL_LOG" \
  | grep -v 'missing --http-interface' \
  | grep -v 'werkzeug' \
  | grep -v 'not installable, skipped' \
  | grep -v 'ir_mail_server' \
  | grep -vE 'sbu_|/home/odoo/src/user|have the same label|Fields with the same|compute method|should not be' \
  | tail -50 || echo "(none after filters)"
echo ""

echo ""
echo "=== Unique WARNING sources (deduped logger names) ==="
grep WARNING "$INSTALL_LOG" \
  | grep -v 'missing --http-interface' \
  | grep -v 'werkzeug' \
  | sed -E 's/^[0-9]+://' \
  | sed -E 's/^[^ ]+ [^ ]+ [0-9]+ //' \
  | sed -E 's/ .+$//' \
  | sort -u \
  | tail -40 || true

echo ""
echo "=== Known SBU yellow-build patterns (fixed in 19.0.1.0.114+) ==="
echo "1) openpyxl UserWarning: Cannot parse header or footer (P1002 / ANACO xlsx import)"
echo "2) docutils (WARNING/2) Block quote ends without a blank line (field help / RST noise)"
echo "After rebuild: grep -c WARNING ~/logs/install.log  should be 0 for green build."
