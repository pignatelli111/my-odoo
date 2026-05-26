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
| HTTP 401 Invalid credentials | Sign-in sbagliato, secret non salvato, o sandbox on/off | Vedi sezione «401» sotto |

### Errore 401 — Invalid credentials

1. In Qonto web app (produzione): **Integrations and partnerships → API key**.
2. Copia **Sign-in** (slug, es. `suburban-1234`) → campo **Qonto API login** in Odoo.
3. Clic **Generate** se serve, copia **Secret key** (stringa lunga) → **Qonto secret key**.
4. **Non** usare email utente né password di accesso Qonto.
5. **Qonto sandbox** = **spento** per chiavi produzione.
6. In Odoo: incolla login + secret + IBAN → **Salva** (in alto) → poi **Test Qonto connection**.
7. Se il campo secret è vuoto dopo il salvataggio, **re-incolla** il secret e salva di nuovo (Odoo a volte non mostra il valore salvato).

Verifica shell (non stampa il secret):

```bash
odoo-bin shell -d "$PGDATABASE" --no-http <<'PY'
c = env.company
login = (c.sbu_qonto_login or "").strip()
print("login:", login)
print("looks_like_email:", "@" in login)
print("login_len:", len(login))
print("secret_len:", len((c.sbu_qonto_secret_key or "").strip()))
print("sandbox:", c.sbu_qonto_use_sandbox)
PY
```

`looks_like_email: True` → credenziali sbagliate. `secret_len: 0` → secret non salvato.
| Sandbox senza token | `Qonto sandbox` attivo senza staging token | Developer Portal → token → campo **Staging token** |
| 0 movimenti importati | IBAN sbagliato o conto senza transazioni | `GET /v2/organization` in Qonto → IBAN corretto |
| Nessun menu | Modulo non installato / non aggiornato | `-u sbu_qonto` |
| Connect bank error | Flusso Odoo Enterprise | Ignorare; usare tab **Qonto (SBU)** |

## 5. Upgrade modulo

```bash
odoo-bin -u sbu_qonto -d <db> --stop-after-init
```

Oppure **Apps → SBU Qonto → Upgrade** dopo deploy Git.
