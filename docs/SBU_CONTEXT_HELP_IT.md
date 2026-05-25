# SBU context help (removed)

The **`sbu_ui_help`** module (floating **?** button, systray **Screen help**, RPC on every screen) was **removed** because it caused **memory pressure and container kills** on Odoo.sh production.

A **minimal stub** (no JS/assets) may stay in git until production DB rows are cleaned. **Uninstall in the database** via **`docs/ODOO_SH_REAL_SQL_FIX.md`** (Odoo.sh **SQL** button on branch **`real`**).

## After deploy

1. Run **`tools/sql/odoo_sh_uninstall_sbu_ui_help.sql`** on Odoo.sh **SQL** (see **`docs/ODOO_SH_REAL_SQL_FIX.md`**).
2. **Rebuild** branch **`real`** until green.
3. **Ctrl+F5** in the browser.

## User documentation

Use **`docs/guide/`** and **`docs/presentazione-cliente/`** for training material instead of in-app help.
