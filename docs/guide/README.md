# Guide utente SBU

| Documento | Pubblico |
|-----------|----------|
| [GUIDA_TEST_AUTONOMO_COSIMO.md](GUIDA_TEST_AUTONOMO_COSIMO.md) | **Cosimo / UAT** — test passo-passo senza esperienza Odoo (con screenshot) |
| [GUIDA_UTENTE_SBU_ODOO.md](GUIDA_UTENTE_SBU_ODOO.md) | Suburban SRL — utenti operativi |
| [../REPORT_CLIENTE_SBU_ODOO_IT.md](../REPORT_CLIENTE_SBU_ODOO_IT.md) | Report tecnico / avanzamento |
| [../UAT_LOGISTICS_B.md](../UAT_LOGISTICS_B.md) | Checklist UAT logistica |
| [../UAT_BANKING_C.md](../UAT_BANKING_C.md) | Checklist UAT Qonto |

## Screenshot

Le immagini in `screenshots/` provengono dalle sessioni di sviluppo e UAT (maggio 2026).

### Bot automatico (Playwright)

Tool in repo: [`tools/screenshot_bot/README.md`](../../tools/screenshot_bot/README.md)

- `capture.py login` — salva sessione Odoo
- `capture.py watch` — **screenshot ad ogni cambio URL** mentre navighi
- `capture.py manual` — screenshot su richiesta (nome file da tastiera)
- `capture.py run` — elenco URL da `capture_plan.json`

Per un PDF da consegnare al cliente: aprire la guida in VS Code / Cursor → anteprima Markdown → **Stampa / Esporta PDF**, oppure usare Pandoc.

```bash
# Esempio Pandoc (se installato)
pandoc GUIDA_UTENTE_SBU_ODOO.md -o GUIDA_UTENTE_SBU_ODOO.pdf --resource-path=.
```
