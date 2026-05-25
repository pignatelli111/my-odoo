# Odoo.sh: dev green, production (`real`) red

## No SSH shell?

Use **`docs/ODOO_SH_BUILD_LOG_ONLY.md`** — diagnose from the **Build log in the browser** only.

**Instant KILLED + Shell disabled:** run **`docs/ODOO_SH_REAL_SQL_FIX.md`** first (SQL button on branch **`real`**).

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
| Install time | Shorter | **Upgrades your live DB** (not a fresh test DB) → **KILLED** if RAM runs out |
| Stored field on big tables | N/A | e.g. `store=True` on all RDA lines → full recompute → **KILLED** |
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
| Prod **KILLED** after “Confirmed for PO” list filter | `technical_confirmed` on PR lines is **not stored** (writable compute only) |
| Shell greyed out | Normal while build is **KILLED** / failed — wait for **green** build |
| **KILLED** in a few seconds, no log progress | Production DB still has **`sbu_ui_help` installed** but addon was missing from git → restore stub + auto-uninstall (`19.0.1.0.10`) |
| UI label **Test Failed** on Production | Misleading: production builds **load your live DB**, they do not run the dev test suite |

---

## After green build

Update SBU apps from **Apps** (or your usual upgrade path). **Ctrl+F5** in the browser.

Optional: `sbu_purchase_flow`, `sbu_estimate` upgrade if views/translations changed.
