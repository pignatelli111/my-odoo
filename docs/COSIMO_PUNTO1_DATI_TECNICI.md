# Cosimo — Punto 1: ANACO stima vs documenti tecnici

## Modello concordato

| Fase | Fonte | Uso |
|------|--------|-----|
| **Stima** | ANACO / distinta preventivo | Preventivo, contratto, bozza RDA |
| **Revisione tecnica** | RDA/ACO/ACP/VT… (Excel o DWG/DF consulenti) | Misure e costi **reali** |
| **Pronto per PO** | Righe confermate in Odoo | RFQ / ordine fornitore |

## Regole distinta (da ANACO)

| Prodotto | Regola |
|----------|--------|
| **SBU-VETRO** | MQ = **90%** di B×H posizione (mq/cad); richiede conferma tecnica |
| **SBU-ZANZ** | Altezza effettiva = H posizione **+ 300 mm**; mq da B×H effettivi |
| **SBU-OSC** | Come zanzariere (+300 mm H) |

Campi in **Distinta (ITEM)**: `Dimensioni`, `MQ/cad eff.`, `Confermato per PO`, `Fase dati`.

## Flusso RDA

1. **Aggiungi righe da distinta** → stima con dimensioni calcolate.  
2. **Avvia revisione tecnica** → aggiornare misure da documento consulente (righe distinta o RDA).  
3. Spuntare **Confermato per PO** sulle righe vetro/zanzariere/oscuranti.  
4. **Pronto per RFQ/PO** → abilita **Create draft RFQ(s)**.  

Senza passo 4, la creazione RFQ è bloccata con messaggio esplicativo.

## Prossimi passi (non in questo commit)

- Import Excel RDA/ACO/ACP per sovrascrivere righe.  
- Logikal → flag «bozza Logikal» + applica mq.  
- Costi reali su **offerte fornitore** (già separati da costo CAD ANACO).

---

## Punto 2 — Dimensioni su RFQ / PO

Colonne su **righe RFQ/ordine acquisto** (oltre alla RDA):

| Colonna | Campo |
|---------|--------|
| L mm | `sbu_width_mm` |
| H mm | `sbu_height_mm` |
| P mm | `sbu_depth_mm` (profondità non unitaria, da documento tecnico) |
| MQ/cad | `sbu_sqm_per_piece` |
| MQ tot. | `sbu_sqm_total` |
| Dimensioni | riepilogo testuale |

Copiate automaticamente alla **Create draft RFQ(s)**. Se aggiorni misure sulla RDA, usa **Refresh BOM quantities** per aggiornare anche le righe RFQ in bozza.

---

## Punto 3 — Filtri e modifica massiva

**Menu:** SBU → Purchasing → **Request lines (bulk edit)**

1. Usa **Filtri** (tipo RDA/ACO/VT, route, data consegna vuota, conferma tecnica, …).  
2. Seleziona righe o **Select all matching search**.  
3. **Action → Apply to selected lines** (o da RDA: **Apply to all lines**).  
4. Spunta i campi da applicare (checkbox): data consegna, destinazione, magazzino/acquisto, priorità, need-by testata.

Moduli: `sbu_estimate` **19.0.1.0.75+**, `sbu_purchase_flow` **19.0.1.0.22+**.
