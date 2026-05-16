# SBU Odoo — Suburban SRL Custom Modules

Custom **Odoo 19.0** addons for **Suburban SRL a Socio Unico**.

## Current status (May 2026)

- **Target:** Odoo **19**; code is deployed via **GitHub** + **Odoo.sh**. Development tracks **`main`**; production normally tracks **`production`** — merge `main` → `production` and push when promoting releases.
- **General Settings / SBU:** SBU integration blocks are injected under **Settings → General Settings** (search *SBU*, *Graph*, *OneDrive*, *Logikal*). There is no separate “SBU” app tab in the settings left rail.
- **`res.config.settings` fixes:** Policy fields that use `config_parameter` must be **`Char`**, not `Text` (Odoo rejects `Text` for classified settings keys). Graph / OneDrive / Logikal URL settings behave accordingly.
- **Copying SBU parameters between databases:** **`sbu_integrations`** includes **Settings → Administration → SBU settings JSON (dev → prod)** — export all `sbu.*` `ir.config_parameter` keys as JSON on one DB and import on another. If export is empty, either **save** the SBU block once under Settings or use **Fill missing code defaults** (non-secret defaults only; Azure secrets still require saving Settings or pasting into JSON).
- **Qonto / Revolut:** Use the **company form** tabs **Qonto (SBU)** / **Revolut (SBU)** and module **SBU Qonto** / **SBU Revolut**. Do **not** use Odoo’s **Accounting → Connect your bank → Qonto** flow unless you have a valid **Odoo Enterprise** subscription linked to the database — that path shows a subscription error for SBU-only setups.
- **Logikal:** The **Logikal / ReynaPro** SQLite file (e.g. from Orgadata/Fonatto) is **not** read by Odoo. Use **Logikal → Imports** with **CSV/JSON** (column aliases documented in code) or an optional **HTTP API bridge** (`sbu.logikal_*` system parameters). **Logikal API base URL** in Settings is only required for API mode.
- **Custom domains:** You control DNS only for hostnames under **zones you own**. A name like `*.odoo.com` is assigned by Odoo; use your Odoo.sh URL (e.g. `https://…-my-odoo.odoo.com`) or add a **CNAME** from **your** domain to that host per Odoo.sh Domains instructions.
- **Estimates + CRM opportunities:** The optional **CRM Opportunity** field on a preventivo reads `crm.lead`. Users need **SBU Estimate User** (or **Sales / User** / **Sales / Administrator**) on their user record. Without that, Odoo shows *You are not allowed to access 'Lead' (crm.lead) records*.

## Modules

| Module | Description |
|--------|-------------|
| `sbu_estimate` | Custom estimating engine (ANACO → Odoo) |
| `sbu_purchase_flow` | RDA/ACO/ACP/LDS purchase flow |
| `sbu_project` | Project / job container |
| `sbu_stock_config` | Stock locations / routes for SBU |
| `sbu_sal` | SAL + payment certificates + retention |
| `sbu_documents` | Document hub, Microsoft Graph folder sync, M365 links |
| `sbu_integrations` | Graph / OneDrive naming & policies; SBU settings JSON wizard |
| `sbu_logikal` | Logikal / ReynaPro file or API bridge → products & BOM |
| `sbu_qonto` | Qonto movements import + webhooks |
| `sbu_revolut` | Revolut movements import + webhooks |
| `sbu_closure` | Job closure requirements / document types |
| `sbu_mail_ingest` | Email aliases on RFQ/PO; supplier/project ingest routes |

## ANACO Excel (reference)

Authoritative formulas and workbook: keep the team copy outside git or in a shared drive.  
Example path used for analysis: `f:\TASK\20 . Odoo\New folder\CARTELLA PREVENTIVO\ANALISI E PREVENTIVO\ANACO_REV7_111122.xlsx`  
Short mapping notes: `docs/ANACO_REFERENCE.txt`.  
All Excel templates under `New folder` (RDA, ACP, ACO, LDS, definizioni): `docs/EXCEL_SOURCE_INDEX.txt`.  
Regenerate workbook previews: `python tools/dump_excel_workbooks.py` (writes `docs/excel_workbooks_inventory.json`, gitignored).

## Deploy (Odoo.sh)

1. Clone / push this repo to GitHub.
2. **Development:** push to **`main`**; wait for a green build; **upgrade** changed modules on the dev database (**Apps → SBU … → Upgrade**).
3. **Production:** merge **`main` → `production`**, push **`production`**; wait for green build; **upgrade** the same modules on production.

After code changes that touch settings views or `ir.config_parameter` logic, upgrade **`sbu_integrations`** (and any other touched addon) on each database.

## Company

- Suburban SRL a Socio Unico  
- P.IVA: 12352270966  
- Cornate d'Adda (MB)
