# TMS Excel integration — step-by-step plan

Origin files: `file base che usano i tecnici_riservato/`

## Step 1 — TMS RDA/ACO/ACP import (DONE in 19.0.1.0.97)

- Parser `wizards/sbu_tms_excel_parser.py` for M.4.3.x layout
- Wizard **Import from Excel** auto-detects TMS or generic flat headers
- Imports header: Item, Topic, Drawn by, Check by, need-by date
- Imports lines: POS, description, article, qty, L/H/P, utilization, VdC, weight, destination
- New fields: `vdc_code`, `reference_rda` on purchase request lines

## Step 2 — VdC → budget family (DONE in 19.0.1.0.98)

- Model `sbu.vdc.catalog` with heuristic cost-family mapping
- PR line budget resolution uses `vdc_code` via catalog
- RDA import and project TMS import sync «Vdc» worksheet

## Step 3 — LDS register (DONE in 19.0.1.0.98)

- Model `sbu.lds.entry` from `M.4.4.A_TMS_LDS (Registro)_03.xlsx`
- Import via **Import TMS Excel** on project (auto or LDS mode)
- LDS tab on job form

## Step 4 — Drawing approval tracker (DONE in 19.0.1.0.98)

- Model `sbu.drawing.register` from Report tav appr TMS
- Import via project TMS wizard
- Optional `block_purchase` flag per drawing

## Step 5 — Multi-delivery dates (DONE in 19.0.1.0.98)

- PRIMA / SECONDA / TERZA / QUARTA CONSEGNA on purchase request
- Parsed from TMS header and imported with Excel wizard

## Step 6 — Route ownership (DONE in 19.0.1.0.98)

- `default_drawn_by` / `default_author` on workflow routes
- Sync from «Elenco elementi» sheet on LDS/RDA import
- Pre-filled on new purchase document wizard

## Step 7 — Unified project import (DONE in 19.0.1.0.98)

- Wizard `sbu.project.tms.import.wizard` on job: RDA/ACO/ACP/LDS/drawings/VdC/elenco
- Menu: SBU → Purchasing → Import TMS Excel
- Stat button on project form

## Verify on Odoo.sh

1. Upgrade `sbu_purchase_flow` to **19.0.1.0.101** and `sbu_estimate` to **19.0.1.0.112**
2. Import origin files from `file base che usano i tecnici_riservato/`
3. Confirm new fields: order n°, logistics supplier/site, project code, LEED, area/zone, LDS order n°, drawing RIF/emission 3

### Field parity vs origin Excel (19.0.1.0.99)

| Origin column | Odoo field |
|---------------|------------|
| Project / CODICE COMMESSA | `project_code` |
| Item / area (F01) | `excel_item` / `area_code` |
| PRIMA…QUARTA CONSEGNA | `need_by_date` + `delivery_date_2/3/4` |
| Unità (PZ, ml) | `product_uom` |
| N° ORDINE | `order_number` |
| FORNITORE/LOGISTICA + LOGISTICA/CANTIERE | `logistics_supplier` / `logistics_site` |
| NOTE / NOTE CONFORMITA | `note` |
| Vdc NOTE | `sbu.vdc.catalog.note` |
| LDS n.ro ORDINE | `sbu.lds.entry.order_number` |
| Drawing RIF + EMISS 3 | `reference` + `emission_3_date` |
| Elenco elementi → route owners | `default_drawn_by` on workflow routes |
