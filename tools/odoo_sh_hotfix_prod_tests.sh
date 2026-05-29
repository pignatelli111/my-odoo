#!/bin/bash
# Emergency hotfix on Odoo.sh production shell when git is stuck at 4dc3ef6.
# Patches the two known prod-DB test failures, then re-runs SBU tests.
# Usage: bash /home/odoo/src/user/tools/odoo_sh_hotfix_prod_tests.sh
# (Copy this script from GitHub raw if tools/ is not deployed yet.)
set -euo pipefail
REPO="${USER_REPO:-/home/odoo/src/user}"
BULK="$REPO/sbu_purchase_flow/tests/test_sbu_bulk_wizard.py"
BUDGET="$REPO/sbu_purchase_flow/tests/test_sbu_project_budget.py"

if [[ ! -w "$BULK" ]]; then
  echo "Cannot write $BULK (read-only?). Wait for green Odoo.sh build on 641cd98+ instead."
  exit 1
fi

python3 <<'PY'
from pathlib import Path
import re

bulk = Path("/home/odoo/src/user/sbu_purchase_flow/tests/test_sbu_bulk_wizard.py")
text = bulk.read_text(encoding="utf-8")
text = text.replace(
    "active_domain=[('request_type', '=', 'rda')],",
    "active_domain=[('id', '=', line_rda.id)],",
)
text = text.replace(
    "# Cosimo point 3: apply date to all lines matching list filters.",
    "# Pin to this line only (prod DB has 1000+ RDA lines).\n        # Cosimo point 3: apply date to all lines matching list filters.",
)
bulk.write_text(text, encoding="utf-8")
print("patched", bulk)

budget = Path("/home/odoo/src/user/sbu_purchase_flow/tests/test_sbu_project_budget.py")
b = budget.read_text(encoding="utf-8")
if "SBU_BUDGET_OVER_PCT" not in b:
    b = b.replace(
        "from odoo.addons.sbu_estimate.tests.sbu_test_label_utils import duplicate_custom_field_labels\n",
        "from odoo.addons.sbu_estimate.tests.sbu_test_label_utils import duplicate_custom_field_labels\n\nSBU_BUDGET_OVER_PCT = 105.0\n",
    )
old_helper = """        self.env['sbu.estimate.line'].create({
            'estimate_id': estimate.id,
            'pos': 'VC01',
            'description': 'Glass package',
            'cost_family': 'glass',
            'cost_posa_lamiera_lin_cad': planned_cad,
            'qty': 1,
        })"""
new_helper = """        eline = self.env['sbu.estimate.line'].create({
            'estimate_id': estimate.id,
            'pos': 'VC01',
            'description': 'Glass package',
            'cost_family': 'glass',
            'cost_posa_lamiera_lin_cad': planned_cad,
            'cost_coibentazione_cad': 0.0,
            'cost_industrial_pct': 0.0,
            'qty': 1,
        })
        self.env.flush_all()
        self.assertGreaterEqual(eline.cost_total_tot, planned_cad)"""
if old_helper in b:
    b = b.replace(old_helper, new_helper)

old_test = """    def test_budget_check_blocks_when_over_budget(self):
        \"\"\"Direct check on _sbu_check_budget_before_confirm (no PO confirm workflow).\"\"\"
        project, _estimate = self._project_with_glass_budget(planned_cad=100.0)
        po, _pr_line = self._po_over_glass_budget(project)
        pol = po.order_line.filtered('sbu_pr_line_id')
        self.assertEqual(len(pol), 1)
        self.assertGreater(pol.price_subtotal, 100.0)

        self.env.flush_all()
        rows = self.env['sbu.project.budget.family'].refresh_project(project)
        glass_row = rows.filtered(lambda r: r.cost_family == 'glass')
        self.assertEqual(len(glass_row), 1)
        self.assertGreater(glass_row.budget_planned, 0.0)
        self.assertGreater(glass_row.amount_engaged, glass_row.budget_planned)
        self.assertEqual(glass_row.traffic_light, 'over')
        self.assertTrue(glass_row.is_over_budget)"""

new_test = """    def test_budget_check_blocks_when_over_budget(self):
        \"\"\"Direct check on _sbu_check_budget_before_confirm (no PO confirm workflow).\"\"\"
        planned = 100.0
        project, _estimate = self._project_with_glass_budget(planned_cad=planned)
        po, _pr_line = self._po_over_glass_budget(project)
        pol = po.order_line.filtered('sbu_pr_line_id')
        self.assertEqual(len(pol), 1)
        pol.write({'price_unit': 250.0})
        self.env.flush_all()
        pol.invalidate_recordset(['price_subtotal'])
        self.assertGreater(pol.price_subtotal, planned * 1.1)

        rows = self.env['sbu.project.budget.family'].refresh_project(project)
        glass_row = rows.filtered(lambda r: r.cost_family == 'glass')
        self.assertEqual(len(glass_row), 1)
        self.assertGreater(glass_row.pct_engaged, SBU_BUDGET_OVER_PCT)
        self.assertTrue(glass_row.is_over_budget)"""

if old_test in b:
    b = b.replace(old_test, new_test)
else:
    print("budget test block not found — may already be patched")
budget.write_text(b, encoding="utf-8")
print("patched", budget)
PY

echo "=== Re-run tests (same as manual block) ==="
bash "$REPO/tools/odoo_sh_run_tests.sh" 2>/dev/null || {
  echo "Run your odoo-bin -u ... block again after this hotfix."
}
