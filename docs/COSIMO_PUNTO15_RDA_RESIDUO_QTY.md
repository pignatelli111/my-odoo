# Cosimo punto 15 — Quantità 1,03 e residuo RDA

## Cosa significa 1,03

**Non è l’unità di misura (U.M.).** È la **quantità richiesta** dopo le regole distinta:

- quantità teorica (es. `1,00`)
- **+ perdita fabbisogno %** sulla RDA (default **3%** → `1 × 1,03 = 1,03`)
- eventuali MOQ / arrotondamento confezione

In form RDA: colonna **Qtà richiesta**, colonna **U.M.** (pz, m, m²…), opzionale **Qty breakdown** con la formula.

## Residuo dopo modifica qty su RFQ

| Campo RDA | Significato |
|-----------|-------------|
| **Qtà richiesta** | Fabbisogno totale sulla RDA |
| **Qty on RFQ/PO** | Somma qty su righe ordine collegate |
| **Qty remaining** | Residuo da ordinare |

Flusso:

1. **Crea bozza RFQ** → copia il **residuo** (inizialmente = quantità richiesta).
2. Se su RFQ si riduce la qty (es. 10 → 3), sulla RDA resta **residuo 7**.
3. **Seconda RFQ** (stesso fornitore) riusa la bozza e imposta la riga al **residuo** aggiornato (non duplica qty piena).

Il budget commessa considera anche il valore del **residuo** ancora da ordinare.

## Modulo

`sbu_purchase_flow` ≥ **19.0.1.0.44**
