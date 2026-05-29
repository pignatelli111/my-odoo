# Report sul feedback Odoo SBU

**Gentile Cosimo,**

La ringraziamo per il tempo dedicato e per il feedback dettagliato sui 18 punti. Questo documento riassume, punto per punto, cosa abbiamo già implementato in Odoo, cosa è parzialmente disponibile e come può verificarlo autonomamente sul sistema.

**Cliente:** Suburban SRL a Socio Unico  
**Data:** maggio 2026 (aggiornamento TMS Excel — `sbu_purchase_flow` 19.0.1.0.99)  
**Sistema:** Odoo 19 — moduli SBU custom  

---

## Legenda

| Simbolo | Significato |
|---------|-------------|
| ✅ | Disponibile e utilizzabile |
| ⚠️ | Disponibile in parte — utile una verifica insieme o in una fase successiva |
| ❌ | Non ancora previsto nella versione attuale |

---

## Prima di iniziare le verifiche

Le chiediamo gentilmente di eseguire questi passaggi **una sola volta**, prima di testare i singoli punti:

1. **Apps → Aggiorna elenco app** → cercare **SBU** → **Aggiorna** i moduli indicati (dopo ogni aggiornamento del software).
2. Moduli principali: `sbu_estimate`, `sbu_purchase_flow`, `sbu_sal`, `sbu_qonto`, `sbu_project`, `sbu_documents`.
3. Utilizzare il menu **SBU** (oltre ai menu standard Contabilità / Acquisti).
4. Per una guida passo-passo con screenshot: `docs/guide/GUIDA_TEST_AUTONOMO_COSIMO.md`.

---

## Riepilogo dei 18 punti

| # | Argomento | Stato |
|---|-----------|-------|
| 1 | Dati tecnici vs ANACO / PO | ✅ |
| 2 | Dimensioni su RDA/RFQ/PO | ✅ |
| 3 | Filtri + applica al filtrato | ✅ |
| 4 | Item / Topic / Area | ✅ |
| 5 | LA / LZ / ST / PAN / OSC | ✅ |
| 6 | SAL passivo (posa) | ✅ |
| 7 | Righe verdi compilazione manuale | ✅ |
| 8 | Microsoft Planner | ⚠️ |
| 9 | Logikal | ⚠️ |
| 10 | Qonto pagamenti automatici | ✅ |
| 11 | Budget semafori + sblocco admin | ✅ |
| 12 | Import costi / margini / retention | ⚠️ |
| 13 | Fattura per voce + SAL/CDP | ✅ |
| 14 | Fornitori da Qonto | ✅ |
| 15 | Residuo RDA e qty 1,03 | ✅ |
| 16 | Stampa offerta condizioni | ✅ |
| 17 | Delivery standard | ✅ |
| 18 | Label revisioni REV | ✅ |

---

## Punto 1 — Documenti tecnici (RDA/ACO/ACP/VT/LA/LZ/FE) vs ANACO

**Il Suo feedback**  
ANACO resta la stima per preventivo e contratto. I documenti dei consulenti tecnici (Excel o DWG/DF) contengono i dati reali per il PO, dopo l’approvazione dei disegni e le eventuali varianti. Le Sue domande: quando inserire misure e costi reali? Come gestire vetro (90% mq), zanzariere/oscuranti (+300 mm)?

**Stato attuale:** ✅ **Disponibile** (Excel TMS completo — maggio 2026)

**Cosa può già fare in Odoo**
- Flusso a fasi: stima ANACO → revisione tecnica → **Pronto per RFQ/PO**.
- Regole automatiche in distinta: **vetro** (90% mq posizione), **zanzariere/oscuranti** (+300 mm altezza).
- Campi **Confermato per PO** e **Fase dati** (stima / Logikal / tecnico).
- Creazione RDA da distinta; blocco RFQ finché non è impostato «pronto».
- **Import Excel TMS** allineato ai file dei tecnici (`M.4.3.x` RDA/ACO/ACP, `M.4.4.x` LDS, Report tavole, catalogo VdC):
  - Su commessa: pulsante **TMS import** oppure **SBU → Acquisti → Import TMS Excel**.
  - Su singola RDA/ACO/ACP: **Import from Excel** (auto-detect layout TMS).
  - Header: Item, Topic, Area, Project code, Drawn by, Check by, date consegna 1–4, LEED.
  - Righe: POS, articolo, qty, U.M., L/H/P, mq, VdC, peso, destinazione, N° ordine, note.
  - Registri: **LDS**, **Drawing register**, **VdC budget catalog** con semafori budget.
  - **Elenco elementi**: precompila «Drawn by» per route (ACO→Tecnomont, ACP→TEU DESIGN, …).
  - Blocco RFQ opzionale se tavola non approvata (flag su registro disegni).

**Cosa resta fuori scope Excel / fase successiva**
- File **DWG/DF** con tabelle interne (cartigli AutoCAD) — non importabili in ERP.
- **Logikal**: pre-compilazione distinta, non sostituto della conferma tecnica finale (punto 9).

**Come può verificare**
1. Aggiornare `sbu_purchase_flow` a **19.0.1.0.99** su Odoo.sh.
2. Aprire una commessa → **TMS import** → caricare `M.4.3.C_TMS_RDA_LEED (...)_02.xlsx`.
3. Controllare testata RDA (Item, Topic, date consegna) e righe (dimensioni, VdC, destinazione).
4. Ripetere con file ACO, ACP, LDS e Report tav appr dalla cartella tecnici.
5. Distinta ITEM: righe vetro → verificare MQ 90% e righe verdi da confermare.
6. Passare RDA a **Pronto per RFQ/PO** → creare RFQ; senza passaggio → messaggio di blocco.

**Moduli:** `sbu_estimate`, `sbu_purchase_flow` ≥ 19.0.1.0.99  
**Guida tecnica:** `docs/TMS_EXCEL_INTEGRATION_ROADMAP.md`

---

## Punto 2 — Colonne dimensioni su RDA / RFQ / PO

**Il Suo feedback**  
In RDA/RFQ mancavano larghezza, altezza, profondità, mq/cad e mq/tot.

**Stato attuale:** ✅ **Disponibile**

**Cosa può già fare in Odoo**
- Righe RDA con L, H, P (mm), mq/cad, mq tot. e riepilogo **Dimensioni**.
- Alla creazione RFQ/PO i valori vengono **copiati** dalla RDA.
- Stesse colonne sulle righe ordine acquisto (se non le vede: attivare le colonne opzionali nel listino).

**Come può verificare**
1. Aprire una riga RDA con B/H compilati → **Crea bozza RFQ**.
2. Controllare su RFQ/PO: **L mm, H mm, P mm, MQ/cad, MQ tot.**

**Modulo:** `sbu_purchase_flow`

---

## Punto 3 — Filtri a tendina + applica scelta a tutto il filtrato

**Il Suo feedback**  
Desiderava filtri sezionabili e la possibilità di applicare una scelta (es. data consegna) a tutto il risultato filtrato.

**Stato attuale:** ✅ **Disponibile**

**Cosa può già fare in Odoo**
- Pannello sinistro su richieste acquisto e righe: tipo documento, route, priorità, commessa, dati tecnici.
- Menu **SBU → Acquisti → Righe richiesta (modifica massiva)**.
- Wizard **Applica al risultato filtrato**.

**Come può verificare**
1. Aprire **Righe richiesta** → filtrare (es. solo RDA senza data).
2. **Azione → Applica al risultato filtrato** → impostare la data → applicare.
3. Controllare che tutte le righe filtrate siano aggiornate.

**Modulo:** `sbu_purchase_flow`

---

## Punto 4 — Item, Topic, Area (purchase requests)

**Il Suo feedback**  
Non era chiaro l’uso di Item / Topic / Area.

**Stato attuale:** ✅ **Disponibile** (con guida in interfaccia)

**Significato dei campi**

| Campo | Cosa inserire |
|-------|---------------|
| **Item** | Codice voce del foglio tecnico (es. LA01, FT, F01) |
| **Topic** | Argomento / facciata (es. «Facciata nord») |
| **Area / zone** | Codice area dal template ACP (campo **Area / zone** in testata RDA) |
| **Route** | LA, LZ, ST, PAN, OSC, VC/VS… |
| **Tipo documento** | RDA, ACO, ACP, VT, FE, ST, LDS |

Servono per **ricerca, filtri e report** — non avviano azioni automatiche.

**Come può verificare**
1. Aprire una RDA → compilare **Item** e **Topic** in testata.
2. Cercare nel listino **Richieste acquisto** per Topic / Item.
3. Leggere il testo guida presente nel form RDA.

**Modulo:** `sbu_purchase_flow`

---

## Punto 5 — LA / LZ / ST / PAN / OSC e creazione guidata

**Il Suo feedback**  
Mancavano negli elenchi; serviva una creazione guidata per evitare dati inconsistenti.

**Stato attuale:** ✅ **Disponibile**

**Cosa può già fare in Odoo**
- Catalogo **Workflow routes** (LA, LZ, ST, PAN, OSC, VC/VS, ecc.) — estendibile.
- Wizard **Nuovo documento acquisto** con controlli obbligatori per route.
- Da commessa: **By workflow** — un documento per route, senza duplicati aperti.

**Come può verificare**
1. **Workflow routes** → verificare LA con «Topic obbligatorio».
2. **Nuovo documento acquisto** → route LA senza Topic → errore; con Topic → OK.
3. Da commessa → **By workflow** due volte → una sola RDA LA aperta.

**Modulo:** `sbu_purchase_flow`

---

## Punto 6 — SAL passivo (posa / subappalto)

**Il Suo feedback**  
Il SAL doveva gestire anche il passivo, in particolare i servizi di posa (appalti/subappalti).

**Stato attuale:** ✅ **Disponibile**

**Cosa può già fare in Odoo**
- **SAL passivo**: commessa, fornitore, % avanzamento, budget da ANACO.
- **Carica budget POS** → **Conferma** → **Crea fattura fornitore**.
- Blocco se la % cumulata supera il 100%.
- Tab commessa **Avanzamento posa (passivo)**.

**Come può verificare**
1. Commessa con righe posa → **SBU → Billing → Passive SAL**.
2. **Load POS budget** → impostare % → Conferma → fattura fornitore.
3. Secondo SAL sulla stessa voce oltre il 100% → messaggio di blocco.

**Modulo:** `sbu_sal`

---

## Punto 7 — Celle verdi per compilazione manuale

**Il Suo feedback**  
Desiderava evidenziare in verde le celle da compilare manualmente, come in Excel.

**Stato attuale:** ✅ **Disponibile**

**Cosa può già fare in Odoo**
- **Riga verde** = da compilare; **riga grigia** = da import / Logikal.
- Su preventivo, distinta, RDA, PO e offerte fornitore.
- B/H evidenziati se mancanti.
- Filtri dedicati nel listino.

**Come può verificare**
1. Riga preventivo MQ senza B/H → riga verde.
2. Compilare B e H → evidenziazione scompare.

**Moduli:** `sbu_estimate`, `sbu_purchase_flow`

---

## Punto 8 — Microsoft Planner ↔ Odoo

**Il Suo feedback**  
Aveva provato Planner con Odoo senza risultati soddisfacenti.

**Stato attuale:** ⚠️ **Collaborazione via link** (non sincronizzazione completa)

**Cosa può già fare in Odoo**
- Link Teams / Planner / Outlook sulla commessa.
- Import opzionale **CSV → task** progetto.

**Cosa non è previsto**
- Sincronizzazione bidirezionale Planner ↔ Odoo (troppo instabile per un uso affidabile in produzione).

**Come può verificare**
1. Commessa → tab documenti / M365 → aprire link Planner.
2. Se utile: wizard import task da CSV (configurazione Graph in Impostazioni → SBU).

**Moduli:** `sbu_documents`, `sbu_integrations`

---

## Punto 9 — Logikal

**Il Suo feedback**  
«Lo vediamo quando siete pronti».

**Stato attuale:** ⚠️ **Modulo presente, da affinare insieme**

**Cosa può già fare in Odoo**
- Import **CSV/JSON** o bridge API opzionale.
- Mappatura profili → prodotti; applicazione righe su distinta.

**Prossimo passo con Lei**
- Definire il flusso operativo e l’applicazione delle dimensioni finali.

**Modulo:** `sbu_logikal` (opzionale)

---

## Punto 10 — Qonto: pagamenti automatici

**Il Suo feedback**  
I pagamenti ricevuti dovrebbero riconciliarsi automaticamente; abbandonare gli scenari what-if in Qonto e gestire fatturazione in Odoo.

**Stato attuale:** ✅ **Disponibile** (modulo SBU Qonto)

**Cosa può già fare in Odoo**
- Import movimenti (API + cron).
- **Registrazione automatica pagamenti cliente** (entrate ad alta confidenza) → fattura saldata.
- Sync fornitori da beneficiari Qonto (punto 14).

**Nota importante**  
Utilizzare la scheda **Qonto (SBU)** sull’azienda — **non** il percorso standard Contabilità → Collega banca (richiede abbonamento Enterprise).

**Cosa resta per una fase successiva**  
Riconciliazione riga-per-riga dell’estratto conto bancario.

**Come può verificare**
1. **Azienda → Qonto (SBU)**: login API (Sign-in), secret, IBAN, cron attivo.
2. **Test Qonto connection** → messaggio OK.
3. **Import Qonto movements now** → **SBU → Banking → Qonto movements**.
4. Fattura cliente postata + bonifico corrispondente → movimento **Matched**, residuo = 0.

**Modulo:** `sbu_qonto`

---

## Punto 11 — Budget per tipologia (semafori) e sblocco admin

**Il Suo feedback**  
Desiderava un controllo budget come nel foglio ITEM, con semafori e sblocco acquisto solo per admin in caso di sforamento.

**Stato attuale:** ✅ **Disponibile**

**Cosa può già fare in Odoo**
- Cruscotto **Budget per famiglia** su commessa e tab preventivo.
- Preventivo, ordini, consuntivo, residui, **semaforo**.
- Blocco conferma PO se famiglia in rosso; sblocco per Administrator o gruppo dedicato.

**Come può verificare**
1. Commessa con preventivo e PO → tab **Budget acquisti**.
2. Dopo fattura fornitore → controllare consuntivo e semafori.
3. Famiglia rossa → tentare conferma PO → blocco; poi sblocco con utente autorizzato.

**Modulo:** `sbu_purchase_flow`

---

## Punto 12 — Costi, margini, retention in import ANACO

**Il Suo feedback**  
Dopo l’import, costi, margini e retention non coincidevano con Excel.

**Stato attuale:** ⚠️ **Migliorato, da validare insieme su file reale**

**Cosa abbiamo già corretto**
- Import colonna **BS** (prezzo), **BB/BC** (costo), staffame ST/LZ, ritenuta % da foglio SAL.
- Avviso se manca BS.

**Cosa Le chiediamo di verificare con noi**
- Odoo ricalcola alcuni valori con regole simili ma non identiche a ogni formula Excel.
- Una sessione di confronto su **una riga pilota** del file P1002 ci aiuterà a chiudere eventuali scostamenti residui.

**Come può verificare**
1. Import P1002 → controllare riga **F1**: BS ≈ 4443,06 €.
2. Tab **Voci contrattuali SAL** → **Retention %**.
3. Confrontare una riga Excel vs Odoo (prezzo TOT, costo TOT, margine %).

**Modulo:** `sbu_estimate`

---

## Punto 13 — Stampa fattura per voce + SAL + CDP

**Il Suo feedback**  
In fattura serviva ogni voce di contratto con descrizione, valori, U.M., totali; testata SAL e CDP; avanzamenti visibili.

**Stato attuale:** ✅ **Disponibile**

**Cosa può già fare in Odoo**
- Una riga contabile per voce contrattuale del periodo SAL.
- Report **«Fattura con dettaglio SAL (SBU)»**.
- Tab commessa **Avanzamento fatturazione**; CDP collegato.

**Come può verificare**
1. Foglio SAL confermato → fattura cliente.
2. Stampa **Dettaglio SAL** da fattura o foglio SAL.
3. Commessa → tab avanzamento fatturazione.

**Modulo:** `sbu_sal`

---

## Punto 14 — Fornitori da Qonto

**Il Suo feedback**  
Chiedeva se integrando Qonto si recuperano automaticamente fornitori e clienti.

**Stato attuale:** ✅ **Fornitori sì** (clienti solo se presenti come beneficiari)

**Cosa può già fare in Odoo**
- Sync **beneficiari SEPA** → contatti fornitore.
- Pulsante **Sync Qonto suppliers**.

**Come può verificare**
1. Configurare Qonto (punto 10).
2. **Sync Qonto suppliers** → **Contatti** → verificare fornitori creati/aggiornati.

**Modulo:** `sbu_qonto`

---

## Punto 15 — Residuo RDA e quantità 1,03

**Il Suo feedback**  
Cambiando qty su RFQ restava riga aperta per il residuo; non era chiaro il valore 1,03.

**Stato attuale:** ✅ **Disponibile**

**Spiegazione**
- **1,03** è la **quantità** (es. 1,00 + 3% perdita), **non** l’unità di misura.
- **Qty remaining** sulla RDA; nuova RFQ propone il residuo.

**Come può verificare**
1. RDA con qty 1,03 → U.M. separata (pz, m²…).
2. RFQ parziale → **Qty remaining** > 0 sulla RDA.

**Modulo:** `sbu_purchase_flow`

---

## Punto 16 — Stampa offerta (flag verdi/rossi, pagamenti, ritenute)

**Il Suo feedback**  
La stampa offerta doveva riflettere le condizioni ANACO con flag verdi/rossi, pagamenti e ritenute collegati.

**Stato attuale:** ✅ **Disponibile**

**Cosa può già fare in Odoo**
- Tab **Condizioni di Fornitura** (Incluso / Escluso / Nota).
- **Carica condizioni standard** → **Stampa offerta** PDF con colori.

**Come può verificare**
1. Preventivo → **Condizioni di Fornitura** → **Carica condizioni standard**.
2. **Stampa offerta** → PDF con tabella condizioni colorata.

**Modulo:** `sbu_estimate`

---

## Punto 17 — Delivery standard

**Il Suo feedback**  
Regole consegna: alluminio/ACO via sistemista e terzista; vetro diretto o via terzista.

**Stato attuale:** ✅ **Disponibile**

**Cosa può già fare in Odoo**
- Tabella **Delivery standard** per route/famiglia.
- Su commessa: terzista, sistemista, modalità vetro.
- **Applica delivery standard** → colonna **Destinazione** sulle righe RDA.

**Come può verificare**
1. **SBU → Purchasing → Delivery standard**.
2. Commessa → tab logistica → **Applica delivery standard su tutte le RDA**.

**Modulo:** `sbu_purchase_flow`

---

## Punto 18 — Revisioni visibili (REV + data)

**Il Suo feedback**  
Non era chiaro quale revisione fosse la più recente su Jobs, SAL, RDA, ecc.

**Stato attuale:** ✅ **Disponibile**

**Cosa può già fare in Odoo**
- Etichetta tipo `[P0015_2026] CLIENTE · REV02 · 2026-05-20` su commesse, preventivi, SAL, RDA, fatture.
- Filtro Jobs: **Solo revisione più recente**.

**Come può verificare**
1. **SBU → Jobs** → colonna con REV e data.
2. Creare REV02 → verificare indicazione «revisione più recente».

**Moduli:** `sbu_estimate`, `sbu_project`, `sbu_sal`, `sbu_purchase_flow`

---

## Checklist verifica — può spuntarla durante i test

| Step | Punto | Verifica | OK |
|------|-------|----------|-----|
| 1 | 18 | Label REV su Jobs | ☐ |
| 2 | 1–2 | Import TMS Excel + distinta vetro 90% | ☐ |
| 3 | 5–17 | Route LA + delivery standard | ☐ |
| 4 | 11 | Budget semafori commessa | ☐ |
| 5 | 6–13 | SAL passivo + fattura dettaglio | ☐ |
| 6 | 10–14 | Qonto import + sync fornitori | ☐ |
| 7 | 12 | Confronto riga F1 Excel vs Odoo | ☐ |
| 8 | 3–4–15 | RDA righe + residuo qty | ☐ |

---

## Prossimi passi — con il Suo supporto

1. Aggiornare i moduli SBU su Odoo.sh dopo ogni rilascio (**`sbu_purchase_flow` 19.0.1.0.99** per TMS Excel).
2. Verificare insieme i punti ⚠️ residui (8 Planner, 9 Logikal, 12 margini ANACO) su una commessa reale.
3. **Punto 1 (TMS Excel):** test UAT con i file in `file base che usano i tecnici_riservato/`.
4. Sessione breve (circa 2 ore) su file P1002 per chiudere il punto 12.

---

## Chiusura

La ringraziamo ancora per la precisione del Suo feedback: ci ha permesso di allineare Odoo al processo reale di Suburban. Restiamo a Sua disposizione per qualsiasi chiarimento o per accompagnarLa nei test sul sistema.

Cordiali saluti,  
**Team SBU Odoo**

---

*Documento preparato per Cosimo — Suburban SRL — maggio 2026.*
