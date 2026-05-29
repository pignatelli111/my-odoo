# SBU Odoo — production roadmap (post UAT)

UAT chapters **1–5** passed on pilot job **P0006_2026** / **PRV/2026/0004**.  
This document tracks work to reach **full production use** (not only demo).

## Phase A — Enforced workflows (in code)

| Item | Module | Status |
|------|--------|--------|
| Block job **Chiusa/Archiviata** until closure checklist OK | `sbu_closure` | Implemented |
| Auto-init closure checklist when **In chiusura** | `sbu_closure` | Implemented |
| PO budget warning vs preventivo cost | `sbu_purchase_flow` | Implemented |
| OneDrive **access instructions** (link password / guest access) | `sbu_documents` | Implemented |
| **Test Graph connection** in Settings | `sbu_integrations` | Implemented |

## Phase B — Logistics (Chapter 6)

| Item | Module | Status |
|------|--------|--------|
| Project on receipts / deliveries | `sbu_stock_config` | Exists — UAT on real receipt |
| Reception buffer under Input (2-step) | `sbu_stock_config` | Implemented (`post_init_hook`) |
| DDT report + sequence on validate | `sbu_stock_config` | Implemented — UAT: `docs/UAT_LOGISTICS_B.md` |
| Site delivery + logistics tab | `sbu_stock_config` | Implemented (19.0.1.1.4) |

## Phase C — Banking (Chapter 6–8)

| Item | Module | Status |
|------|--------|--------|
| Qonto import cron (sync with company flag) | `sbu_qonto` | Implemented — UAT: `docs/UAT_BANKING_C.md` |
| Match suggestions + high-confidence link | `sbu_qonto` | Implemented (no bank reconcile) |
| Revolut import cron | `sbu_revolut` | Exists — enable separately |
| Bank journal reconciliation | both | TODO (full automation) |
| Webhook signature verification | both | TODO |

## Phase D — M365 (Chapter 5 + 8)

| Item | Module | Status |
|------|--------|--------|
| Document hub URL + custodian | `sbu_documents` | UAT done |
| Graph folder sync (drive/item id) | `sbu_documents` + `sbu_integrations` | Configure Azure app |
| Company SharePoint (no guest link password) | Process | Cosimo / IT |
| Teams / Planner deep links | `sbu_documents` | Manual links |

## Phase E — Logikal (Chapter 2)

| Item | Module | Status |
|------|--------|--------|
| CSV/JSON import | `sbu_logikal` | Exists |
| Apply dimensions to BOM lines | `sbu_logikal` | TODO |

## Phase F — Go-live checklist (non-code)

- [ ] Odoo.sh production build green (`sbu_estimate` 47+, `sbu_documents` 8+, `sbu_purchase_flow` 17+)
- [ ] Upgrade all `sbu_*` modules on production DB
- [ ] Real **products** and **suppliers** (not only UAT-PROF-01)
- [ ] User groups: who approves RDA, who closes jobs
- [ ] Training half-day on preventivo → RDA → RFQ → SAL
- [ ] Pilot: 2–3 new real jobs before migrating all open ANACO files
