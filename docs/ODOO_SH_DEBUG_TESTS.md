# Odoo.sh — catch build / test failures (correct shell steps)

Run **one block at a time**. Do not paste multiple commands on one line (no `git log -1pwd`).

On Odoo.sh, `~/src/user` is **read-only** until a build is **green**. Do **not** use `git pull` in the shell.

---

## Step 0 — Which code is on this shell?

```bash
cd ~/src/user
git log -1 --oneline
```

Compare with GitHub `main` / `real` (e.g. `46d37b9`). If older, the shell still has the **last green** deploy; a **red** build log may only appear in **Odoo.sh → Builds** in the browser.

---

## Step 1 — Which database?

```bash
echo "DB=$PGDATABASE"
```

---

## Step 2 — Find the error line in install.log

```bash
grep -nE 'Traceback \(most recent|ParseError|AssertionError|FAIL:|ERROR: test_|cannot be located|Invalid view|Could not load module|have the same label|CRITICAL' \
  ~/logs/install.log | tail -50
```

Note the **line number** of the last `Traceback` (example: `1964`).

---

## Step 3 — Print the full traceback (replace 1964)

```bash
TB_LINE=1964
sed -n "$((TB_LINE - 5)),$((TB_LINE + 80))p" ~/logs/install.log
```

If `TB_LINE` is wrong, pick the number from step 2.

---

## Step 4 — What was loading when it broke?

```bash
grep -n 'loading sbu_' ~/logs/install.log | tail -25
```

The **last** `loading sbu_...` line before the Traceback is the module/view to fix.

---

## Step 5 — Live odoo.log (runtime, optional)

```bash
grep -nE 'Traceback|ParseError|AssertionError|FAIL:|ERROR: test_' ~/logs/odoo.log | tail -30
```

---

## Step 6 — Run SBU tests and create `/tmp/sbu-test.log`

Only after `tools/odoo_sh_run_tests.sh` exists on this commit:

```bash
test -f ~/src/user/tools/odoo_sh_run_tests.sh && echo OK || echo "Script missing — wait for green build with tools/"
```

```bash
bash ~/src/user/tools/odoo_sh_run_tests.sh
```

If the script is missing, use the manual block:

```bash
cd ~/src/user
DB="${PGDATABASE}"
ADDONS="/home/odoo/src/user,/home/odoo/src/odoo/addons,/home/odoo/src/odoo/odoo/addons"
test -d /home/odoo/src/enterprise && ADDONS="/home/odoo/src/enterprise,${ADDONS}"
ODOO="/home/odoo/src/odoo/odoo-bin"
MODULES="sbu_stock_config,sbu_estimate,sbu_purchase_flow,sbu_sal,sbu_project,sbu_documents,sbu_closure,sbu_integrations,sbu_logikal,sbu_mail_ingest,sbu_qonto,sbu_revolut"
TAGS="/sbu_estimate,/sbu_purchase_flow,/sbu_sal,/sbu_stock_config,/sbu_closure,/sbu_qonto,/sbu_logikal,/sbu_documents,/sbu_project,/sbu_integrations,/sbu_mail_ingest,/sbu_revolut"

python3 "$ODOO" shell -d "$DB" --addons-path="$ADDONS" --stop-after-init <<'PY'
names = 'sbu_estimate,sbu_purchase_flow,sbu_sal,sbu_stock_config,sbu_project,sbu_documents,sbu_closure,sbu_logikal'.split(',')
imm = env['ir.module.module'].search([('name', 'in', names), ('state', '=', 'installed')])
for m in names:
    r = imm.filtered(lambda x: x.name == m)[:1]
    print(m, r.state if r else 'missing', r.latest_version if r else '')
if imm:
    imm.write({'state': 'to upgrade'})
    print('marked_to_upgrade:', ','.join(imm.mapped('name')))
PY

python3 "$ODOO" -d "$DB" --addons-path="$ADDONS" -u "$MODULES" \
  --test-enable --stop-after-init --log-level=test --test-tags "$TAGS" \
  2>&1 | tee /tmp/sbu-test.log
echo "EXIT=$?"
```

---

## Step 7 — Read test results from `/tmp/sbu-test.log`

```bash
test -f /tmp/sbu-test.log && echo "log exists" || echo "log missing — run step 6 first"
```

```bash
grep -nE 'FAIL:|ERROR: test_|AssertionError|ParseError|cannot be located|Could not load module|Traceback \(most recent' \
  /tmp/sbu-test.log | tail -50
```

```bash
grep -E 'odoo\.tests\.result:' /tmp/sbu-test.log | tail -5
```

```bash
grep -E 'odoo\.tests\.stats: sbu_' /tmp/sbu-test.log | tail -20
```

If you see `0 failed, 0 error(s) of 0 tests` — tests did not run; read the Traceback **above** in the same file:

```bash
grep -n 'Traceback (most recent' /tmp/sbu-test.log | tail -3
```

Use the line number with `sed` (same as step 3, file `/tmp/sbu-test.log`).

---

## Step 8 — One-shot “copy everything useful” (paste to developer)

```bash
{
  echo "=== commit ==="
  git -C ~/src/user log -1 --oneline
  echo "=== DB ==="
  echo "$PGDATABASE"
  echo "=== install.log errors ==="
  grep -nE 'Traceback|ParseError|AssertionError|FAIL:|ERROR: test_|cannot be located|have the same label' ~/logs/install.log | tail -30
  echo "=== last sbu load ==="
  grep -n 'loading sbu_' ~/logs/install.log | tail -15
  echo "=== sbu-test.log (if any) ==="
  test -f /tmp/sbu-test.log && grep -nE 'FAIL:|ERROR: test_|Traceback|ParseError|odoo.tests.result' /tmp/sbu-test.log | tail -30 || echo "(no /tmp/sbu-test.log)"
} 2>&1
```

---

## If shell logs are empty but Odoo.sh build is red

The failed build log is often **only** in the web UI:

**Odoo.sh → your project → Builds → latest red build → open log for step “Test” or “Install”** → search `Traceback`, `ParseError`, `FAIL:`.

The SSH `install.log` can still reflect an **older successful** install.

---

## Build button says **KILLED** (not CONNECT)

On Odoo.sh this often means the **test/install process was stopped** (time or memory limit), not necessarily a failing assertion.

1. Open the **red build in the browser** (not only SSH `install.log`) and scroll to the **last lines** of the Test step.
2. If you see `Traceback`, `ParseError`, or `FAIL:` → fix that code error.
3. If the log **stops mid-test** with no traceback → **Retry** the build once; `338f22c`-style commits bump `sbu_estimate` and rerun the full `-i` + test suite (slow).
4. On shell after a new build:

```bash
bash ~/src/user/tools/odoo_sh_why_build_failed.sh
```
