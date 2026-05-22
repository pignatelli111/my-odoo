#!/bin/bash
# Shortcut when SSH lands in $HOME (script lives in the git repo).
REPO="${ODOO_SH_USER_REPO:-/home/odoo/src/user}"
if [[ -x "$REPO/tools/grep_odoo_sh_test_fail.sh" ]]; then
  exec bash "$REPO/tools/grep_odoo_sh_test_fail.sh" "$@"
fi
if [[ -x "$REPO/tools/odoo_sh_why_build_failed.sh" ]]; then
  exec bash "$REPO/tools/odoo_sh_why_build_failed.sh" "$@"
fi
echo "Missing scripts under $REPO/tools — build may not have deployed latest commit yet." >&2
exit 1
