# Odoo.sh: dev test OK, production test failed

## Git branches (check this first)

| Branch | Role | Must match for green prod |
|--------|------|---------------------------|
| **`main`** | Development on Odoo.sh | Latest fixes |
| **`real`** | Production deploy (pushed with `git push origin main:real`) | **Same commit as `main`** |
| **`production`** | Legacy name in some docs / old Odoo.sh settings | Often **behind** — update it |

Verify on GitHub:

```text
main        → 63fbffd (example)
real        → 63fbffd  (same SHA)
production  → must not be 5c9156d or older
```

On Odoo.sh: **Project → Settings → Production branch** must track **`real`** (or `main`), not a stale `production` ref.

If production build uses old code while dev uses `main`, you get **different test results on the same day**.

---

## Same commit, different result?

Then the difference is almost always **environment**, not different code.

| Cause | Dev | Production |
|--------|-----|------------|
| **Database** | Fresh / dev copy, few modules | Long-lived DB, more PR lines, edited delivery rules |
| **Module upgrade** | Often clean `-i` | Upgrade on old schema |
| **Build time** | Shorter | Heavier DB → **KILLED** timeout possible |
| **0 tests run** | SBU modules installed | SBU only `-u` → **0 tests** (looks like “failed”) |

---

## 1) On the **production** Odoo.sh shell

```bash
cd ~/src/user
git log -1 --oneline
git branch --show-current

bash tools/grep_odoo_sh_test_fail.sh
bash tools/odoo_sh_why_build_failed.sh
```

Paste the lines that show:

- `FAIL: Test...`
- `odoo.tests.result: N failed`
- `ParseError` / `ValidationError` / `TypeError` / `Invalid field`

---

## 2) Re-run tests on production DB

```bash
bash tools/odoo_sh_run_tests.sh
grep -E 'FAIL:|odoo.tests.result' /tmp/sbu-test.log | tail -15
```

Success: `0 failed, 0 error(s) of N tests` with **N > 0**.

---

## 3) If grep is empty but build is red

- Open Odoo.sh → **production** branch → latest build → **full log**.
- Search: `FAIL:`, `AssertionError`, `have the same label`, `failed to load registry`, `KILLED`.

---

## 4) Known prod-DB test failures (fixed in repo)

| Test | Symptom | Cause |
|------|---------|--------|
| `test_bulk_apply_filtered_domain_without_selection` | `1009 != 1` | Domain `[('request_type','=','rda')]` matched **all** RDA lines in prod |
| `test_budget_check_blocks_when_over_budget` | `'warning' != 'over'` | PO subtotal in yellow band; fixed with forced `price_unit` |
| `test_la_line_gets_sistemista_terzista_path` | Partner name not in `destination` | Prod DB had **extra/edited** delivery standards winning over test data |

Fixes: pin bulk domain to `('id', '=', line_rda.id)`; budget test forces red amount; delivery tests **deactivate** existing rules for the class.

---

## 5) Align `production` branch on GitHub (if Odoo.sh still uses it)

```bash
git push origin main:production
```

Then trigger a new production build on Odoo.sh.

---

## 6) `purchase_order_ids` (upgrade)

`purchase_order_ids` is **Many2many** (not One2many). After deploy, upgrade:

`sbu_purchase_flow`, `sbu_estimate`

---

**Stale shell:** `~/src/user` is read-only until a **green** build. Use the **Build log** in the browser for the latest red run.
