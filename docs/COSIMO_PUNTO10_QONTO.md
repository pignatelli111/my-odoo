# Cosimo — Punti 10 e 14 (Qonto)

**Modulo:** `sbu_qonto` (Odoo 19)  
**Versione riferimento:** `19.0.1.0.7+`

---

## Punto 10 — Pagamenti ricevuti e abbandono what-if Qonto

### Aspettativa Cosimo

- I **pagamenti in entrata** si **riconciliano in automatico** dopo l’integrazione Qonto.
- **Fatturazione attiva/passiva e SAL** in Odoo; Qonto **non** per scenari what-if su fatture.
- Qonto resta **conto corrente** (movimenti bancari).

### Comportamento implementato

| Fase | Cosa fa Odoo |
|------|----------------|
| Import | API, cron orario, webhook `/qonto/webhook/<token>` |
| Anagrafiche (14) | Sync **beneficiari SEPA** Qonto → `res.partner` fornitore (opz. ad ogni import) |
| Suggerimento | Match euristica su fattura cliente, fattura fornitore, pagamenti già in Odoo |
| Auto (default) | **Alta confidenza + entrata** → registra pagamento cliente (`account.payment.register`) → fattura **saldata in Odoo** |
| Auto (opz.) | **Alta confidenza + uscita** → registra pagamento fornitore (flag **spento** di default) |
| Auto link | Collega movimento a documento senza registrare pagamento se non si usa register |

**Non incluso (fase successiva):** riconciliazione riga-per-riga **estratto conto bancario** Odoo ↔ journal Qonto. Per Cosimo, la “riconciliazione operativa” richiesta è **fattura saldata** quando arriva il bonifico.

### Impostazioni (Azienda → Qonto (SBU) o Impostazioni → integrazioni SBU)

| Campo | Default | Note |
|-------|---------|------|
| Sync beneficiaries on import | Sì | Punto 14 |
| Auto-link high confidence | Sì | Solo collegamento |
| Auto-register customer payments | Sì | Punto 10 |
| Auto-register vendor payments | No | Abilitare dopo UAT |

### Operatività

1. Configurare login, secret, IBAN Qonto.
2. Attivare cron import (o import manuale).
3. **Contabilità → Movimenti Qonto**: verificare movimenti `matched` e fatture con residuo a zero.
4. Non usare gli strumenti what-if fatture in Qonto: emettere fatture/SAL da Odoo.

---

## Punto 14 — Fornitori/clienti da Qonto

### Implementato

- API `GET /v2/sepa/beneficiaries` (fallback `/v2/beneficiaries`).
- Pulsante **Sync Qonto suppliers** (impostazioni, scheda azienda, lista movimenti).
- Campi partner: `sbu_qonto_beneficiary_id`, `sbu_qonto_iban`, `sbu_qonto_partner_synced`.
- Deduplica: id beneficiario → IBAN Qonto → IBAN su `res.partner.bank`.
- Nuovi partner: `supplier_rank = 1` (fornitore).

I movimenti usano **counterparty IBAN** per collegare `partner_id` e migliorare il match fatture fornitore.

---

## UAT rapido

Vedi anche [UAT_BANKING_C.md](UAT_BANKING_C.md).

1. Sync suppliers → compare nuovo fornitore in Contatti.
2. Import movimento entrata con riferimento fattura cliente postata → stato `matched`, pagamento creato.
3. Fattura cliente: residuo = 0.
4. Movimento uscita con riferimento fattura fornitore → suggerimento `high`; register manuale o flag auto outbound.

---

## Limiti noti

- Match su **importo + testo** (numero fattura, payment reference); più candidati = revisione manuale.
- Clienti creati da beneficiari solo se presenti in Qonto come beneficiari SEPA (tipicamente fornitori pagati).
- Sandbox Qonto: usare flag **Qonto sandbox** per test API.
