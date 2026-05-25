# Punto 11 — Budget acquisti per tipologia (ITEM / semafori)

## Obiettivo (feedback Cosimo)

- Controllo budget per **famiglia di costo** (tipologia acquisto ANACO), come foglio ITEM.
- **Preventivo**, **ordini emessi**, **costi sostenuti (consuntivo)**, **residui** e **%** in un’unica schermata.
- **Semafori** (verde &lt; 90 %, giallo fino 105 %, rosso oltre) su impegnato e consuntivo.
- **Sblocco PO** in rosso solo per utenti autorizzati (non tutti gli acquisti).

## Dove in Odoo

| Schermata | Percorso |
|-----------|----------|
| Cruscotto per famiglia | Commessa → smart button **Purchase budget** o tab **Budget acquisti** |
| Menu globale | **SBU → Purchasing → Budget per famiglia** |
| Righe ITEM | Preventivo → tab **Budget acquisti (ITEM)** + colonne opzionali su righe ANACO |

Dopo ogni refresh (pulsante o automatico su conferma PO / registrazione fattura fornitore).

## Colonne cruscotto (famiglia)

| Colonna | Significato |
|---------|-------------|
| Budget (estimate) | Somma `cost_total_tot` righe ANACO per famiglia |
| RDA aperte | Richieste non ancora su PO (offerta o prezzo standard) |
| PO bozza | RFQ/PO in bozza |
| Ordini emessi | PO confermati |
| Costi sostenuti | Fatture fornitore **registrate**, collegate alle righe PO |
| Impegnato tot. | RDA + PO bozza + ordini emessi |
| Residuo (impegnato) | Preventivo − impegnato |
| Residuo (consuntivo) | Preventivo − costi sostenuti |
| Semaforo | Peggior % tra impegnato e consuntivo vs preventivo |

## Blocco e sblocco PO

- Conferma PO **bloccata** se la famiglia è **rossa** (&gt; 105 %).
- Sblocco solo se:
  1. Utente in **Settings / Administrator**, oppure
  2. Utente nel gruppo **SBU — Sblocco budget acquisti** *e* flag **Unlock PO over budget** attivo sulla commessa.

Assegnare il gruppo solo a responsabili acquisti / admin (es. Cosimo).

## Righe preventivo (ITEM)

Su ogni riga ANACO collegata a BOM/PR/PO:

- **Ordini emessi** — totale PO confermati tracciati
- **Costi sostenuti** — fatture fornitore registrate
- **Residuo**, **% su preventivo**, **semaforo**

## Modulo

`sbu_purchase_flow` **19.0.1.0.91+** (dipendenza `account` per consuntivo).

## UAT rapido

1. Commessa con preventivo vinto → **Refresh from estimate and purchases**.
2. Creare RDA/PO sotto budget → semaforo verde/giallo.
3. PO sopra 105 % → conferma bloccata per buyer normale.
4. Abilitare sblocco su commessa + utente nel gruppo sblocco → conferma OK.
5. Registrare fattura fornitore su PO → **Costi sostenuti** e tab ITEM aggiornati.
