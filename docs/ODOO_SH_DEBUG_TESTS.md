# Odoo.sh — debug build / SBU tests

## `/tmp/sbu-test.log` missing

That file is created **only** when you run:

```bash
bash ~/src/user/tools/odoo_sh_run_tests.sh
```

It is **not** created by the normal Odoo.sh web build alone.

---

## Read the real error from `install.log`

Your log shows `Traceback` around line **1964**, but `sed -n '1680,1760p'` stops **before** that line. Use:

```bash
grep -nE "Traceback|ParseError|AssertionError|FAIL:|ERROR.*test_|cannot be located|Invalid view" ~/logs/install.log | tail -40
```

Then print the full traceback (replace `1964` with the line number grep shows):

```bash
sed -n '1960,2040p' ~/logs/install.log
```

---

## After a green git deploy

```bash
cd ~/src/user
git log -1 --oneline

bash tools/odoo_sh_run_tests.sh

grep -nE 'FAIL:|ERROR: test_|AssertionError|ParseError' /tmp/sbu-test.log | tail -40
grep -E 'odoo\.tests\.result:' /tmp/sbu-test.log | tail -5
```

---

## Typical SBU failures (recent)

| Symptom | Cause |
|---------|--------|
| `decoration-secondary` | Invalid on `<list>` in Odoo 19 — use `decoration-muted` |
| `cannot be located` on `sbu_estimate_id` in view | Field used in `invisible=` but not present in inherited form |
| Owl `Dropdown` / reading `'0'` | `widget="badge"` with `in (...)` in decoration |
| `0 tests` in log | Modules not installed/upgraded — run `-u` on SBU modules first |
