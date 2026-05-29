# Cosimo — Punto 18: Revisioni visibili (REV + data)

**Moduli:** `sbu_estimate` 19.0.1.0.86+, `sbu_project` 1.0.1+, `sbu_sal` 1.0.45+, `sbu_purchase_flow` 1.0.54+

---

## Problema

Con più revisioni dello stesso preventivo/commessa non era chiaro in **Jobs**, **SAL**, **RDA**, **fatture** quale fosse la REV corrente e quale la più recente.

---

## Formato etichetta

Esempio commessa:

`[P0015_2026] BLACKROCK · REV02 · 2026-05-20`

- **Codice commessa** + cantiere  
- **REV** dal preventivo collegato  
- **Data** del preventivo (campo Data)

Documenti operativi (SAL, RDA, CDP, fattura):

`SAL-0042 · [P0015_2026] BLACKROCK · REV02 · 2026-05-20`

---

## Dove si vede

| Schermata | Campo / comportamento |
|-----------|------------------------|
| **Jobs** (menu SBU) | Colonna *Commessa* = etichetta REV; filtro default *Solo revisione più recente* |
| **Preventivi** | Colonna *Preventivo* = etichetta; badge *Ultima REV* |
| **SAL attivo / passivo** | Colonna e `name_get` con etichetta commessa |
| **Richieste acquisto** | Colonna *Documento* con REV commessa |
| **Fatture** (cliente/fornitore collegate) | `name_get` con REV quando c’è commessa/SAL |

Scheda commessa **SBU**: riepilogo `sbu_revision_label`, flag *Revisione più recente*.

---

## Filtri

- Jobs: **Solo revisione più recente** (attivo di default) / **Tutte le revisioni**  
- Preventivi: **Solo revisione più recente**

---

## Aggiornamento DB

Upgrade: `sbu_estimate`, `sbu_project`, `sbu_sal`, `sbu_purchase_flow`.

Le etichette si ricalcolano ai campi stored al primo upgrade; aprire/salvare una commessa se serve forzare il refresh su record vecchi.
