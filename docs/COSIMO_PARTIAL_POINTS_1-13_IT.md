# Cosimo — chiusura punti parziali (1, 1b, 2, 4, 7, 8, 10, 13)

Aggiornamento modulo **maggio 2026** dopo richiesta «fix all partial parts fully».

## Riepilogo

| Punto | Cosa è stato completato |
|-------|-------------------------|
| **1 / 1b** | Wizard **Import from Excel** su RDA (`sbu.purchase.request.excel.import.wizard`); stato `excel_imported`; regole vetro 90% / zanzariere +300 mm anche su **create()** distinta |
| **2** | Dimensioni L/H/P/mq visibili su righe RDA e RFQ/PO; **Utilizzo** propagato su `purchase.order.line` |
| **4** | Item/Topic in lista e ricerca; help in testata RDA; default Item/Topic al caricamento BOM per route |
| **7** | Evidenziazione verde compilazione manuale anche su **righe PO** (related da riga RDA) |
| **8** | Tab M365: apri Planner, import **CSV → project.task**; deep link invariato |
| **10** | Qonto: auto **Register payment** cliente (import/cron/webhook) + match fornitore; vedi `COSIMO_PUNTO10_QONTO.md` |
| **13** | Fattura cliente: **una riga contabile per voce SAL** (+ ritenuta); stat **Contract billing** su commessa |

## Moduli / versioni

- `sbu_estimate` **19.0.1.0.89**
- `sbu_purchase_flow` **19.0.1.0.56**
- `sbu_documents` **19.0.1.0.10**
- `sbu_sal` **19.0.1.0.48**
- `sbu_qonto` **19.0.1.0.7**

## Verifica su Odoo.sh

```bash
# dopo build verde
odoo-bin -u sbu_estimate,sbu_purchase_flow,sbu_documents,sbu_sal,sbu_qonto -d <db> --stop-after-init
bash tools/odoo_sh_run_tests.sh
```

## Ancora fuori scope (non richiesti in questo batch)

- **9** Logikal produzione
- **12** import costi/margini/retention da Excel ANACO
- **14** — fatto in `sbu_qonto` 19.0.1.0.7 (sync beneficiari SEPA)
- Riconciliazione automatica **estratti conto** Qonto ↔ journal (fase 2)
