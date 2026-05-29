# Report feedback Cosimo — Risposta implementazione e guida verifica

**Cliente:** Suburban SRL  
**Destinatario:** Cosimo (operativo)  
**Data report:** maggio 2026 (agg. TMS Excel — `sbu_purchase_flow` 19.0.1.0.99)  
**Ambiente:** Odoo 19 — Odoo.sh (`pignatelli111-my-odoo.odoo.com`)  
**Repository:** `pignatelli111/my-odoo` — ramo **`real`** / **`production`**

---

## Legenda stati

| Simbolo | Significato |
|---------|-------------|
| ✅ | Implementato e utilizzabile (base o completo) |
| ⚠️ | Implementato in parte — serve UAT o fase successiva |
| ❌ | Non implementato / solo documentato |
| 📖 | Dettaglio tecnico in documento collegato |

---

## Prima di verificare (una volta)

1. **Apps → Aggiorna elenco app** → cercare **SBU** → **Aggiorna** i moduli indicati sotto (dopo ogni deploy Git).
2. Moduli principali: `sbu_estimate`, `sbu_purchase_flow`, `sbu_sal`, `sbu_qonto`, `sbu_project`, `sbu_documents`, `sbu_logikal` (opzionale).
3. Menu operativo: app **SBU** (non solo Contabilità / Acquisti standard).
4. Guida test passo-passo: [guide/GUIDA_TEST_AUTONOMO_COSIMO.md](guide/GUIDA_TEST_AUTONOMO_COSIMO.md).

---

## Punto 1 — Documenti tecnici (RDA/ACO/ACP/VT/LA/LZ/FE) vs ANACO

**Feedback Cosimo**  
ANACO = stima per preventivo/contratto. I documenti dei consulenti tecnici (Excel o DWG/DF) sono i **dati veri** per il PO, dopo approvazione disegni e possibili varianti. Dalla distinta preventivo alle RDA: quando inserire misure/costi reali? Regole vetro (90% mq), zanzariere/oscuranti (+300 mm H), Logikal da verificare.

**Risposta — cosa abbiamo fatto** ✅  
- Flusso a **fasi** su distinta e RDA: stima ANACO → revisione tecnica → **Pronto per RFQ/PO**.  
- Regole automatiche su prodotti distinta: **SBU-VETRO** (90% mq posizione), **SBU-ZANZ** / **SBU-OSC** (+300 mm altezza).  
- Campi **Confermato per PO**, **Fase dati** (stima / Logikal / tecnico).  
- RDA da distinta; blocco RFQ se non in stato «pronto».  
- **Import Excel TMS completo** (file tecnici `M.4.3.x` / `M.4.4.x`): RDA, ACO, ACP, LDS, registro tavole, catalogo VdC, Elenco elementi, date consegna 1–4, N° ordine, logistica DDT. Wizard **Import TMS Excel** su commessa e **Import from Excel** su singola RDA. Modulo ≥ **19.0.1.0.99**.  
- **Fuori scope:** DWG cartigli; Logikal resta pre-fill (punto 9), non verità finale PO.

**Come verificare**  
1. Upgrade `sbu_purchase_flow` → **19.0.1.0.99**.  
2. Commessa → **TMS import** → file `M.4.3.C_TMS_RDA_LEED (...)_02.xlsx`.  
3. Preventivo vinto → commessa → RDA da distinta **oppure** import Excel tecnico.  
4. Distinta ITEM: righe vetro/zanzariere → MQ e flag tecnico.  
5. RDA → **Pronto per RFQ/PO** → RFQ; senza passaggio → blocco.

📖 [TMS_EXCEL_INTEGRATION_ROADMAP.md](TMS_EXCEL_INTEGRATION_ROADMAP.md) — Moduli: `sbu_estimate`, `sbu_purchase_flow` ≥ 19.0.1.0.99

---

## Punto 2 — Colonne dimensioni su RDA / RFQ / PO

**Feedback Cosimo**  
In RDA/RFQ mancano larghezza, altezza, profondità (non unitaria), mq/cad, mq/tot.

**Risposta — cosa abbiamo fatto** ✅ (con attenzione colonne opzionali)  
- Su **righe RDA**: L, H, P (mm), mq/cad, mq tot., riepilogo **Dimensioni**.  
- Alla creazione **RFQ/PO** i valori si **copiano** dalla RDA.  
- Su **righe ordine acquisto**: colonne SBU dimensioni (se la vista le mostra — usare **opzionale colonne** nel listino).

**Come verificare**  
1. Riga RDA con B/H compilati → **Crea bozza RFQ**.  
2. Aprire righe RFQ/PO → verificare **L mm, H mm, P mm, MQ/cad, MQ tot.**  
3. Se non visibili: icona colonne nel listino → attivare campi SBU.

📖 [COSIMO_PUNTO1_DATI_TECNICI.md](COSIMO_PUNTO1_DATI_TECNICI.md) — Modulo: `sbu_purchase_flow` ≥ 19.0.1.0.28+

---

## Punto 3 — Filtri a tendina + applica scelta a tutto il filtrato

**Feedback Cosimo**  
Filtri sezionabili (come area Acquisti) e possibilità di applicare una scelta (es. data consegna) a tutto il risultato filtrato.

**Risposta — cosa abbiamo fatto** ✅  
- **Pannello sinistro** (searchpanel) su richieste acquisto e righe: tipo documento, route, priorità, commessa, dati tecnici.  
- Menu **SBU → Acquisti → Righe richiesta (modifica massiva)**.  
- Wizard **Applica al risultato filtrato** (data consegna, destinazione, priorità, ecc.).

**Come verificare**  
1. Aprire **Righe richiesta** → filtrare es. solo RDA senza data.  
2. **Azione → Applica al risultato filtrato** → impostare data → applicare.  
3. Controllare che tutte le righe filtrate siano aggiornate.

📖 [COSIMO_PUNTO1_DATI_TECNICI.md](COSIMO_PUNTO1_DATI_TECNICI.md) — Modulo: `sbu_purchase_flow` ≥ 19.0.1.0.28+

---

## Punto 4 — Item, Topic, Area (purchase requests)

**Feedback Cosimo**  
Non chiaro come usare Item / Topic / Area.

**Risposta — cosa abbiamo fatto** ✅ (spiegazione + campi)  

| Campo in Odoo | Cosa mettere |
|---------------|--------------|
| **Item (foglio Excel)** | Codice voce template (es. LA01, FT) — traccia il file del tecnico |
| **Topic** | Argomento / facciata (es. «Facciata nord») |
| **Route** (`workflow_route`) | LA, LZ, ST, PAN, OSC, VC/VS… |
| **Tipo documento** | RDA, ACO, ACP, VT, FE, ST, LDS |

Non sono trigger automatici: servono per **ricerca, filtri e report**. Creare documenti con wizard **Nuovo documento acquisto** (punto 5).

**Come verificare**  
1. Aprire una RDA → compilare **Item** e **Topic** in testata.  
2. Listino **Richieste acquisto** → cercare per Topic / Item.  
3. Leggere help in testata RDA (testo guida in form).

📖 [FEEDBACK_COSIMO_ROADMAP_IT.md](FEEDBACK_COSIMO_ROADMAP_IT.md) (punto 4) — Modulo: `sbu_purchase_flow`

---

## Punto 5 — LA / LZ / ST / PAN / OSC negli elenchi e creazione guidata

**Feedback Cosimo**  
Mancano negli elenchi; serve creazione guidata per non creare dati sporchi; possibilità di altri tipi con passi corretti.

**Risposta — cosa abbiamo fatto** ✅  
- Catalogo **`sbu.workflow.route`**: LA, LZ, ST, PAN, OSC, VC/VS, ZANZ, PRF, FT, SE, ASS, ACC, GUA, POS, TRN, PM, CNT, EXT (dati iniziali + estendibile).  
- Menu **SBU → Acquisti → Workflow routes** (responsabili acquisti): aggiungere route, tipo documento, obbligo Topic/data.  
- Wizard **Nuovo documento acquisto** e campo **Route** su RDA leggono il catalogo; validazione obblighi per route.  
- Da commessa: **By workflow** — un documento per route; **salta** se esiste già RDA aperta stessa commessa+route.

**Come verificare**  
1. **Workflow routes** → verificare LA con «Topic obbligatorio».  
2. **Nuovo documento acquisto** → route **LA** senza Topic → errore; con Topic → OK.  
3. Commessa → **By workflow** due volte → una sola RDA LA aperta.  
4. (Opz.) Creare route **TST** nel catalogo → compare nel wizard.

📖 [COSIMO_PUNTO1_DATI_TECNICI.md](COSIMO_PUNTO1_DATI_TECNICI.md) — Modulo: `sbu_purchase_flow` ≥ **19.0.1.0.95**

---

## Punto 6 — SAL passivo (posa / subappalto)

**Feedback Cosimo**  
Il SAL deve gestire anche il **passivo**, in particolare servizi di **posa** (appalti/subappalti).

**Risposta — cosa abbiamo fatto** ✅  
- Modello **SAL passivo**: commessa, fornitore, scope posa/subappalto, % avanzamento, budget da ANACO.  
- **Carica budget POS** → **Conferma** → **Crea fattura fornitore**.  
- **Blocco % cumulato > 100%** per riga budget (conferma + validazione righe).  
- Tab commessa **Avanzamento posa (passivo)**: budget, fatturato, % avanzamento, link fogli SAL passivi.

**Come verificare**  
1. Commessa con preventivo vinto e righe **posa** / famiglia **installation**.  
2. Passive SAL → **Load POS budget** → % questo SAL → Conferma → fattura fornitore.  
3. Secondo SAL stessa voce con % che supera 100% cumulato → messaggio di blocco.  
4. Commessa → tab **Avanzamento posa (passivo)** → totali coerenti.

📖 [FEEDBACK_COSIMO_ROADMAP_IT.md](FEEDBACK_COSIMO_ROADMAP_IT.md) (punto 6) — Modulo: `sbu_sal` ≥ **19.0.1.0.67**

---

## Punto 7 — Celle verdi per compilazione manuale

**Feedback Cosimo**  
Colore verde sulle celle che richiedono compilazione manuale.

**Risposta — cosa abbiamo fatto** ✅ (equivalente operativo a Excel)  
- **Riga verde** = da compilare manualmente; **riga grigia** = import / Logikal.  
- Su ANACO, distinta ITEM, righe RDA, righe PO, matrice **offerte fornitore**.  
- Celle **B (mm)** e **H (mm)** evidenziate in arancione se mancanti e riga in attesa manuale.  
- Filtri: «Manual entry pending (green)», «From import / Logikal (grey)».  
- **Non:** replica pixel-per-pixel di ogni cella Excel su tutte le colonne RFQ.

**Come verificare**  
1. Preventivo → riga MQ senza B/H → riga verde + colonne B/H evidenziate.  
2. Compilare B e H → evidenziazione sparisce.  
3. **Righe richiesta** e **Offerte fornitore** → verde/grigio coerente con RDA.

📖 [FEEDBACK_COSIMO_ROADMAP_IT.md](FEEDBACK_COSIMO_ROADMAP_IT.md) (punto 7) — Moduli: `sbu_estimate`, `sbu_purchase_flow`

---

## Punto 8 — Microsoft Planner ↔ Odoo

**Feedback Cosimo**  
Ha provato Planner con Odoo; non crede funzioni integrazione completa.

**Risposta — cosa abbiamo fatto** ⚠️ (collaborazione, non sync bidirezionale)  
- **Link** Teams / Planner / Outlook su commessa (Document hub).  
- Import opzionale **CSV → task** progetto (wizard).  
- **Non** sincronizzazione bidirezionale Planner ↔ Odoo (fragile e non promessa).

**Come verificare**  
1. Commessa → tab documenti / M365 → aprire link Planner.  
2. Se serve: wizard import task da CSV (IT configura Graph in Impostazioni → SBU).

📖 [FEEDBACK_COSIMO_ROADMAP_IT.md](FEEDBACK_COSIMO_ROADMAP_IT.md) (punto 8) — Modulo: `sbu_documents`, `sbu_integrations`

---

## Punto 9 — Logikal

**Feedback Cosimo**  
«Lo vediamo quando sei pronto».

**Risposta — cosa abbiamo fatto** ⚠️  
- Modulo **`sbu_logikal`**: import **CSV/JSON** o bridge API opzionale; mappatura profili → prodotti; applica righe su distinta.  
- **Non** lettura diretta file SQLite Orgadata; **non** automazione completa senza export Logikal.  
- ERP Interface licence Logikal + eventuale bridge = fase congiunta.

**Come verificare (quando pronti)**  
1. **Logikal → Imports** → caricare export → Match products → Apply.  
2. Vedi README progetto sezione Logikal.

📖 [FEEDBACK_COSIMO_ROADMAP_IT.md](FEEDBACK_COSIMO_ROADMAP_IT.md) (punto 9) — Modulo: `sbu_logikal` (opzionale)

---

## Punto 10 — Qonto: pagamenti automatici e abbandono what-if

**Feedback Cosimo**  
Pagamenti ricevuti riconciliati con Qonto; smettere scenari what-if fatture in Qonto; fatturazione in Odoo.

**Risposta — cosa abbiamo fatto** ✅ (SBU Qonto, non «Collega banca» Odoo)  
- Modulo **`sbu_qonto`**: import movimenti (API + cron + webhook opzionale).  
- **Auto-registrazione pagamenti cliente** (entrate, alta confidenza) → fattura saldata in Odoo.  
- **Non usare** Contabilità → Collega banca → Qonto (richiede Enterprise).  
- **Non ancora:** riconciliazione estratto conto bancario riga-per-riga.

**Come verificare**  
1. **Azienda → Qonto (SBU)**: login API, secret, IBAN, cron attivo.  
2. **Import Qonto movements now** → **Contabilità → Movimenti Qonto**.  
3. Fattura cliente postata + bonifico coerente → movimento **Matched**, residuo fattura = 0.  
4. **Non** configurare webhook finché import manuale non funziona.

📖 [COSIMO_PUNTO10_QONTO.md](COSIMO_PUNTO10_QONTO.md) — Modulo: `sbu_qonto` ≥ 19.0.1.0.7+

---

## Punto 11 — Budget per tipologia (semafori ITEM) e sblocco admin

**Feedback Cosimo**  
Come foglio ITEM: preventivo, acquistato, residui, %; semafori; solo admin sblocca se sforamento.

**Risposta — cosa abbiamo fatto** ✅  
- Cruscotto **Budget per famiglia** su commessa + tab preventivo **Budget acquisti (ITEM)**.  
- Colonne: preventivo, RDA, PO bozza, **ordini emessi**, **costi sostenuti (consuntivo)**, residui, **semaforo**.  
- Conferma PO **bloccata** se famiglia rossa; sblocco: **Administrator** o gruppo **SBU — Sblocco budget acquisti** + flag su commessa.

**Come verificare**  
1. Commessa con preventivo e PO → **Purchase budget** / tab budget.  
2. Verificare semafori e importi consuntivo dopo fattura fornitore registrata.  
3. Famiglia rossa → tentare conferma PO → blocco; sbloccare con utente autorizzato.

📖 [COSIMO_PUNTO11_BUDGET_ACQUISTI.md](COSIMO_PUNTO11_BUDGET_ACQUISTI.md) — Modulo: `sbu_purchase_flow` ≥ 19.0.1.0.91+

---

## Punto 12 — Costi, margini, retention in import ANACO

**Feedback Cosimo**  
Dopo import, costi, margini % e retention risultano sbagliati.

**Risposta — cosa abbiamo fatto** ⚠️  
- Miglioramenti import: colonna **BS**, staffame ST/LZ, **ritenuta %** da foglio SAL, avviso se BS mancante.  
- Margine e costo totale sono **ricalcolati** in Odoo (non copia 1:1 ogni formula Excel).  
- **MOL** non incluso nel costo totale come in alcuni fogli Excel.  
- Validazione numerica automatica P1002 = ancora da consolidare in UAT.

**Come verificare**  
1. Re-import file P1002 → controllare **Prezzo unit. ANACO (col. BS)** su righe campione.  
2. Tab **Voci contrattuali SAL** → **Retention %** se diversa da contratto.  
3. Confrontare 1 riga pilota Excel vs Odoo (prezzo TOT, costo TOT, margine %).

📖 [COSIMO_PUNTO12_COSTI_MARGINI_RETENTION.md](COSIMO_PUNTO12_COSTI_MARGINI_RETENTION.md) — Modulo: `sbu_estimate` ≥ 19.0.1.0.109+

---

## Punto 13 — Stampa fattura per voce + SAL + CDP + cruscotto

**Feedback Cosimo**  
In fattura ogni voce contratto con descrizione/valori/U.M./totali; testata SAL e CDP; avanzamenti visibili da cruscotto.

**Risposta — cosa abbiamo fatto** ✅ (PDF e dati; cruscotto base)  
- Fattura: **una riga contabile per voce contrattuale** del periodo SAL.  
- Report **«Fattura con dettaglio SAL (SBU)»** + blocco SAL/CDP su PDF standard.  
- Tab commessa **Avanzamento fatturazione** (contratto / fatturato / residuo / SAL).  
- CDP collegato a SAL e fattura.

**Come verificare**  
1. Foglio SAL confermato → crea fattura cliente.  
2. Stampa **Dettaglio SAL** dalla fattura o dal foglio SAL.  
3. Commessa → tab avanzamento fatturazione.

📖 [COSIMO_PUNTO13_FATTURA_SAL_CDP.md](COSIMO_PUNTO13_FATTURA_SAL_CDP.md) — Modulo: `sbu_sal` ≥ 19.0.1.0.64+

---

## Punto 14 — Fornitori (e clienti) da Qonto

**Feedback Cosimo**  
Integrando Qonto si recuperano automaticamente fornitori/clienti?

**Risposta — cosa abbiamo fatto** ✅ (fornitori da beneficiari)  
- Sync **beneficiari SEPA** Qonto → contatti **fornitore** in Odoo.  
- Pulsante **Sync Qonto suppliers**; opzione sync ad ogni import.  
- **Clienti:** solo se presenti come beneficiari (di solito sono i fornitori pagati).

**Come verificare**  
1. Configurare credenziali Qonto (punto 10).  
2. **Sync Qonto suppliers** → Contatti → nuovi/aggiornati fornitori.

📖 [COSIMO_PUNTO10_QONTO.md](COSIMO_PUNTO10_QONTO.md) — Modulo: `sbu_qonto`

---

## Punto 15 — Residuo RDA e quantità 1,03

**Feedback Cosimo**  
Se cambio qty su RFQ resta riga aperta per residuo; non capisce U.M. = 1,03.

**Risposta — cosa abbiamo fatto** ✅  
- **1,03** = quantità richiesta (es. 1,00 + **3% perdita** fabbisogno default), **non** unità di misura.  
- Campi **Qty on RFQ/PO** e **Qty remaining**; seconda RFQ riusa residuo.

**Come verificare**  
1. RDA con qty 1,03 → leggere colonna **U.M.** (pz, m²…) separata.  
2. RFQ parziale → su RDA **Qty remaining** > 0.  
3. Nuova RFQ stesso fornitore → qty proposta = residuo.

📖 [COSIMO_PUNTO15_RDA_RESIDUO_QTY.md](COSIMO_PUNTO15_RDA_RESIDUO_QTY.md) — Modulo: `sbu_purchase_flow` ≥ 19.0.1.0.44+

---

## Punto 16 — Stampa offerta (flag verdi/rossi, pagamenti, ritenute)

**Feedback Cosimo**  
Stampa offerta con scelte condizioni ANACO (verde/rosso), pagamenti e ritenute collegati.

**Risposta — cosa abbiamo fatto** ✅  
- Tab **Condizioni di Fornitura**: righe strutturate Incluso/Escluso/Nota.  
- **Carica condizioni standard** → **Stampa offerta** PDF con flag colore.  
- Ritenuta offerta allineata alla riga verde «Ritenuta».

**Come verificare**  
1. Preventivo → **Condizioni di Fornitura** → **Carica condizioni standard**.  
2. **Stampa offerta** → PDF con tabella condizioni colorata.  
3. Verificare % ritenuta in testata vs riga verde.

📖 [COSIMO_PUNTO16_STAMPA_OFFERTA.md](COSIMO_PUNTO16_STAMPA_OFFERTA.md) — Modulo: `sbu_estimate` ≥ 19.0.1.0.82+

---

## Punto 17 — Delivery standard (sistemista → terzista → cantiere; vetro)

**Feedback Cosimo**  
Regole consegna: alluminio/ACO via sistemista e terzista; vetro diretto o via terzista.

**Risposta — cosa abbiamo fatto** ✅  
- Tabella **Delivery standard** (regole per route/famiglia).  
- Commessa → **Logistica / delivery**: terzista, sistemista, modalità vetro.  
- **Applica delivery standard** su RDA → colonna **Destinazione** compilata.

**Come verificare**  
1. **SBU → Purchasing → Delivery standard** → vedere regole LA/VT.  
2. Commessa → tab logistica → impostare terzista → **Applica delivery standard su tutte le RDA**.  
3. Aprire righe RDA → testo **Destinazione** popolato.

📖 [COSIMO_PUNTO17_DELIVERY_STANDARD_IT.md](COSIMO_PUNTO17_DELIVERY_STANDARD_IT.md) — Modulo: `sbu_purchase_flow` ≥ 19.0.1.0.53+

---

## Punto 18 — Revisioni visibili (REV + data su job e documenti)

**Feedback Cosimo**  
Su Jobs non è chiaro quale REV sia la più recente; stessa confusione su SAL, RDA, ecc.

**Risposta — cosa abbiamo fatto** ✅  
- Etichetta tipo `[P0015_2026] CLIENTE · REV02 · 2026-05-20` su Jobs, preventivi, SAL, RDA, fatture.  
- Filtro default Jobs: **Solo revisione più recente**.  
- Flag su commessa **Revisione più recente**.

**Come verificare**  
1. **SBU → Jobs** → colonna commessa con REV e data.  
2. Creare REV02 → verificare badge ultima revisione.  
3. Aprire SAL/RDA → titolo documento con stessa etichetta REV.

📖 [COSIMO_PUNTO18_REVISIONI_LABEL_IT.md](COSIMO_PUNTO18_REVISIONI_LABEL_IT.md) — Moduli: `sbu_estimate`, `sbu_project`, `sbu_sal`, `sbu_purchase_flow`

---

## Riepilogo veloce (18 punti)

| # | Argomento | Stato | Verifica rapida |
|---|-----------|-------|-----------------|
| 1 | Dati tecnici vs ANACO / PO | ✅ | Import TMS Excel su commessa |
| 2 | Dimensioni RDA/RFQ/PO | ✅ | Colonne L/H/P/MQ su RFQ |
| 3 | Filtri + applica filtrato | ✅ | Righe richiesta → wizard bulk |
| 4 | Item / Topic / Route | ✅ | Campi testata RDA + wizard |
| 5 | LA/LZ/ST/PAN/OSC | ✅ | Catalogo route + wizard + by workflow |
| 6 | SAL passivo posa | ✅ | Cap 100% + tab posa commessa |
| 7 | Righe verdi | ✅ | Verde/grigio + B/H evidenziati |
| 8 | Planner | ⚠️ | Link M365, no sync pieno |
| 9 | Logikal | ⚠️ | Import CSV quando pronti |
| 10 | Qonto | ✅ | Tab Qonto SBU, movimenti |
| 11 | Budget semafori | ✅ | Purchase budget commessa |
| 12 | Import costi/margini | ⚠️ | Confronto riga P1002 |
| 13 | Fattura SAL/CDP | ✅ | PDF Dettaglio SAL |
| 14 | Fornitori Qonto | ✅ | Sync suppliers |
| 15 | Residuo / 1,03 | ✅ | Qty remaining su RDA |
| 16 | Stampa offerta | ✅ | Condizioni + PDF |
| 17 | Delivery standard | ✅ | Tab logistica commessa |
| 18 | Label REV | ✅ | Lista Jobs |

---

## Prossimi passi consigliati (con Suburban)

1. **Upgrade moduli SBU** su database produzione dopo ogni deploy (**`sbu_purchase_flow` 19.0.1.0.99**).  
2. **UAT a campione** su una commessa reale: punti 1→2→5→11→10→13 (import TMS Excel incluso).  
3. **Logikal** (punto 9): pianificare con file campione e licenza ERP Logikal.  
4. **Punto 12**: sessione 2h su una riga ANACO Excel vs Odoo con file P1002.

---

## Documenti collegati

| Documento | Contenuto |
|-----------|-----------|
| [FEEDBACK_COSIMO_ROADMAP_IT.md](FEEDBACK_COSIMO_ROADMAP_IT.md) | Roadmap completa |
| [guide/GUIDA_TEST_AUTONOMO_COSIMO.md](guide/GUIDA_TEST_AUTONOMO_COSIMO.md) | Test autonomo con screenshot |
| [TMS_EXCEL_INTEGRATION_ROADMAP.md](TMS_EXCEL_INTEGRATION_ROADMAP.md) | Integrazione Excel TMS tecnici |
| [GUIDA_REINSTALLAZIONE_APPS_E_IMPOSTAZIONI_IT.md](GUIDA_REINSTALLAZIONE_APPS_E_IMPOSTAZIONI_IT.md) | Installazione moduli |

---

*Report generato per risposta al feedback originale Cosimo — maggio 2026.*
