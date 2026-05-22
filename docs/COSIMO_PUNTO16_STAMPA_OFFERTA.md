# Cosimo punto 16 — Stampa offerta (flag e condizioni)

## Problema

In ANACO le condizioni di offerta usano **scelte** (flag **verde** = incluso, **rosso** = escluso) collegate a pagamenti, ritenute, garanzia, resa. In Odoo restavano campi testo scollegati (`payment_terms_text`, inclusioni/esclusioni) senza legame con la stampa.

## Soluzione (`sbu_estimate` ≥ 19.0.1.0.82)

### Tab «Condizioni di Fornitura»

- Lista **Condizioni commerciali strutturate** (`sbu.estimate.commercial.term`):
  - **Categoria**: pagamento, ritenuta, garanzia, resa, inclusione, esclusione
  - **Scelta offerta**: Incluso (verde) / Escluso (rosso) / Nota
  - **%** opzionale (rate pagamento, ritenuta)
- **Ritenuta offerta (%)** allineata a impostazione azienda SAL
- Pulsanti:
  - **Carica condizioni standard** — righe Suburban predefinite
  - **Aggiorna testi da righe** — sincronizza i campi testo legacy
- **Stampa offerta** (header preventivo) → PDF QWeb

### Report PDF «Offerta / Preventivo (SBU)»

- Righe offerta (pos, descrizione, U.M., qtà, prezzo da colonna BS / prezzo cliente)
- Tabella condizioni con **flag colore** e righe evidenziate
- Riepilogo ritenuta e totale offerta

### Preventivi esistenti

Aprire il preventivo → **Condizioni di Fornitura** → **Carica condizioni standard**.
