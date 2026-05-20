# Sample ANACO workbooks (UAT)

## `SBU_ANACO_SAMPLE_UAT.xlsx`

Rich Excel aligned with the **SBU import wizard** (`sbu_estimate` — REV7 column layout). Regenerate after script changes:

```powershell
cd "f:\TASK\20 . Odoo\my-odoo"
pip install openpyxl
python tools/generate_sample_anaco_workbook.py
```

### Foglio **ANACO**

| Riga | Contenuto |
|------|-----------|
| **5** | Moltiplicatori sconto **K/L/M = 0,95 / 0,96 / 0,97** (sconti successivi in Odoo). **BM = 6%** (industrial), **BP = 4%** (MOL) sui costi materiali. |
| **11** | Intestazione non importata (`COD.` + `DESCRIZIONE`). |
| **12** | **FT-SAMPLE-01** — finestra 1200×1500, Qt 2: listino serramento + accessori + vetro, **stack costi** (coibenta, posa, trasporto, tech, cantiere, extra), **BS 450**, nota col. 74. |
| **13** | **LA-SAMPLE-02** — lucernario 1000×1000, Qt 1: prezzi/costi ridotti, **BS 890**. |
| **14** | **ACC-SAMPLE-03** — solo Qt **5** (senza B×H): test **Nr** + famiglia costo da prefisso **ACC**. |

### Foglio **Voci Contrattuali_SAL** (da riga **16**)

| Riga | Voce | Importo | Piano SAL % |
|------|------|---------|-------------|
| 16 | SAL-VOCE-01 | 50.000 € | 20 + 30 + 50 = **100%** |
| 17 | SAL-VOCE-02 | 25.000 € | 25 + 25 + 25 = **75%** |

### Foglio **OFFERTA**

Due righe dati (solo se l’import ANACO non trova righe — drill fallback): `FT-OFF-99` (MQ) e `VC-OFF-88` (Nr).

### Import in Odoo

1. **Nuovo preventivo** → Salva → Cliente.  
2. **Importa Excel ANACO** → allega `SBU_ANACO_SAMPLE_UAT.xlsx`.  
3. Spunte: **Importa righe ANACO** + **Importa Voci Contrattuali SAL**, **Sostituisci** entrambe, **Rileva prima riga**, **Fallback OFFERTA**.  
4. **Prima riga SAL:** **16**.

### Atteso dopo import

- **3 righe** preventivo ANACO (FT, LA, ACC).  
- **2 righe** voci contrattuali SAL.  
- **Costo totale** in testata **> 0** (costi CAD + % riga 5).  
- **Margine** realistico (non 100% da costo zero).  
- **SAL status** sulle voci contrattuali: se sono compilate solo le **SAL-1…10 %** (ancora nessun foglio SAL reale), il badge è **Planned (SAL % only)** — non “Approved” / “Submitted” (quelle servono al flusso reale con `sbu_sal`).

La **distinta ITEM** resta da compilare in Odoo (il wizard non importa il foglio Excel ITEM in questo file).

### Nota

Il file di cantiere reale resta il vostro ANACO REV7; questo è per **test ripetibili** e formazione.
