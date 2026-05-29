# Odoo.sh production (`real`) — instant KILLED, Shell disabled

When every new build on **`real`** shows **KILLED** in a few seconds and **Shell** is greyed out, the **live production database** is still broken. Failed builds do not get a working Shell.

Fix the **database first** with the **SQL** button, then **Rebuild**.

## Step 1 — Use SQL (not Shell)

1. Open [Odoo.sh](https://www.odoo.sh/) → project **my-odoo** → branch **`real`**.
2. At the top (next to SSH), click **SQL** — this uses the **current production database**, not the failed build container.
3. Paste and run the script from **`tools/sql/odoo_sh_uninstall_sbu_ui_help.sql`** (run each block, or all at once).
4. The last `SELECT` must show **`state = uninstalled`** for `sbu_ui_help`.

If `sbu_ui_help` is already `uninstalled`, continue to Step 2 anyway.

## Step 2 — Rebuild

1. On branch **`real`**, click **Rebuild** (wait until no build is in progress).
2. Wait for commit **`4a4e1c8`** or newer on the build.
3. A **green** build enables **Shell** again.

## Step 3 — After green

- Browser: **Ctrl+F5**
- **Apps** → upgrade **SBU Estimate** / **SBU Purchase Flow** if needed

## Why this happens

| Symptom | Cause |
|--------|--------|
| **KILLED** in seconds | Build worker dies loading/upgrading the **production DB** (RAM), or an addon left **installed** while missing from git |
| **Test Failed** on Production | Misleading label — production does **not** run the dev test suite; it **loads your live DB** |
| Shell disabled | Only **successful** builds get Shell on that container |

Removing **`sbu_ui_help`** from git without uninstalling it in the DB leaves the module **installed** → startup fails or is killed. Git stubs alone are not enough until the DB row is **`uninstalled`**.

## If still KILLED after SQL

1. Open the red build → **Logs** / **Install** → copy the **last 40 lines** (search `CRITICAL`, `MemoryError`, `KILLED`, `Traceback`).
2. In **Settings**, confirm Odoo version is **19.0** (not 13/15).
3. Check **Settings** → disable **Run tests** on production if that option exists.
