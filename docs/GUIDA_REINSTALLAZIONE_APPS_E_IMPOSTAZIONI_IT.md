# Guida — Reinstallare app e impostazioni (Odoo.sh produzione Suburban)

**Quando serve:** database nuovo, ambiente resettato, o moduli SBU risultano **Non installati** dopo un problema Odoo.sh.  
**URL produzione:** https://pignatelli111-my-odoo.odoo.com  
**Repository:** `pignatelli111/my-odoo` — ramo **`production`**

---

## 0. Cosa perdi e cosa no

| Elemento | Dopo DB nuovo / reset |
|----------|------------------------|
| Preventivi, commesse, RDA, fatture | **Persi** (salvo backup / altro DB) |
| Moduli **installati** | Da reinstallare |
| **Impostazioni** (`ir.config_parameter`, azienda, conti) | Da reimpostare |
| Codice custom su GitHub | **Resta** (Odoo.sh lo deploya col build) |
| Utenti Odoo (login) | Di solito **restano** (account portal/internal) |

Se avevi solo un problema di **build rosso**, spesso **non** serve reinstallare tutto: basta **Apps → Aggiorna** sui moduli SBU. Usa questa guida solo se in **Apps** i moduli SBU sono **Non installati** o hai un **database vuoto**.

---

## 1. Prima di installare (Odoo.sh)

1. **Build verde** sul ramo `production` (commit recente, es. `39bb2fe+`).
2. Login come **amministratore**.
3. In alto a destra: azienda **Suburban SRL** (non “My Company” di test).
4. **Apps** → menu ⋮ → **Aggiorna elenco app** (Update Apps List).

---

## 2. App Odoo standard (di solito già presenti su Odoo.sh)

Verifica che siano **Installate** (cerca in Apps):

| App | Perché |
|-----|--------|
| **Contabilità** (+ localizzazione **Italia** se prevista) | Fatture, SAL, Qonto |
| **Vendite** / **CRM** | Preventivi, opportunità |
| **Progetti** | Commesse |
| **Acquisti** | RFQ / ordini fornitore |
| **Magazzino** | Ricevimenti, DDT |
| **MRP** (distinta) | BOM preventivo |

Se manca l’Italia contabile, installala **prima** dei moduli SBU che usano `account`.

---

## 3. Moduli SBU — ordine consigliato

In **Apps**, rimuovi il filtro “Apps” e cerca **`SBU`**. Installa **uno alla volta** nell’ordine sotto (oppure tutti se Odoo risolve le dipendenze automaticamente).

| # | Modulo tecnico | Nome in Apps (circa) | Note |
|---|----------------|----------------------|------|
| 1 | `sbu_integrations` | SBU Integrations | Impostazioni Graph / JSON dev→prod |
| 2 | `sbu_stock_config` | SBU Stock configuration | Ubicazioni / DDT |
| 3 | `sbu_estimate` | SBU Estimate | **Applicazione** principale preventivi |
| 4 | `sbu_project` | SBU Project | Collegamento commessa |
| 5 | `sbu_purchase_flow` | SBU Purchase Flow | RDA / RFQ / budget |
| 6 | `sbu_sal` | SBU SAL | SAL, CDP, fattura con dettaglio |
| 7 | `sbu_documents` | SBU Documents | Hub documenti / M365 |
| 8 | `sbu_logikal` | SBU Logikal / ReynaPro | Import tecnico (opzionale) |
| 9 | `sbu_closure` | SBU Project closure | Chiusura commessa |
| 10 | `sbu_qonto` | SBU Qonto | Movimenti bancari |
| 11 | `sbu_revolut` | SBU Revolut | Movimenti Revolut |
| 12 | `sbu_mail_ingest` | SBU Mail / Attachment Ingest | Email RFQ (opzionale) |

**Dopo ogni installazione:** se compare **Aggiorna** (Upgrade) su un modulo già installato, eseguilo dopo ogni deploy Git.

### Installazione rapida da shell Odoo.sh (solo admin tecnico)

Solo se il build ha deployato `tools/` e la shell è aggiornata:

```bash
cd ~/src/user
# Elenco uguale al build Odoo.sh
odoo-update sbu_integrations,sbu_stock_config,sbu_estimate,sbu_project,sbu_purchase_flow,sbu_sal,sbu_documents,sbu_closure,sbu_logikal,sbu_mail_ingest,sbu_qonto,sbu_revolut
```

Se `odoo-update` non esiste, usa **Apps** nell’interfaccia web.

---

## 4. Utenti e permessi

| Gruppo / ruolo | Chi |
|----------------|-----|
| **Impostazioni / Amministratore** | IT, deploy |
| **SBU Estimate User** (creato da `sbu_estimate`) | Preventivatori |
| **Acquisti / Utente** | Buyer, RDA |
| **Progetti / Utente** | PM commessa |
| **Contabilità** | Fatture, SAL |

Per ogni utente operativo: **Impostazioni → Utenti** → gruppi sopra + azienda **Suburban** nelle aziende consentite.

---

## 5. Impostazioni da reimpostare (checklist)

### 5.1 Azienda

**Impostazioni → Aziende → Suburban SRL**

- Ragione sociale, P.IVA **12352270966**, indirizzo  
- Valuta **EUR**  
- Logo (per stampe PDF / offerta)  
- **Layout documento esterno** (per fatture/offerte PDF — evita wizard layout vuoto)

### 5.2 Blocco SBU (Impostazioni generali)

**Impostazioni → General Settings** → cerca **`SBU`** (non c’è tab separato “SBU” a sinistra).

| Area | Cosa inserire |
|------|----------------|
| **Microsoft Graph** | Tenant ID, Client ID, Client secret (da Azure) |
| **OneDrive / SharePoint** | Policy cartelle commessa |
| **Logikal** | URL API (solo se usi bridge API) |
| **Test connessione Graph** | Pulsante test → deve essere OK |

**Copia da ambiente dev (consigliato):**

1. Sul DB **dev** che aveva già le impostazioni: **Impostazioni → Amministrazione → SBU settings JSON (dev → prod)** → **Export JSON**.  
2. Sul **prod**: stesso wizard → **Import JSON** (incolla file).  
3. Segreti (Graph, Qonto): verificare che siano presenti; se mancano, reinserirli e **Salva**.

### 5.3 Qonto (`sbu_qonto`)

**Impostazioni** (blocco Qonto) **oppure** scheda azienda **Qonto (SBU)**:

- Login API, secret, IBAN  
- **Enable Qonto import cron** = sì  
- **Suggest matches after import** = sì  

**Non usare** “Collega banca → Qonto” standard Odoo Enterprise se non avete licenza bancaria Odoo collegata (vedi README).

Vedi anche: [UAT_BANKING_C.md](UAT_BANKING_C.md)

### 5.4 Revolut (`sbu_revolut`)

Stessa logica della scheda **Revolut (SBU)** sull’azienda.

### 5.5 SAL — ritenuta e conti

**Impostazioni / Azienda** (campi `sbu_sal`):

- % ritenuta default su SAL (es. 5%)  
- Conto ritenuta su fattura (se richiesto dalla contabilità)

### 5.6 Magazzino (`sbu_stock_config`)

Dopo install: verifica esistenza ubicazioni/route SBU (il modulo crea dati da XML).  
Su commessa: tab **Logistics** / spedizioni come da [UAT_LOGISTICS_B.md](UAT_LOGISTICS_B.md).

---

## 6. Verifica che tutto funzioni (15 minuti)

| # | Test | Menu | Esito atteso |
|---|------|------|----------------|
| 1 | Moduli installati | Apps → cerca `sbu_estimate` | Stato **Installato** |
| 2 | Menu SBU | App **SBU** | Preventivi, Jobs, Billing, … |
| 3 | Nuovo preventivo | SBU → Preventivi → **Nuovo** | Scheda salvabile |
| 4 | Condizioni offerta | Tab **Condizioni di Fornitura** | Pulsante **Condizioni standard** |
| 5 | Commessa | Preventivo **Vinto** → crea commessa | Progetto collegato |
| 6 | RDA | SBU → Purchase → Richieste | Nuova RDA |
| 7 | SAL | Commessa → foglio SAL | Conferma + bozza fattura |

Guida passo-passo per Cosimo: [guide/GUIDA_TEST_AUTONOMO_COSIMO.md](guide/GUIDA_TEST_AUTONOMO_COSIMO.md)

---

## 7. Dati storici (preventivi / commesse esistenti)

- **Backup Odoo.sh:** se esiste snapshot precedente al reset, ripristino va richiesto al **supporto Odoo.sh** (non dal menu standard).  
- **Import ANACO:** da Excel su ogni preventivo ([GUIDA_TEST_AUTONOMO_COSIMO.md](guide/GUIDA_TEST_AUTONOMO_COSIMO.md) § Test 2).  
- **Non** c’è migrazione automatica dal vecchio DB senza backup.

---

## 8. Problemi frequenti

| Problema | Soluzione |
|----------|-----------|
| Menu SBU vuoto | Moduli non installati → § 3 |
| “Accesso negato” preventivi | Azienda sbagliata in alto a destra → Suburban |
| Build Odoo.sh rosso | Non è reinstallazione: fix test/deploy su Git `production` |
| Impostazioni Graph perse | Export/import JSON da dev (§ 5.2) |
| PDF apre wizard layout | Impostare **Layout documento esterno** su azienda |
| Qonto non importa | Cron attivo + credenziali § 5.3 |

---

## 9. Riferimenti

- [README.md](../README.md) — deploy e note Qonto/Logikal  
- [REPORT_CLIENTE_SBU_ODOO_IT.md](REPORT_CLIENTE_SBU_ODOO_IT.md) — panoramica moduli  
- [GUIDA_UTENTE_SBU_ODOO.md](guide/GUIDA_UTENTE_SBU_ODOO.md) — uso quotidiano  

*Ultimo aggiornamento: maggio 2026 — allineato a moduli SBU su Odoo 19.*
