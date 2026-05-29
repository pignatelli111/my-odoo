# Odoo.sh shell — comandi quando `tools/` non esiste ancora

Se il build Odoo.sh è **rosso**, la shell usa ancora l’ultimo commit **verde** (`~/src/user` non ha i nuovi script).

## 1) Verifica commit in shell

```bash
cd ~/src/user
git log -1 --oneline
ls tools/odoo_sh_run_tests.sh 2>/dev/null || echo "script assente — build non ancora verde su questo commit"
```

**Non usare `git fetch` / `git checkout` sulla shell Odoo.sh** — il filesystem git è **read-only** (`Read-only file system`). Il codice in `~/src/user` cambia **solo** dopo un build **verde** su Odoo.sh. Fino ad allora resta l’ultimo commit deployato (es. `4dc3ef6`).

## 2) Perché `grep FAIL` è vuoto ma il build è rosso

Su Odoo.sh spesso succede questo:

1. **`~/logs/install.log` sulla shell** = ultimo install **riuscito** sul container, **non** per forza l’ultimo build rosso in UI.
2. Il build **Test** fallito può essere in un **altro step** (log solo nella pagina **Builds** del progetto).
3. Il fallimento può essere **WARNING** (etichette duplicate), **0 test eseguiti**, **Traceback upgrade**, non solo `FAIL:`.

Diagnostica completa (funziona anche senza `tools/`):

```bash
cd ~/src/user
echo "=== Commit deployato sulla shell (ultimo build VERDE) ==="
git log -1 --oneline

echo "=== Ultimo comando in install.log ==="
head -3 ~/logs/install.log

echo "=== Fine install.log ==="
tail -25 ~/logs/install.log

echo "=== Test / errori (pattern larghi) ==="
grep -nE 'FAIL:|ERROR: test_|AssertionError|odoo\.tests\.result:|failures=[1-9]|failed, [1-9]|have the same label|Traceback|CRITICAL|ParseError|Could not load module' \
  ~/logs/install.log ~/logs/odoo.log 2>/dev/null | tail -40

echo "=== SBU nel log? ==="
grep -c 'sbu_purchase_flow\|test-enable' ~/logs/install.log 2>/dev/null || echo 0
```

Se tutto è vuoto: apri **Odoo.sh → Builds → ultimo build rosso → log dello step Test / Install** e cerca `FAIL:` lì.

## 2b) Errore rapido (solo install.log)

```bash
grep -nE 'FAIL:|ERROR: test_|AssertionError|have the same label|odoo\.tests\.result:' ~/logs/install.log | tail -40
tail -20 ~/logs/install.log
```

## 3) Rieseguire test SBU (senza script — copia/incolla)

```bash
cd ~/src/user
DB="${PGDATABASE}"
ADDONS="/home/odoo/src/user,/home/odoo/src/odoo/addons,/home/odoo/src/odoo/odoo/addons"
[[ -d /home/odoo/src/enterprise ]] && ADDONS="/home/odoo/src/enterprise,${ADDONS}"
ODOO="/home/odoo/src/odoo/odoo-bin"
MODULES="sbu_stock_config,sbu_estimate,sbu_purchase_flow,sbu_sal,sbu_project,sbu_documents,sbu_closure,sbu_integrations,sbu_logikal,sbu_mail_ingest,sbu_qonto,sbu_revolut"
TAGS="/sbu_estimate,/sbu_purchase_flow,/sbu_sal,/sbu_stock_config,/sbu_closure,/sbu_qonto,/sbu_logikal,/sbu_documents,/sbu_project,/sbu_integrations,/sbu_mail_ingest,/sbu_revolut"

python3 "$ODOO" shell -d "$DB" --addons-path="$ADDONS" --stop-after-init <<'PY'
imm = env['ir.module.module'].search([
    ('name', 'in', 'sbu_estimate,sbu_purchase_flow,sbu_sal,sbu_stock_config'.split(',')),
    ('state', '=', 'installed'),
])
if imm:
    imm.write({'state': 'to upgrade'})
    print('marked_to_upgrade', imm.mapped('name'))
PY

python3 "$ODOO" -d "$DB" --addons-path="$ADDONS" -u "$MODULES" \
  --test-enable --stop-after-init --log-level=test --test-tags "$TAGS" \
  2>&1 | tee /tmp/sbu-test.log

grep -E 'FAIL:|odoo.tests.result' /tmp/sbu-test.log | tail -15
```

Successo: `0 failed, 0 error(s) of N tests` con **N > 0**.

## 4) `lnav` / `odoo.log` (funziona anche su commit vecchio `4dc3ef6`)

```bash
# Ultimi errori test SBU nel log runtime
grep -nE 'FAIL:|ERROR: test_|odoo\.tests\.result:|have the same label' ~/logs/odoo.log | tail -40

# In lnav: apri il file poi cerca (/) FAIL:  oppure  tests.result
lnav ~/logs/odoo.log
```

Se vedi ancora `1009 != 1` o `warning != over`, il build Odoo.sh deve deployare **`181635e`** (fix già su GitHub `production`).
