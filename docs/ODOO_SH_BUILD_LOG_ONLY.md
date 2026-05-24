# Odoo.sh — red build without SSH shell

Use this when **SSH / webshell is disabled** on production (branch **`real`**).

## 1) Confirm the commit

1. Open [Odoo.sh](https://www.odoo.sh/) → project **pignatelli111** / **my-odoo**.
2. Open branch **`real`** (production).
3. Open the latest **red** build.
4. Note the **commit hash** (must match GitHub `real`, e.g. `…98`).

If the hash is older than GitHub `main` / `real`, wait for deploy or check that production tracks branch **`real`**, not legacy **`production`**.

## 2) Read the failure (browser only)

In the build page:

1. Open step **Test** (or **Install** if Test is empty).
2. Use the log search box (or Ctrl+F) for:
   - `FAIL:`
   - `AssertionError`
   - `Traceback`
   - `ParseError`
   - `have the same label`
   - `KILLED`

3. Copy **20–40 lines** around the first match and send them to support / developer.

## 3) Typical production-only causes (already fixed in repo)

| Pattern in log | Meaning |
|----------------|---------|
| `1009 != 1` on bulk wizard | Filter matched whole prod DB — fixed (pin line id) |
| `'warning' != 'over'` on budget | PO amount band — fixed (force `price_unit`) |
| Log stops with **KILLED** | Build timeout on heavy prod DB — hooks skip mass work during `--test-enable` |
| `have the same label` + `sbu.` | Duplicate field label — fix in code, then new build |

## 4) After a **green** build

In Odoo (browser): **Apps** → update **SBU** modules (`sbu_estimate`, `sbu_purchase_flow`, …) or use your usual `odoo-update` if shell is available on staging only.

Hard refresh: **Ctrl+F5**.

## 5) Branches

| Branch | Use |
|--------|-----|
| `main` | Development |
| `real` | Production deploy |
| `production` | Legacy — keep aligned with `main` (`git push origin main:production`) |

Shell scripts under `tools/` are **optional** when SSH is enabled; they are not required to diagnose a red build.
