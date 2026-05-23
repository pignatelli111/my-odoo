# Lingua italiana — menu e interfaccia SBU

## Come funziona (due lingue)

| Lingua utente | Cosa vede |
|---------------|-----------|
| **Italiano** | Testi da `i18n/it.po` (menu **Commesse**, **Preventivi**, …) |
| **English** | Testo **inglese nel codice** (menu **Jobs**, **Estimates**, …) |

Regola Odoo: il **codice** usa l’**inglese**; l’**italiano** è nel file `sbu_*/i18n/it.po`.  
Se nel codice c’era italiano fisso (es. **Miei Preventivi**), l’utente inglese vedeva comunque italiano — corretto dalla v. `19.0.1.0.93` di `sbu_estimate`.

## Perché alcune voci restano in inglese (utente IT)

1. **Lingua utente** = Italiano (Preferenze).
2. **Lingua installata** con **Carica traduzioni**.
3. **`odoo-update`** sui moduli SBU dopo il deploy (carica `it.po`).

I pulsanti **Nuovo**, **Cerca…**, date tipo **May 23** dipendono dalle traduzioni **standard Odoo** (`web`, `base`), non dai moduli SBU.

## Dopo il deploy Git (commit con `i18n/it.po`)

Su Odoo.sh, dopo build verde:

```bash
cd ~/src/user
# Aggiorna i moduli che contengono le traduzioni
odoo-update sbu_project,sbu_purchase_flow,sbu_sal,sbu_closure,sbu_logikal
```

Poi nel browser: **Ctrl+F5** o logout/login.

## Verifica rapida

| Voce menu (prima) | Dovrebbe diventare |
|-------------------|-------------------|
| Jobs | Commesse |
| Purchasing | Acquisti |
| Billing | Fatturazione |
| Closure document types | Tipi documento chiusura |

## Se ancora in inglese

1. **Impostazioni → Lingue → Aggiungi lingua** → Italiano → spunta **Carica traduzioni**.
2. **Preferenze utente** → Lingua = **Italiano** → Salva.
3. **Impostazioni → Traduzioni → Termini tradotti** → cerca `Jobs` → verifica traduzione IT (opzionale).
4. Ri-esegui `odoo-update` sui moduli SBU sopra.

## Estendere le traduzioni

Per tradurre altre etichette (form, pulsanti, messaggi Python):

1. In dev: **Impostazioni → Traduzioni → Esporta traduzione** → lingua Italiano → moduli SBU.
2. Modifica il file `.po` esportato o aggiungi voci in `sbu_*/i18n/it.po`.
3. Commit su Git e `odoo-update` sul modulo.
