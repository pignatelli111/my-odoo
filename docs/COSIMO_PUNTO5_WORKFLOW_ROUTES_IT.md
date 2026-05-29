# Cosimo punto 5 — Catalogo route acquisto (LA, LZ, ST, …)

## Modello

- **`sbu.workflow.route`**: codice route, etichetta, tipo documento Odoo (RDA/ACO/…), flag wizard, obbligo Topic / data consegna.
- Dati iniziali: `sbu_purchase_flow/data/sbu_workflow_route_data.xml`.

## Menu

**SBU → Acquisti → Workflow routes** (gruppo responsabili acquisti).

## Utilizzo

1. Wizard **Nuovo documento acquisto** — elenco route da catalogo; validazione obblighi.
2. Campo **Route** su RDA — stessa selezione dinamica.
3. Commessa → **Crea richieste per workflow** — una RDA per route ANACO; non duplica RDA aperta stessa route.

## Modulo

`sbu_purchase_flow` ≥ 19.0.1.0.95
