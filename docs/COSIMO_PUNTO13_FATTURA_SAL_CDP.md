# Cosimo — Punto 13: stampa fattura per voce contratto + SAL + CDP

**Feedback:** in fattura servono **ogni singola voce di contratto** con descrizione, valori, unità di misura e totali; in testata **SAL di riferimento** e **CDP**; gli avanzamenti poi visibili anche da moduli standard Odoo (dashboard / cruscotto).

**Valutazione:** la richiesta è **corretta** e allineata al processo Suburban. Oggi la **tracciabilità** SAL → fattura → CDP c’è nei dati; la **stampa/PDF** cliente è ancora **sintetica** (1–2 righe contabili), non il dettaglio per voce contrattuale.

---

## 1. Cosa funziona oggi in Odoo SBU

### 1.1 Flusso dati (OK)

```text
Preventivo → Voci contrattuali SAL (tab su estimate)
     ↓
Commessa → Foglio SAL (sbu.sal.sheet) con righe per voce (sbu.sal.sheet.line)
     ↓
Conferma SAL → Fattura cliente (account.move out_invoice)
     ↓
Certificato di pagamento / CDP (sbu.payment.certificate), collegato al SAL e alla fattura
```

| Elemento | Dove in Odoo | Collegamento |
|----------|--------------|--------------|
| Voce contratto | `sbu.estimate.sal.line` | Import ANACO / manuale |
| Avanzamento periodo | `sbu.sal.sheet.line` | `estimate_sal_line_id`, **This SAL %**, importo periodo |
| Foglio SAL | `sbu.sal.sheet` | Commessa, data, ritenuta %, totali lordo/netto |
| Fattura | `account.move` (cliente) | `invoice_id` sul foglio; `ref` / `invoice_origin` = SAL/… |
| CDP | `sbu.payment.certificate` | `sal_sheet_id`, fattura collegata, netto da pagare |

Sul **preventivo**, ogni voce contrattuale mostra anche **fatturato**, **residuo**, **garanzia**, riferimenti fattura/CDP (tab aggiornata da `sbu_sal`).

### 1.2 Cosa stampa la fattura oggi (GAP)

La creazione fattura (`action_create_draft_invoice` in `sbu_sal/models/sbu_sal_sheet.py`) genera **righe contabili aggregate**, non una riga per voce contratto:

| Caso | Righe fattura Odoo |
|------|-------------------|
| Con ritenuta | 1) «SAL … — progress (gross)» = totale lordo periodo · 2) «Retention (withholding)» = −ritenuta |
| Senza ritenuta | 1 sola riga «SAL … — progress billing» = netto |

**Non compaiono** su `account.move.line`: descrizione voce F4b, U.M., qty contrattuale, prezzo unitario, importo voce del periodo.

Il PDF standard Odoo (**Stampa fattura**) riproduce quelle 1–2 righe + totali IVA. **Non** c’è report QWeb SBU dedicato in `sbu_sal` (nessun `report/*.xml` custom oggi).

### 1.3 Testata fattura / CDP (parziale)

| Richiesta Cosimo | Stato |
|------------------|--------|
| Commessa / job | Parziale — `project_id` sulla fattura se il campo esiste; partner = cliente |
| Riferimento **SAL/xx/xxxx** | Sì — `ref` e `invoice_origin` tipicamente «SAL …» |
| Periodo SAL | Data foglio SAL; non sempre ripetuta in evidenza sul PDF |
| **CDP** in testata fattura | **No** — il CDP è documento **separato** (`sbu.payment.certificate`); collegato ma non stampato sul layout fattura standard |

---

## 2. Dashboard e visibilità avanzamenti (Cosimo: “cruscotto standard”)

**Sì, in parte** — senza un cruscotto SBU unico, ma con strumenti Odoo + campi SBU:

| Bisogno | Dove guardare oggi |
|---------|-------------------|
| Fatture per commessa | Fatture cliente filtrate per progetto / origine SAL |
| Avanzamenti SAL | Commessa → **SAL sheets**; preventivo → **Voci contrattuali SAL** (fatturato / residuo / %) |
| Pagamenti | Stato pagamento fattura; CDP **Issued / Paid** |
| Contabilità | Prima nota standard; analitica su commessa se configurata |
| KPI aggregati | **Da definire** — cruscotto SBU dedicato (fatturato vs contratto, SAL aperti) è in roadmap **P1**, non ancora un modulo “dashboard Suburban” |

Quindi: gli **avanzamenti sono tracciati** nel modello SBU; la **vista executive** passa ancora per liste Odoo (SAL, fatture, progetto), non per un unico cruscotto come in Excel.

---

## 3. Cosa propone Cosimo (target)

### Layout fattura (PDF o stampa)

**Intestazione**

- Cliente, commessa, oggetto lavori  
- **SAL/26/0005** (o sequenza reale) + **periodo** (date SAL)  
- Riferimento **CDP** se emesso (es. CDP/26/0003)  
- Eventuale preventivo / contratto (PRV/…)

**Corpo — una riga per voce contrattuale**

| Colonna | Fonte Odoo |
|---------|------------|
| Descrizione | `sbu.sal.sheet.line` → `description` / voce SAL |
| U.M. | `sbu.estimate.sal.line` → `uom_type` (MQ, ML, Nr, …) |
| Q.tà | qty contrattuale o qty periodo (da concordare) |
| Prezzo unitario | `unit_price` voce o derivato da importo periodo |
| Importo periodo | `amount_this_sal` |
| **Totale** | Somma righe + riga **ritenuta %** + netto |

### Due strade tecniche (da scegliere con Cosimo / commercialista)

| Opzione | Pro | Contro |
|---------|-----|--------|
| **A — Righe fattura Odoo = una per voce SAL** | Un solo documento; SDI/e-fattura allineati al dettaglio | Più righe contabili; IVA per riga; ritenuta da modellare |
| **B — Fattura contabile sintetica (come oggi) + PDF SBU dettagliato** | Contabilità semplice (lordo + ritenuta); PDF cliente ricco | Due rappresentazioni da tenere coerenti |
| **C — Allegato PDF “Allegato SAL”** dal foglio | Veloce da implementare; foglio SAL già ha le righe | Non sostituisce righe in fattura elettronica se richieste in XML |

**Proposta SBU:** **B o C** per UAT (PDF cliente professionale); valutare **A** con commercialista per SDI Italia.

---

## 4. Piano implementazione (P1)

| # | Deliverable | Modulo | Stato |
|---|-------------|--------|--------|
| 1 | Report QWeb **Fattura con dettaglio SAL (SBU)** — testata commessa + SAL + CDP | `sbu_sal` | **Fatto** (`report/sbu_invoice_sal_report.xml`, v `19.0.1.0.39`) |
| 2 | Tabella righe da `sbu.sal.sheet.line` (item, desc, U.M., qty, PU, % SAL, importo periodo) | idem | **Fatto** (+ campi computed `item_ref`, `uom_label`, `qty_display`, `unit_price_display`) |
| 3 | Riga ritenuta e totali lordo / netto come oggi | idem | **Fatto** (footer PDF + righe contabili aggregate invariati) |
| 4 | Azione **Stampa** su fattura (menu Stampa + pulsante) e su foglio SAL | idem | **Fatto** |
| 5 | Collegamento `sbu_sal_sheet_id` + `sbu_sal_cdp_name` su `account.move` | `account.move` | **Fatto** |
| 6 | (P2) Cruscotto progetto: fatturato, residuo SAL, ultimo CDP | `sbu_project` / reporting | Aperto |

---

## 5. Risposta sintetica a Cosimo

> «In fattura voglio ogni voce di contratto con descrizione, U.M., prezzi e totali, in testata SAL e CDP, e poi vedere gli avanzamenti in dashboard.»

- **Processo:** sì, è il modello SBU (foglio SAL per voce → fattura → CDP).  
- **Stampa attuale:** report **«Invoice with SAL detail (SBU)»** (PDF per voce contratto); la fattura contabile resta sintetica (lordo + ritenuta).  
- **SAL in testata:** sì nel dato (`ref` / origine); **da mettere in evidenza** sul layout stampa.  
- **CDP:** esiste e si collega alla fattura; **da mostrare in testata** sul PDF custom.  
- **Dashboard:** uso liste Odoo + tab preventivo; **cruscotto unico SBU** = fase successiva.

---

*Riferimenti: `docs/REPORT_CLIENTE_SBU_ODOO_IT.md` § 4.4, `docs/presentazione-cliente/REPORT_PRESENTAZIONE_CLIENTE_IT.md` schede 7–9, `sbu_sal/models/sbu_sal_sheet.py`.*
