# Odoo.sh shell — comandi quando `tools/` non esiste ancora

Se il build Odoo.sh è **rosso**, la shell usa ancora l’ultimo commit **verde** (`~/src/user` non ha i nuovi script).

## 1) Verifica commit in shell

```bash
cd ~/src/user
git log -1 --oneline
ls tools/odoo_sh_run_tests.sh 2>/dev/null || echo "script assente — build non ancora verde su questo commit"
```

## 2) Errori del build fallito (sempre disponibile)

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
