# P1002 REV03 workbook vs import wizard

File analysed: `ANACO_P1002_25_CON_REV03_EIALL+ALL_P1.xlsx`

## Sheets

| Sheet | Role |
|-------|------|
| OFFERTA | Client offer grid (fallback if ANACO empty) |
| ANACO | Estimate lines (cols A–BW, max col **75**) |
| ITEM | BOM (not imported by wizard) |
| Voci Contrattuali_SAL | Contractual SAL lines |
| Sommario-SAL01-DIC21 | SAL summary (not imported) |

## ANACO (vs REV7)

| Topic | REV7 default | P1002 file |
|-------|----------------|------------|
| First product row | 12 | **13** (F1); row 12 = section title only |
| Row 5 K/L/M | Sc multipliers | 1, 1, 1 |
| Row 5 BM / BP | industrial / MOL % | **0** / **0.32** (32% MOL) |
| Testata rows 2–11 | — | Must **not** import (no product code) |

Product detection: column **B** codes like `F1`, `F3a`, with **qty** (H) and **BS** (col 71) > 0.

## Voci Contrattuali_SAL

| Topic | REV7 default | P1002 file |
|-------|----------------|------------|
| SAL-1 … SAL-10 headers | Col **98** (CT–DC) | Same col **98** |
| SAL-1…10 **data** | Often filled | **Empty** on product rows (formulas not stored) |
| First billable row | 16 | **17** (row 16 = section «SERRAMENTI SERIE F») |
| Billable lines | — | **34** (matches ANACO product count) |

Cols 85–96 (`Qty [n]` / `Qty [%]` blocks) hold 0/1 flags — **not** SAL-1…10 planning %.

## Expected Odoo result after import

- ~**34** `sbu.estimate.line` rows (not 43 with testata)
- ~**34** `sbu.estimate.sal.line` rows (not 163)
- **Cum.% = 0** on SAL lines until % are entered in Excel or Odoo
- **SAL status** = Prepared (contract qty/price), not Planned

Re-analyse locally:

```powershell
python tools/analyze_p1002_workbook.py "path\to\ANACO_P1002_25_CON_REV03_EIALL+ALL_P1.xlsx"
```
