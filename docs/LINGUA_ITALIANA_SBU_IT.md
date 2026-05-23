# Lingua italiana — menu e interfaccia SBU

## Perché alcune voci restano in inglese

Odoo traduce l’interfaccia così:

1. **Lingua utente** (Preferenze → Lingua = Italiano).
2. **Lingua installata** con opzione **Carica traduzioni** (Impostazioni → Lingue).
3. **File di traduzione** del modulo (`i18n/it.po`) caricati all’**aggiornamento** del modulo.

I menu SBU scritti in inglese nel codice (**Jobs**, **Purchasing**, **Billing**, …) restano in inglese finché non esiste `it.po` e non si aggiorna il modulo.

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
