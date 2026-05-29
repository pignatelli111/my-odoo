# Cosimo — Punto 12: costi, margini e retention in import ANACO

**Feedback:** dopo l’import Excel, costi, margini % e retention/garanzia non coincidono con il foglio ANACO.

**Valutazione:** il feedback è **corretto**. L’import copia **parte** delle colonne e Odoo **ricalcola** prezzo/costo/margine con regole **simili ma non identiche** a Excel. Da **`sbu_estimate` 19.0.1.0.109**: staffame ST/LZ, ritenuta % SAL da foglio, avviso BS mancante — parità 1:1 su tutto il foglio richiede ancora validazione P1002.

---

## 1. Cosa fa oggi l’import (`Importa Excel ANACO`)

| Area | Importato da Excel | Calcolato in Odoo dopo import |
|------|-------------------|------------------------------|
| **Prezzo** | Componenti listino (N, 22, 28, … 52), **col. BS (71)** → `price_anaco_bs_cad` | `price_total_cad`: se BS è valorizzato → **usa BS**; altrimenti somma componenti × Sc1–Sc3 × Comm.% |
| **Sconti** | Moltiplicatori foglio riga 5 (K–M) → Sc1–Sc3 % | Stessa catena % su prezzo e costo |
| **Costo** | Coib., posa LIN, trasporto, PM, cantiere, extra; BM/BP riga 5 → % industriali/MOL | `cost_total_cad` = materiali scontati + oneri industriali; **MOL % non entra nel costo totale** (solo indicatore) |
| **Margine %** | — | `(price_total_tot − cost_total_tot) / price_total_tot` |
| **Voci SAL** | Item, descrizione, qty, prezzo unit., piani PT–P8, SAL-1…10 % (se colonne riconosciute) | `total_contract`, cumulative %, retention **solo default azienda** |
| **Retention %** | **Importata** (col. «Ritenuta» / «Garanzia» o testata SAL) | Se assente nel file → default azienda (`sbu_sal_default_retention_percent`) |
| **Staffame ST/LZ** | **Importato** (col. rilevata / 55) | `cost_staffame_cad` incluso in `cost_total_cad` |

Riferimento colonne REV7: `docs/PHASE2_STEP2_4_optional_excel_import.txt`, codice `sbu_estimate/wizards/sbu_estimate_anaco_import_wizard.py`.

---

## 2. Perché il **prezzo** / il **margine** sembrano sbagliati

### 2.1 Catena prezzo Excel ≠ somma componenti Odoo

In Excel il prezzo offerta (**col. BS**) è il risultato di una **catena lunga** (BB, BC, moltiplicatori di foglio `$K$5`, `$L$5`, `$M$5`, `$BE$5`, …) che Odoo **non replica** riga per riga.

Odoo, se **BS è vuoto**, fa:

```text
Listino = Σ colonne prezzo CAD importate
Prezzo netto = Listino × (1−Sc1%) × (1−Sc2%) × (1−Sc3%) × (1−Comm.%)
```

Se una colonna prezzo non è mappata o uno sconto foglio non è in K–M, **listino Odoo ≠ BS Excel** → margine % diverso.

### 2.2 Cosa fare subito (operativo)

1. Verificare che l’import legga **BS** (campo riga **«Prezzo unit. ANACO (col. BS)»**).
2. Se BS in Excel è corretto ma Odoo no: valorizzare / correggere **BS** sulla riga (è il prezzo certificato previsto dalla parità 2.1).
3. Confrontare una riga pilota: Excel **BS × Qt.** vs Odoo **Prezzo cliente TOT**.

---

## 3. Perché i **costi** sembrano sbagliati

| Causa | Dettaglio |
|-------|-----------|
| **Colonne costo non importate** | Es. **ST/LZ staffame** (`cost_staffame_cad`) **non** è nel mapping v1 dell’import (solo coib., posa LIN, trasporto, PM, cantiere, extra). |
| **MOL** | In ANACO il MOL è spesso **indicatore**; in Odoo `cost_mol_amount_cad` **non** è sommato in `cost_total_cad` (come da nota campo). Excel può mostrare un “costo” diverso se include il MOL nel totale che l’utente guarda. |
| **% industriali** | Lette da **riga 5** del foglio (BM/BP), non per ogni riga prodotto se nel file Excel cambiano per riga. |
| **Budget ITEM** | Colonne «Ordini emessi» / «Costi sostenuti» su riga ANACO **non** sono importate; restano 0 finché non si collegano acquisti/consuntivo. |

Confronto consigliato: Excel **costo materiale lavorato e posato TOT** (o equivalente) vs Odoo **Costo Materiale Lavorato e Posato TOT**, riga per riga, non solo il totale preventivo.

---

## 4. Perché la **retention** (garanzia) è sbagliata

- Sulle **voci contrattuali SAL**, l’import imposta sempre:

  `retention_percent` = default **azienda** (es. 5 %), **non** la % del foglio SAL del cliente.
- Il **cap garanzia** sul preventivo (`sal_retention_cap`) è la somma dei `retention_amount` delle voci → se la % è sbagliata, tutto il riquadro garanzia è sbagliato.
- Le **% SAL-1…10** possono non importarsi se il foglio ha **100 % cumulativo** o importi € al posto delle % (il wizard le salta e lascia un messaggio in chatter).

**Workaround:** dopo import, tab **Voci contrattuali SAL** → correggere **Retention %** per voce (o allineare default in **Impostazioni → Azienda**).

**Fix previsto (P0):** individuare colonna/e «Ritenuta %» / «Garanzia» nel foglio `Voci Contrattuali_SAL` del file P1002/REV e mapparla in import.

---

## 5. Verifica con file pilota (P1002 / PRV reale)

### 5.1 Script di analisi (senza Odoo UI)

```bash
cd ~/src/user
pip install openpyxl   # se manca
python tools/probe_anaco_workbook.py "docs/samples/client/ANACO_P1002_25_CON_REV03_EIALL+ALL_P1.xlsx"
```

Copiare il workbook cliente in `docs/samples/client/` (non in git per default).

### 5.2 Confronto manuale (DELTA_LOG)

Per **5 righe ANACO** e **3 voci SAL** registrare:

| Riga | Excel (cella) | Campo Odoo | Δ € | Nota |
|------|---------------|------------|-----|------|
| F1 | BS12 | `price_anaco_bs_cad` / `price_total_tot` | | |
| F1 | Costo TOT | `cost_total_tot` | | MOL escluso in Odoo |
| SAL-01 | Ritenuta % | `retention_percent` | | Oggi = default 5 % |

Modello: `docs/PHASE2_STEP2_1_anaco_field_formula_parity.txt`.

### 5.3 Test automatici esistenti

- `sbu_estimate/tests/test_sbu_anaco_import.py` — layout REV7, SAL %, distinta.
- `sbu_estimate/tests/test_sbu_p1002_workbook.py` — conteggi righe **se** il file P1002 è sul server.

Manca ancora: test di **parità numerica** riga per riga (P0 backlog).

---

## 6. Piano fix (priorità P0)

| # | Intervento | Effetto |
|---|------------|---------|
| 1 | Mappare colonne costo mancanti (es. **staffame ST/LZ**) dopo scansione header P1002 | Costi più vicini ad ANACO |
| 2 | Import **retention %** da foglio SAL (o da testata preventivo se unica) | Garanzia / cap corretti |
| 3 | Opzione wizard «**Usa sempre BS come prezzo cliente**» + avviso se BS vuoto e listino ≠ atteso | Margini allineati all’offerta Excel |
| 4 | Test regressione: export righe Odoo vs golden row da P1002 (tolleranza € / 0,5 %) | Evita regressioni Odoo.sh |
| 5 | Import opzionale colonne budget ANACO (ordini emessi / consuntivo) | Colonne budget ITEM non a zero |

---

## 7. Risposta sintetica a Cosimo

> «I numeri in import sono sbagliati» — **sì, rispetto a Excel 1:1**, per differenze di formula documentate.  
> **Prezzo:** allineare con **colonna BS** o completare mapping sconti.  
> **Costo:** mancano alcune colonne CAD; il MOL in Odoo non è nel totale costo come molti fogli Excel.  
> **Retention:** oggi **non si importa** dal file; va impostata in Odoo o nel fix P0 sopra.

**Stato roadmap:** migliorato in codice (v `19.0.1.0.109`); validazione numerica P1002 ancora P0 — vedi `FEEDBACK_COSIMO_ROADMAP_IT.md` punto 12.

---

*Ultimo aggiornamento: maggio 2026 — commit documentazione; fix codice in corso su file pilota cliente.*
