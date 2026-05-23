# Guida contestuale SBU (pulsante ?)

## Per gli utenti

- Su ogni schermata Odoo con un modello (preventivo, RDA, commessa, SAL…) compare un pulsante **?** blu in basso a destra.
- Il testo segue la **lingua utente** (Preferenze → Lingua).
- Il contenuto spiega: **scopo della schermata**, **pulsanti**, **schede** e **filtri** principali.

## Per gli amministratori

- Menu **SBU → Screen help (admin)** (solo impostazioni / admin).
- Modelli: `sbu.ui.help.topic` e righe `sbu.ui.help.item`.
- Campi traducibili: aggiungere italiano con **Impostazioni → Traduzioni** o file `sbu_ui_help/i18n/it.po`.

## Il pulsante ? non compare?

1. **Apps** → cerca **SBU Context Help** → stato **Installato** (non solo presente nell’elenco).
2. Dopo il deploy Git: `odoo-update sbu_ui_help` (shell Odoo.sh) oppure **Aggiorna** da Apps.
3. **Ctrl+F5** nel browser (asset JavaScript).
4. In shell: `env['ir.module.module'].search([('name','=','sbu_ui_help')]).state` → deve essere `installed`.

Senza modulo installato il pulsante **non esiste** (è JavaScript, non un’impostazione utente).

## Modulo tecnico

- **`sbu_ui_help`** — di solito si installa con gli altri moduli SBU (`auto_install`); se manca, installarlo manualmente.
- Dopo deploy: `odoo-update sbu_ui_help` e **Ctrl+F5** nel browser.

## Estendere la guida

1. Duplicare un topic esistente in **Screen help (admin)**.
2. Impostare **Model** (es. `sbu.purchase.request`) e **View type** (`form` / `list`).
3. Aggiungere righe **Buttons & tabs** con titolo visibile e spiegazione HTML breve.
