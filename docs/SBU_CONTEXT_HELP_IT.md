# Guida contestuale SBU (pulsante ?)

## Per gli utenti

- Su ogni schermata Odoo con un modello (preventivo, RDA, commessa, SAL…) compare un pulsante **?** blu in basso a destra.
- Il testo segue la **lingua utente** (Preferenze → Lingua).
- Il contenuto spiega: **scopo della schermata**, **pulsanti**, **schede** e **filtri** principali.

## Per gli amministratori

- Menu **SBU → Screen help (admin)** (solo impostazioni / admin).
- Modelli: `sbu.ui.help.topic` e righe `sbu.ui.help.item`.
- Campi traducibili: aggiungere italiano con **Impostazioni → Traduzioni** o file `sbu_ui_help/i18n/it.po`.

## Modulo tecnico

- **`sbu_ui_help`** — si installa automaticamente con gli altri moduli SBU (`auto_install`).
- Dopo deploy: `odoo-update sbu_ui_help` e **Ctrl+F5** nel browser.

## Estendere la guida

1. Duplicare un topic esistente in **Screen help (admin)**.
2. Impostare **Model** (es. `sbu.purchase.request`) e **View type** (`form` / `list`).
3. Aggiungere righe **Buttons & tabs** con titolo visibile e spiegazione HTML breve.
