# Qonto — debug test fallito su Odoo.sh

## 1. Verifiche rapide (UI)

| Controllo | Azione |
|-----------|--------|
| Modulo installato | **Apps** → `SBU Qonto` → **Installed** |
| Versione | ≥ **19.0.1.0.8** (pulsante *Test Qonto connection*) |
| Salvataggio | **Impostazioni → Save** dopo aver incollato login/secret |
| Login API | Valore **sign-in** Qonto (es. `suburban-1234`), **non** email utente |
| Sandbox | **Off** = chiavi produzione; **On** = chiavi sandbox + **Staging token** |
| IBAN | Copiato da Qonto (stesso conto dell’API) |
| Menu giusto | **Contabilità → Movimenti Qonto** — non «Collega banca» |

## 2. Ordine test dopo upgrade `sbu_qonto`

1. **Impostazioni** → blocco Qonto → **Test Qonto connection**  
   - ✅ = credenziali OK  
   - ❌ = leggere messaggio HTTP (401 = login/secret/sandbox errati)  
2. **Sync Qonto suppliers**  
3. **Import Qonto movements now**  
4. **Contabilità → Movimenti Qonto**

## 3. Shell Odoo.sh (se il pulsante non c’è ancora)

```bash
odoo-bin shell -d <nome_database> --no-http <<'PY'
company = env.company
print("login:", bool(company.sbu_qonto_login))
print("secret:", bool(company.sbu_qonto_secret_key))
print("iban:", company.sbu_qonto_iban)
print("sandbox:", company.sbu_qonto_use_sandbox)
try:
    company.action_sbu_test_qonto_connection()
    print("OK")
except Exception as e:
    print("FAIL:", e)
PY
```

Log runtime:

```bash
grep -i qonto ~/logs/odoo.log | tail -40
```

## 4. Errori frequenti

| Sintomo | Causa probabile | Fix |
|---------|-----------------|-----|
| HTTP 403 + error 1010 / Cloudflare | Odoo.sh bloccato da Cloudflare Qonto (UA/TLS) | Upgrade `sbu_qonto` ≥ 19.0.1.0.9; se persiste → Qonto support con **Ray ID** |
| HTTP 401 | Login/secret invertiti o email al posto del sign-in | Rigenera API key in Qonto → Integrations |
| Sandbox senza token | `Qonto sandbox` attivo senza staging token | Developer Portal → token → campo **Staging token** |
| 0 movimenti importati | IBAN sbagliato o conto senza transazioni | `GET /v2/organization` in Qonto → IBAN corretto |
| Nessun menu | Modulo non installato / non aggiornato | `-u sbu_qonto` |
| Connect bank error | Flusso Odoo Enterprise | Ignorare; usare tab **Qonto (SBU)** |

## 5. Upgrade modulo

```bash
odoo-bin -u sbu_qonto -d <db> --stop-after-init
```

Oppure **Apps → SBU Qonto → Upgrade** dopo deploy Git.
