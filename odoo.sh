#!/bin/bash
# Odoo.sh build hook: install Python deps for SBU Excel import (sbu_estimate).
set -euo pipefail
REQ="/home/odoo/src/user/requirements.txt"
if [[ -f "$REQ" ]]; then
    pip3 install -r "$REQ"
fi
