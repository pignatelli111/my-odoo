#!/bin/bash
# Shortcut on Odoo.sh: bash ~/src/user/check_build.sh
exec bash "$(dirname "$0")/tools/grep_odoo_sh_test_fail.sh" "$@"
