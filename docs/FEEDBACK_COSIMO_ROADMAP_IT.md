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
| 3 | Filtri a tendina + applica scelta a tutto il filtrato | Utile | Filtri lista standard; bulk edit SBU no | **P1** |
| 4 | Item / Topic / Area su purchase requests | Da chiarire UX | Campi `excel_item`, `topic`; route = `workflow_route` / `request_type` | **P2** |
| 5 | Mancano LA/LZ/ST/PAN/OSC; creazione guidata tipi | **Corretto** | Routing parziale (`LZ→FE`, `ST→ST`, `PAN→RDA`…); non tutti i tipi | **P1** |
| 6 | SAL passivo (posa, subappalto) | **Corretto** | SAL attivo cliente sì; fatture passive fornitore no | **P0** |
| 7 | Celle verdi = compilazione manuale | Ottima UX | Non implementato | **P2** |
| 8 | Planner Microsoft ↔ Odoo | Realistico | Solo deep link / processo; sync bidirezionale fragile | **P3** |
| 9 | Logikal | Rimandato | Modulo presente; dimensioni finali su BOM = TODO | **P1** |
| 10 | Qonto: riconciliazione auto; abbandono what-if | Parziale | Import + suggerimento match; **no** riconciliazione banca auto | **P1** (bank) |
| 11 | Budget per tipologia (semafori ITEM) + sblocco solo admin | **Corretto** | Alert PO ~5% vs riferimento; no cruscotto famiglie | **P0** |
| 12 | Costi / margini / retention import sbagliati | **Bug da verificare** | Formule import complesse; serve test file P1002 | **P0** |
| 13 | Stampa fattura per voce contratto + SAL/CDP; dashboard | Da estendere | Fattura da foglio SAL; layout voci contratto da rifinire | **P1** |
| 14 | Qonto → fornitori/clienti automatici | Opzionale | Non implementato | **P2** |
| 15 | Cambio qty RDA/RFQ: residuo aperto; qty 1,03 | Spiegabile | 1,03 = perdita%/confezione distinta; residuo da confermare | **P1** |
| 16 | Stampa offerta: flag verdi/rossi + pagamenti/ritenute | Gap | Condizioni spesso testo scollegato | **P1** |
| 17 | Delivery standard (sistemista → terzista → cantiere; vetro) | **Corretto** | Campo `destination` su riga RDA; regole no | **P1** |
| 18 | Revisioni: label job/SAL/doc con REV + data | **Corretto** | REV su preventivo; confusione su commessa/SAL | **P0** |

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

**Proposta**  
Wizard «Nuovo documento acquisto» con elenco **chiuso** dei tipi + campi obbligatori per tipo; aggiungere OSC e LA come tipi dedicati se richiesto da Cosimo.

---

### Punto 6 — SAL passivo (posa / subappalto)

**Feedback**  
Il SAL deve gestire anche il **passivo**, in particolare servizi di posa (appalti/subappalti).

**Stato attuale**  
SAL cliente: foglio SAL → fattura attiva → CDP.  
Fatture fornitore / posa: flusso Odoo standard `in_invoice`, **non** integrato come «SAL passivo» periodo.

**Proposta**  
| Elemento | Descrizione |
|----------|-------------|
| Foglio SAL passivo | Periodo + % o importo su voci subappalto |
| Collegamento | `in_invoice` fornitore ↔ commessa ↔ famiglia costo POS |
| Report | Avanzamento posa vs budget ANACO |

---

### Punto 7 — Celle verdi (compilazione manuale)

**Proposta**  
Campo calcolato `richiede_input` su righe preventivo/RDA; decorazione lista **verde** se vuoto; **grigio** se valorizzato da import tecnico o Logikal.

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

**Stato attuale**  
Alert su PO se totale > ~105% di un riferimento singolo (`sbu_budget_over_limit`).

**Proposta**  
| Schermata | Contenuto |
|-----------|-----------|
| Cruscotto commessa | Per famiglia costo: budget ANACO, impegnato (RDA/PO), consuntivo, residuo, % |
| Semaforo | Verde / giallo / rosso |
| Blocco | Conferma PO oltre soglia solo gruppo Admin SBU |

---

### Punto 12 — Costi, margini, retention in import

**Azione**  
1. File Excel pilota (P1002 / PRV reale) + export Odoo.  
2. Confronto riga per riga: costo tot, margine %, cap garanzia, retention.  
3. Ticket bug su formule import (`sbu_estimate` wizard ANACO).  
4. Test automatici regressione su import.

---

### Punto 13 — Stampa fattura e dashboard

**Proposta fattura**  
Intestazione: commessa, **SAL/xx/xxxx**, periodo, **CDP** se presente.  
Righe: **ogni voce contrattuale** con descrizione, U.M., qty, prezzo unitario, totale; riga ritenuta.  

**Dashboard**  
Usare cruscotto Odoo standard + report SBU (fatturato, residuo SAL, budget acquisti) — da definire in fase P1.

---

### Punto 14 — Fornitori/clienti da Qonto

**Risposta**  
Oggi **no** import automatico anagrafiche. Opzionale in fase 2 API Qonto (beneficiari) con deduplica manuale.

---

### Punto 15 — Quantità 1,03 e residuo RDA

**Spiegazione qty 1,03**  
Di solito è **quantità da distinta**: perdita %, arrotondamento confezione o MOQ (es. 10 × 1,03). Non è un errore di unità di misura se documentato.

**Residuo**  
Se Cosimo cambia qty su RFQ e vuole il **residuo** sulla RDA: verificare/implementare righe parziali ordinate vs da ordinare.

---

### Punto 16 — Stampa offerta (flag e condizioni)

**Proposta**  
Tab «Condizioni commerciali» strutturate: pagamento, ritenute, garanzia, flag verde/rosso come ANACO; report QWeb offerta che legge questi campi (non solo testo libero).

---

### Punto 17 — Delivery standard

**Esempi Cosimo**  
- Alluminio + ACO: sistemista → terzista cantiere (4–5 fermate) → cantiere.  
- Vetro: vetraio → cantiere **oppure** vetraio → stesso terzista alluminio → cantiere.

**Proposta**  
Tabella regole: `famiglia_costo` × `request_type` → destinazione default, percorso magazzino (2 step), partner tipo «terzista cantiere».

---

### Punto 18 — Revisioni visibili ovunque

**Proposta**  
Nome visualizzato:  
`[P0015_2026] BLACKROCK · REV02 · 2026-05-20`  
su commessa, preventivo, foglio SAL, RDA, fattura (campo related). Filtro «solo revisione corrente» in liste Jobs.

---

## 5. Piano di lavoro proposto

### Fase P0 — Fiducia e controllo (4–6 settimane)

- [ ] Fix import costi / margini / retention (test P1002)  
- [ ] Label REV + data su commessa e documenti collegati  
- [ ] Dimensioni L×H + mq su RDA → RFQ → PO  
- [ ] Cruscotto budget per famiglia + blocco PO admin  
- [ ] SAL passivo (posa) — modello minimo  

### Fase P1 — Acquisti produzione

- [ ] Stati RDA «revisione tecnica» + import Excel tecnico  
- [ ] Wizard tipi documento (LA, LZ, OSC, …)  
- [ ] Regole delivery standard  
- [ ] Stampa offerta con flag/condizioni strutturate  
- [ ] Stampa fattura per voce contratto + SAL  
- [ ] Residuo qty su RDA dopo PO parziale  
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
