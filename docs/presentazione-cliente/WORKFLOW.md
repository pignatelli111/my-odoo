# Screenshot workflow (for you — English)

## Your routine

1. **Take a screenshot** of any Odoo SBU screen during demo / UAT / client prep.
2. **Send it in chat** with a short note if you want (e.g. “commessa after SAL invoice”).
3. **In chat (English)** you receive:
   - **What this screen is**
   - **What to do on this screen** (clicks, order of steps)
   - **What to explain to the client** (talk track, simple Italian ideas — you can read the full Italian script from the report)
4. **In the repo (Italiano)** the assistant appends a new **Scheda** to:
   - `REPORT_PRESENTAZIONE_CLIENTE_IT.md`
   - `screenshots/NN-short-name.png`

## Chat language vs report language

| Where | Language |
|-------|----------|
| Cursor chat with assistant | **English** |
| `REPORT_PRESENTAZIONE_CLIENTE_IT.md` | **Italiano** (client-facing) |
| `screenshots/` filenames | English short names (e.g. `03-commessa-overview.png`) |

## Standard message to send

Copy-paste when you upload a photo:

```text
Add to client report: [optional one line context]
```

## Report files

- **Main report (Italian):** [REPORT_PRESENTAZIONE_CLIENTE_IT.md](REPORT_PRESENTAZIONE_CLIENTE_IT.md)
- **Technical background:** [../REPORT_CLIENTE_SBU_ODOO_IT.md](../REPORT_CLIENTE_SBU_ODOO_IT.md)
- **Export to Word:** [../COME_ESPORTARE_REPORT_WORD.txt](../COME_ESPORTARE_REPORT_WORD.txt)

## Scheda template (filled automatically in Italian)

Each screenshot becomes one section with:

1. Image  
2. *Cosa mostra la schermata*  
3. *Cosa fare su questa schermata* (operational steps)  
4. *Cosa dire al cliente* (presentation script)  
5. *Valore per Suburban*  
6. *Cosa NON dire* (if relevant)
