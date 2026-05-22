# Feedback operativo Cosimo — Analisi e roadmap SBU Odoo

**Cliente:** Suburban SRL a Socio Unico  
**Autore feedback:** Cosimo (operativo)  
**Documento:** risposta tecnica + piano di lavoro  
**Versione:** 1.0 — maggio 2026  
**Repository:** `pignatelli111/my-odoo`  
**Ambiente:** Odoo 19 su Odoo.sh  

**Collegamenti:**  
- [Report tecnico cliente](REPORT_CLIENTE_SBU_ODOO_IT.md)  
- [Presentazione con screenshot](presentazione-cliente/REPORT_PRESENTAZIONE_CLIENTE_IT.md)  
- [Roadmap produzione](PRODUCTION_ROADMAP.md)  
- [Esportazione Word](COME_ESPORTARE_REPORT_WORD.txt)  

---

## 1. Sintesi (per il cliente)

Il feedback di Cosimo descrive correttamente il **processo reale Suburban**:

1. **ANACO** = preventivo e contratto (misure e prezzi **stimati**).  
2. **Documenti tecnici** (RDA, ACO, ACP, VT, LA, LZ, FE, ST, …) = ordini interni dei consulenti, spesso **fuori ERP** (Excel o DWG/DF con tabelle interne). Sono la base del **PO finale** dopo approvazione disegni e varianti cliente.  
3. **Odoo SBU oggi** copre bene la **spina dorsale** (preventivo → commessa → distinta → RDA/RFQ → SAL attivo → fattura/CDP).  
4. **Fase successiva** = portare in Odoo la **verità tecnica** (misure, costi, caratteristiche reali) e il **controllo budget** come nel foglio ITEM ANACO, più SAL passivo (posa/subappalto).

Questo documento mappa i **18 punti** di Cosimo su: stato attuale, gap, priorità, risposta proposta.

---

## 2. Modello a due livelli (concordato)

```text
┌─────────────────────────────────────────────────────────────────┐
│  LIVELLO 1 — ANACO / Preventivo Odoo (stima commerciale)        │
│  Misure e costi stimati · contratto · distinta “tipo”           │
└────────────────────────────┬────────────────────────────────────┘
                             │ genera bozza RDA/RFQ (quantità da distinta)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  LIVELLO 2 — Documenti tecnici consulenti (oggi spesso Excel)   │
│  Misure/prezzi REALI · varianti post-approvazione disegni       │
└────────────────────────────┬────────────────────────────────────┘
                             │ aggiorna RDA → offerte fornitore → PO
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  PO confermato · magazzino · cantiere · consuntivo vs budget    │
└─────────────────────────────────────────────────────────────────┘
```

**Domanda (a) di Cosimo — quando inserire misure/costi reali per il PO?**  
**Risposta proposta:** in una fase esplicita **«Da confermare tecnico» → «Congelato per PO»**, dopo i documenti interni approvati (non al momento della sola distinta ANACO). Logikal può **precompilare** ma non sostituisce la revisione finale.

**Domanda (b) — vetro 90% mq, zanzariere +300 mm, voci non dimensionate in distinta?**  
**Risposta proposta:** regole configurabili per famiglia/route (VT, zanzariere, oscuranti) + override manuale o import tecnico; propagazione L×H e mq su distinta e righe acquisto.

---

## 3. Tabella riepilogo 18 punti

| # | Argomento Cosimo | Valutazione | Stato Odoo oggi | Priorità |
|---|------------------|-------------|-----------------|----------|
| 1 | Ordini interni vs ANACO; quando dati reali PO; vetro/zanzariere/Logikal | **Corretto** | Distinta da ANACO sì; fase «tecnico finale» no | **P0** |
| 2 | Dimensioni perse su RFQ (L×H×P + mq/cad, mq/tot) | **Corretto** | `dimension_mm` su RDA (spesso nascosto); RFQ/PO incompleto | **P0** |
| 3 | Filtri a tendina + applica scelta a tutto il filtrato | Utile | Searchpanel + wizard «risultato filtrato» su righe RDA | **P1** ✅ base |
| 4 | Item / Topic / Area su purchase requests | Da chiarire UX | Campi `excel_item`, `topic`; route = `workflow_route` / `request_type` | **P2** |
| 5 | Mancano LA/LZ/ST/PAN/OSC; creazione guidata tipi | **Corretto** | Filtri/searchpanel route + wizard «Nuovo documento» | **P1** ✅ base |
| 6 | SAL passivo (posa, subappalto) | **Corretto** | Foglio SAL passivo + fattura fornitore; base in `sbu_sal` | **P0** ✅ base |
| 7 | Celle verdi = compilazione manuale | Ottima UX | Evidenza verde/grigio su righe ANACO, distinta ITEM, RDA | **P2** ✅ base |
| 8 | Planner Microsoft ↔ Odoo | Realistico | Solo deep link / processo; sync bidirezionale fragile | **P3** |
| 9 | Logikal | Rimandato | Modulo presente; dimensioni finali su BOM = TODO | **P1** |
| 10 | Qonto: riconciliazione auto; abbandono what-if | Parziale | Import + suggerimento match; **no** riconciliazione banca auto | **P1** (bank) |
| 11 | Budget per tipologia (semafori ITEM) + sblocco solo admin | **Corretto** | Cruscotto famiglia su commessa + blocco conferma PO; sblocco admin | **P0** ✅ base |
| 12 | Costi / margini / retention import sbagliati | **Corretto** (parità ≠ Excel 1:1) | BS prezzo ok; costi parziali; MOL fuori totale; retention SAL = default azienda | **P0** |
| 13 | Stampa fattura per voce contratto + SAL/CDP; dashboard | **Corretto** | Tracciabilità SAL/fattura/CDP sì; PDF = 1–2 righe aggregate; report dettaglio da fare | **P1** |
| 14 | Qonto → fornitori/clienti automatici | Opzionale | Non implementato | **P2** |
| 15 | Cambio qty RDA/RFQ: residuo aperto; qty 1,03 | Spiegabile | 1,03 = perdita%/confezione distinta; residuo da confermare | **P1** |
| 16 | Stampa offerta: flag verdi/rossi + pagamenti/ritenute | Implementato | Condizioni strutturate + PDF offerta | **P1** ✅ |
| 17 | Delivery standard (sistemista → terzista → cantiere; vetro) | **Corretto** | Regole `sbu.delivery.standard` + tab commessa + auto DESTINAZIONE | **P1** ✅ base |
| 18 | Revisioni: label job/SAL/doc con REV + data | **Corretto** | Etichetta REV+data su Jobs, preventivi, SAL, RDA, fatture | **P0** ✅ base |

**Legenda priorità:** P0 = produzione / fiducia dati · P1 = flusso acquisti/fatture completo · P2 = UX · P3 = integrazioni opzionali  

---

## 4. Dettaglio per punto

### Punto 1 — Documenti tecnici vs ANACO

**Feedback Cosimo**  
RDA, ACO, ACP, VT, LA, LZ, FE, … sono prodotti dai consulenti tecnici (Excel o DWG/DF). Sono i dati veri per il PO. ANACO resta stima per preventivo/contratto. La distinta preventivo può alimentare le RDA, ma servono misure/costi/caratteristiche **reali** dopo approvazione disegni (anche varianti contratto). Logikal spesso non è finale: spuntare o correggere.

**Stato attuale**  
- Import ANACO → righe preventivo + voci SAL + distinta (~434 componenti).  
- RDA da distinta: quantità da regole BOM (perdita %, MOQ, confezioni).  
- Prezzo PO **non** copia costo CAD ANACO (scelta di processo: prezzo da **offerta fornitore**).

**Proposta**  
| Fase | Azione |
|------|--------|
| A | Stati RDA: `Bozza da distinta` → `In revisione tecnica` → `Approvata per RFQ/PO` |
| B | Import Excel tecnico (template RDA/ACO) → aggiorna righe esistenti, marca delta vs distinta |
| C | Logikal: flag «da verificare» su righe importate; wizard applica mq/L×H dove affidabile |
| D | Regole VT (es. 90% mq posizione), zanzariere (+300 mm), ecc. in configurazione |

---

### Punto 2 — Colonna dimensioni su RFQ

**Feedback**  
In RDA/RFQ manca la colonna dimensioni (larghezza, altezza, profondità non unitaria + mq/cad, mq/tot).

**Stato attuale**  
- Righe preventivo: `width_mm`, `height_mm`, `sqm_per_piece`, `sqm_total`.  
- Righe distinta: `dimension_source` (larghezza/altezza/superficie).  
- Righe RDA: `dimension_mm` (testo, colonna **opzionale nascosta**).  
- RFQ/PO: propagazione incompleta.

**Proposta**  
Mostrare e copiare su RDA → RFQ → PO: **L, H, P**, **mq/cad**, **mq tot**, **utilizzo**; descrizione articolo arricchita in automatico.

---

### Punto 3 — Filtri e modifica massiva

**Feedback**  
Filtri a tendina sezionabili + applicare una scelta a tutto il set filtrato (es. data consegna), come concetto visto in area purchase.

**Proposta**  
Azioni server su liste RDA/RFQ/righe: «Imposta data consegna su righe selezionate / filtrate»; filtri salvati per commessa e `request_type`.

---

### Punto 4 — Item, Topic, Area (purchase requests)

**Feedback**  
Non chiaro l’uso di Item / Topic / Area.

**Spiegazione operativa**  

| Campo Odoo | Significato |
|------------|-------------|
| **Item (foglio Excel)** | `excel_item` — codice voce template (es. FT, LA01) |
| **Topic** | `topic` — argomento RDA come nel foglio consulente |
| **Area / percorso** | `workflow_route` (VC/VS, ST, PAN, LA, …) oppure **Tipo documento** (`request_type`: RDA, ACO, ACP, VT, FE, ST, LDS) |

**Uso consigliato**  
1. Creare richieste **per route** dalla commessa (pulsante / wizard).  
2. Compilare Item e Topic per tracciabilità verso il file Excel del tecnico.  
3. Non sono ancora trigger automatici: servono per **ricerca e report**.

---

### Punto 5 — Tipi documento LA / LZ / ST / PAN / OSC

**Feedback**  
Negli elenchi mancano alcuni tipi; serve creazione guidata per evitare dati sporchi.

**Stato attuale (routing)**  

| Route ANACO | Tipo richiesta Odoo |
|-------------|---------------------|
| VC/VS | VT — Vetro |
| ST | ST — Staffe |
| LZ | FE — Carpenteria |
| PAN, LA, PRF, FT/FTF, SE | RDA — Materiali principali |
| ASS, ACC, GUA | ACO |
| POS | ACP |
| TRN | LDS |

**Implementato (base)**  
Wizard «Nuovo documento acquisto», route `LA/LZ/ST/PAN/OSC` in filtri e searchpanel, split OSC/ZANZ da distinta vetro, blocco duplicati aperti per commessa+route.

---

### Punto 6 — SAL passivo (posa / subappalto)

**Feedback**  
Il SAL deve gestire anche il **passivo**, in particolare servizi di posa (appalti/subappalti).

**Stato attuale**  
SAL cliente: foglio SAL → fattura attiva → CDP.  
**SAL passivo (base):** modello `sbu.sal.passive.sheet` — commessa, fornitore, periodo, righe con budget ANACO (POS / famiglia installazione / costi cantiere), % avanzamento, fattura fornitore `in_invoice`. Menu **SBU → Billing → Passive SAL (subcontract)**; smart button su commessa.

**Proposta (fasi successive)**  
| Elemento | Descrizione |
|----------|-------------|
| Report | Cruscotto avanzamento posa vs budget ANACO per commessa |
| CDP passivo | Certificato pagamento subappalto (se richiesto) |
| Vincoli | Blocco % cumulato > 100% su stessa voce preventivo |

---

### Punto 7 — Celle verdi (compilazione manuale)

**Implementato (base)**  
- Stato `manual_input_state` / flag `manual_input_pending` su **distinta ITEM** (`sbu.estimate.bom.line`) e **righe RDA** (`sbu.purchase.request.line`).  
- Liste Odoo: **verde** (`decoration-success`) sulle celle vuote da compilare; **grigio** (`decoration-muted`) quando i dati arrivano da import tecnico o fase **Logikal** (`data_phase`).  
- Righe preventivo ANACO: verde su **B/H** se U.M. = MQ/ML e misure mancanti.  
- Filtri RDA: «Compilazione manuale (verde)», «Da import / Logikal (grigio)».

**Proposta (estensioni)**  
Regole per colonna Excel specifica; stesso schema su RFQ/PO; legenda in form.

---

### Punto 8 — Microsoft Planner

**Posizione**  
Non promettere sincronizzazione bidirezionale Planner ↔ Odoo.  
**Alternativa:** link Planner/Teams su commessa (Document hub); esecuzione task in Planner; Odoo per preventivo, acquisti, SAL, magazzino.

---

### Punto 9 — Logikal

**Posizione**  
Affrontare **dopo** stabilizzazione dimensioni e import tecnico (punti 1–2). Modulo `sbu_logikal` già presente; applicazione dimensioni finali alla distinta = in roadmap.

---

### Punto 10 — Qonto e riconciliazione

**Aspettativa Cosimo**  
Pagamenti ricevuti riconciliati automaticamente; abbandono strumenti what-if fatture in Qonto.

**Realtà oggi (`sbu_qonto`)**  

| Funzione | Disponibile |
|----------|-------------|
| Import movimenti (API + cron) | Sì (richiede IBAN + credenziali) |
| Suggerimento match fattura/pagamento | Sì |
| Collegamento manuale «Matched in Odoo» | Sì |
| Riconciliazione automatica prima nota banca | **No** (roadmap) |
| Sostituzione completa scenari Qonto | **Parziale** (fatturazione in Odoo sì) |

**Messaggio al cliente**  
«Prima fase: mirror movimenti + aiuto al match. Fase successiva: riconciliazione bancaria in Odoo, poi si riduce l’uso Qonto solo come banca.»

---

### Punto 11 — Budget per tipologia (semafori)

**Feedback**  
Come foglio ITEM ANACO: budget preventivo, acquistato, residuo, %; semafori; solo **admin** sblocca PO se sforamento.

**Stato attuale (base maggio 2026)**  
- Modello `sbu.project.budget.family`: preventivo ANACO per famiglia, RDA aperte, PO bozza/confermati, impegnato, residuo, %, semaforo (verde &lt; 90%, giallo fino 105%, rosso oltre).  
- Scheda commessa **Budget acquisti** + menu SBU → Purchasing → **Budget per famiglia**.  
- Conferma PO bloccata se famiglia in rosso; sblocco con flag **Unlock PO over budget** (solo `Settings / Administrator`) o utente admin.  
- Resta alert legacy su totale PO (`sbu_budget_over_limit`).

**Proposta fase 2**  
| Voce | Contenuto |
|------|-----------|
| Consuntivo | Collegare fatture fornitore / movimenti a valore «consuntivo» per famiglia |
| Gruppo dedicato | Ruolo «SBU budget unlock» separato da admin Odoo |

---

### Punto 12 — Costi, margini, retention in import

**Feedback confermato** — vedi analisi: [COSIMO_PUNTO12_COSTI_MARGINI_RETENTION.md](COSIMO_PUNTO12_COSTI_MARGINI_RETENTION.md).

| Voce | Excel / atteso | Odoo oggi |
|------|----------------|-----------|
| Prezzo cliente | Col. **BS** (catena sconti foglio) | BS → `price_anaco_bs_cad` se letto; altrimenti Σ componenti × Sc × Comm.% |
| Costo totale | Include tutte le colonne CAD che l’utente somma | Import parziale; **MOL non nel costo totale**; es. **staffame ST/LZ** non mappato |
| Margine % | Da celle Excel | Ricalcolato: prezzo TOT − costo TOT |
| Retention / garanzia | % su foglio SAL o contratto | **Sempre default azienda** (es. 5 %), non dal file |

**Subito (UAT)**  
1. Dopo import: controllare **Prezzo unit. ANACO (col. BS)** sulle righe.  
2. Tab **Voci contrattuali SAL** → correggere **Retention %** se diversa dal contratto.  
3. `python tools/probe_anaco_workbook.py` sul file P1002 in `docs/samples/client/`.

**Fix P0 (codice)**  
1. Mapping colonne costo mancanti + retention da SAL.  
2. Test parità numerica su P1002.  
3. Avviso wizard se BS assente e listino diverso da atteso.

---

### Punto 13 — Stampa fattura e dashboard

**Feedback confermato** — vedi [COSIMO_PUNTO13_FATTURA_SAL_CDP.md](COSIMO_PUNTO13_FATTURA_SAL_CDP.md).

**Fatto (P1, `sbu_sal` 19.0.1.0.39)**  
- Report QWeb **«Invoice with SAL detail (SBU)»**: testata commessa, preventivo, SAL, periodo, **CDP**; tabella **per voce contrattuale**; footer lordo/ritenuta/netto; sezione righe contabili.  
- `account.move.sbu_sal_sheet_id` impostato in creazione fattura da foglio SAL; `sbu_sal_cdp_name` in testata.  
- Stampa da foglio SAL (**SAL detail PDF**) e da fattura (menu Stampa + pulsante).  
- Contabilità invariata (1–2 righe aggregate).

**Aperto (P2)**  
- Cruscotto SBU unico (fatturato vs contratto, SAL aperti); eventuale dettaglio righe in fattura elettronica SDI (opzione A, con commercialista).

---

### Punto 14 — Fornitori/clienti da Qonto

**Risposta**  
Oggi **no** import automatico anagrafiche. Opzionale in fase 2 API Qonto (beneficiari) con deduplica manuale.

---

### Punto 15 — Quantità 1,03 e residuo RDA

**Stato:** implementato (`sbu_purchase_flow` 19.0.1.0.44). Dettaglio: [COSIMO_PUNTO15_RDA_RESIDUO_QTY.md](COSIMO_PUNTO15_RDA_RESIDUO_QTY.md).

**Qty 1,03** — quantità richiesta (+3% perdita fabbisogno default), non U.M.

**Residuo** — campi `qty_ordered` / `qty_remaining`; RFQ usa il residuo; modifica qty RFQ aggiorna il residuo sulla RDA.

---

### Punto 16 — Stampa offerta (flag e condizioni)

**Stato:** implementato (`sbu_estimate` 19.0.1.0.82). Dettaglio: [COSIMO_PUNTO16_STAMPA_OFFERTA.md](COSIMO_PUNTO16_STAMPA_OFFERTA.md).

Tab condizioni strutturate + report **Offerta / Preventivo (SBU)** con flag verde/rosso.

---

### Punto 17 — Delivery standard

**Stato:** implementato (`sbu_purchase_flow` 19.0.1.0.53). Dettaglio: [COSIMO_PUNTO17_DELIVERY_STANDARD_IT.md](COSIMO_PUNTO17_DELIVERY_STANDARD_IT.md).

**Esempi Cosimo**  
- Alluminio + ACO: sistemista → terzista cantiere (4–5 fermate) → cantiere.  
- Vetro: vetraio → cantiere **oppure** vetraio → stesso terzista alluminio → cantiere.

**Odoo oggi**  
Regole `sbu.delivery.standard`, terzista/sistemista e modalità vetro su commessa, DESTINAZIONE auto su righe RDA + pulsanti di ricalcolo.

---

### Punto 18 — Revisioni visibili ovunque

**Stato:** implementato (`sbu_estimate` 19.0.1.0.86). Dettaglio: [COSIMO_PUNTO18_REVISIONI_LABEL_IT.md](COSIMO_PUNTO18_REVISIONI_LABEL_IT.md).

**Odoo oggi**  
Etichetta `codice · REV · data` su commesse e preventivi; SAL/RDA/fatture/CDP mostrano lo stesso riferimento; Jobs filtra di default la revisione più recente.

---

## 5. Piano di lavoro proposto

### Fase P0 — Fiducia e controllo (4–6 settimane)

- [ ] Fix import costi / margini / retention (test P1002)  
- [x] Label REV + data su commessa e documenti collegati (`sbu_estimate` 19.0.1.0.86)  
- [ ] Dimensioni L×H + mq su RDA → RFQ → PO  
- [ ] Cruscotto budget per famiglia + blocco PO admin  
- [x] SAL passivo (posa) — modello minimo (`sbu.sal.passive.sheet`)  

### Fase P1 — Acquisti produzione

- [ ] Stati RDA «revisione tecnica» + import Excel tecnico  
- [ ] Wizard tipi documento (LA, LZ, OSC, …)  
- [x] Regole delivery standard (`sbu_purchase_flow` 19.0.1.0.53)  
- [x] Stampa offerta con flag/condizioni strutturate (`sbu_estimate` 19.0.1.0.82)  
- [ ] Stampa fattura per voce contratto + SAL  
- [x] Residuo qty su RDA dopo PO parziale (`sbu_purchase_flow` 19.0.1.0.44)  
- [ ] Logikal → dimensioni BOM (dopo P0.2)  

### Fase P2 — UX e dati

- [ ] Celle verdi «da compilare»  
- [ ] Bulk edit su liste filtrate  
- [ ] Qonto: import partners (opzionale)  

### Fase P3 — Integrazioni

- [ ] Planner: solo link, no sync  
- [ ] Qonto: riconciliazione banca completa  

---

## 6. Cosa funziona già (da non dimenticare in riunione)

Per equilibrio con i gap, in demo/UAT risultano **solidi**:

- Import ANACO → preventivo + SAL + distinta  
- Vinto → commessa con contatori (Tasks, SAL, RDA, PO, Receipts)  
- Foglio SAL con % periodo → fattura → CDP  
- RDA da distinta BOM (centinaia di righe)  
- RFQ multi-fornitore; prezzi da **offerta fornitore** (non da costo interno)  
- Chiusura commessa con checklist DOP  
- Ricevimenti magazzino + DDT (modulo logistica)  
- Qonto: import movimenti + suggest match (non ancora reconcile completo)  

---

## 7. Prossimo passo consigliato con Cosimo

**Workshop 90 minuti** su commessa pilota **P0015_2026** / **PRV/2026/0024**:

1. Validare modello a due livelli (ANACO vs documento tecnico).  
2. Un file Excel tecnico reale → definire mapping import.  
3. Una famiglia costo (es. VT) → regole mq e colonne RFQ.  
4. Foglio ITEM ANACO → mockup cruscotto budget.  
5. Firmare priorità P0 per il prossimo sprint.

---

## 8. Riferimenti file codice (per team tecnico)

| Argomento | Modulo / file |
|-----------|----------------|
| Dimensioni preventivo/distinta | `sbu_estimate` — `sbu_estimate_line`, `sbu_estimate_bom_line` |
| RDA / dimension_mm | `sbu_purchase_flow` — `sbu_purchase_request_line` |
| Routing LA/LZ/VT… | `sbu_workflow_routing.py` |
| Alert budget PO | `sbu_purchase_flow` — `purchase_order.py` |
| SAL / fattura / CDP | `sbu_sal` |
| Qonto | `sbu_qonto` — vedi `docs/UAT_BANKING_C.md` |
| Chiusura | `sbu_closure` |
| Logikal | `sbu_logikal` |

---

*Documento generato per risposta strutturata al feedback Cosimo. Aggiornare versione e checkbox al completamento degli sprint.*
