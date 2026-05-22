# Cosimo — Punto 17: Delivery standard

**Modulo:** `sbu_purchase_flow` 19.0.1.0.53+  
**Stato:** implementato (regole + commessa + auto-fill su righe RDA)

---

## Cosa chiedeva Cosimo

1. **Alluminio + accessori di sistema + ACO**  
   Percorso tipico: **sistemista** (fornitore abituale) → **terzista cantiere** (scelto per commessa, spesso 4–5 fermate) → **cantiere**.

2. **Vetro**  
   - **Opzione A:** vetraio → cantiere diretto  
   - **Opzione B:** vetraio → **stesso terzista** dell’alluminio → cantiere  

---

## Come si configura in Odoo

### 1. Regole aziendali (admin)

**SBU → Purchasing → Delivery standard**  
(`sbu.delivery.standard`)

Tabella predefinita (modificabile) per route ANACO / famiglia costo / tipo documento:

| Esempio | Pattern |
|---------|---------|
| LA, LZ, ST, PAN, PRF, FT, ASS, ACC, GUA | Fornitore (sistemista) → terzista → … → cantiere |
| ACO | Come sopra |
| Vetro `direct` | Fornitore → cantiere |
| Vetro `via_terzista` | Fornitore → terzista → cantiere |

### 2. Per commessa (obbligatorio per nomi corretti)

**Progetto / Commessa → scheda «Logistica / delivery»**

- **Terzista cantiere** — partner usato nel testo DESTINAZIONE  
- **Sistemista** — fornitore sistema (alluminio / ACO)  
- **Consegna vetro** — radio: diretto in cantiere **oppure** via terzista  

Pulsante: **Applica delivery standard su tutte le RDA** della commessa.

### 3. Su ogni richiesta acquisto

- All **caricamento righe da distinta** la colonna **Destinazione** si compila da sola (se vuota).  
- Pulsante **Apply delivery standards** sulla RDA — ricalcola tutte le righe (sovrascrive).

---

## Campo operativo

Riga RDA: **`destination`** (DESTINAZIONE) — testo per buyer / fornitore.  
Non sostituisce ancora i pickings magazzino automatici (percorso stock = fase successiva con `sbu_stock_config`).

---

## Test automatici

`sbu_purchase_flow/tests/test_sbu_delivery_standard.py`

---

## Aggiornamento DB

Dopo deploy: aggiornare `sbu_purchase_flow` (o reinstall).  
I record regole default sono in `data/sbu_delivery_standard_data.xml` (`noupdate=1`).
