# Odoo.sh: dev test OK, production test failed

`main` and `production` point to the **same commit** — the difference is almost always **environment**, not different code.

## Typical causes

| Cause | Dev | Production |
|--------|-----|------------|
| **Database** | Fresh / dev copy, few modules | Long-lived DB, more installed modules |
| **Build log** | Tests in `install.log` or `odoo.log` | Same, but path differs |
| **Module upgrade** | Often `-u` on already-installed SBU | Full `-i` or upgrade on old schema |
| **Field type change** | New DB accepts new fields | Old `many2many` → `one2many` same name **breaks upgrade** |
| **0 tests run** | SBU modules installed | SBU only `-u` → **0 tests** (looks like “failed”) |

## 1) On the **production** Odoo.sh shell

```bash
cd ~/src/user
git log -1 --oneline
git branch --show-current   # expect: production

bash tools/grep_odoo_sh_test_fail.sh
bash tools/odoo_sh_why_build_failed.sh
```

Paste the lines that show:
- `FAIL: Test...`
- `odoo.tests.result: N failed`
- `ParseError` / `ValidationError` / `TypeError` / `Invalid field`

## 2) Re-run tests on production DB

```bash
bash tools/odoo_sh_run_tests.sh
grep -E 'FAIL:|odoo.tests.result' /tmp/sbu-test.log | tail -15
```

Success: `0 failed, 0 error(s) of N tests` with **N > 0**.

## 3) If grep is empty but build is red

- Open Odoo.sh → **production** branch → latest build → **full log**.
- Search: `FAIL:`, `AssertionError`, `have the same label`, `failed to load registry`.

## 4) Fix applied (purchase_order_ids)

`purchase_order_ids` was briefly changed from **Many2many** to **One2many**; that can break **production upgrade** on an existing database. It is restored as **Many2many** with an explicit relation table; PO still sets `sbu_purchase_request_id` and syncs the M2M.

Upgrade **`sbu_purchase_flow`** and **`sbu_estimate`** on production after the fix commit.

## Example: 2 failures on a real production DB (May 2026)

| Test | Symptom | Cause |
|------|---------|--------|
| `test_bulk_apply_filtered_domain_without_selection` | `1009 != 1` | Domain `[('request_type','=','rda')]` matched **all** RDA lines in prod, not only the test project |
| `test_budget_check_blocks_when_over_budget` | `'warning' != 'over'` | PO subtotal landed in the **90–105%** yellow band (pricelist / rounding), not clearly red |

Fix: scope bulk domain by `request_id.project_id`; use a smaller planned budget and force `price_unit` in the budget test.

**Stale shell checkout:** if `git log -1` on the Odoo.sh shell shows an old commit (e.g. `4dc3ef6`) while GitHub `production` is newer, wait for the build to deploy or run `git pull` in `~/src/user` after the green build.
