# Odoo.sh: dev green, production (`real`) red

## No SSH shell?

Use **`docs/ODOO_SH_BUILD_LOG_ONLY.md`** — diagnose from the **Build log in the browser** only.

---

## Git branches (check first)

| Branch | Role |
|--------|------|
| **`main`** | Development |
| **`real`** | Production on Odoo.sh |
| **`production`** | Legacy name — must match `main` (`git push origin main:production`) |

GitHub: `main` and `real` must show the **same commit SHA**.

Odoo.sh → **Settings** → production branch = **`real`**.

---

## Same commit, different result?

| Cause | Dev | Production |
|--------|-----|------------|
| Database | Lighter / reset often | Many RDA lines, real master data |
| Install time | Shorter | Upgrade + tests on large DB → **KILLED** possible |
| Stale Git branch | `main` latest | Was `production` @ old SHA — fixed by aligning branches |

---

## Find the error (browser)

Odoo.sh → branch **`real`** → latest **red** build → step **Test** or **Install** → search:

`FAIL:` · `AssertionError` · `Traceback` · `ParseError` · `have the same label` · `KILLED`

Copy the surrounding lines if you need help.

---

## Fixes already in the codebase

| Test / symptom | Fix |
|----------------|-----|
| Bulk wizard `1009 != 1` | Domain pinned to test line id |
| Budget `'warning' != 'over'` | Forced PO `price_unit` for red band |
| Delivery standard assertions | QA-only routes `SBU_QA_LA` / `SBU_QA_VC` (no prod rule edits) |
| Slow install on prod | `post_init_hook` skips mass user/BOM work when `--test-enable` |
| SAL name migration | Batched 500 rows (not `search([])` on full table) |

---

## After green build

Update SBU apps from **Apps** (or your usual upgrade path). **Ctrl+F5** in the browser.

Optional: `sbu_purchase_flow`, `sbu_estimate` upgrade if views/translations changed.
