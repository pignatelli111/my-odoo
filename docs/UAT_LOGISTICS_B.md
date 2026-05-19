# UAT Phase B — Logistics (one real receipt: DDT + picking)

**Environment:** `pignatelli111-my-odoo.odoo.com` (production pilot DB)  
**Module:** `sbu_stock_config` **19.0.1.1.4+** (upgrade after deploy)

## Pilot references

| Object | Reference |
|--------|-----------|
| Preventivo | PRV/2026/0004 |
| Commessa | P0006_2026 |
| RDA | RDA/26/0002 |
| Ordine acquisto | P00001 (CROMATOS SRL) |

## Preconditions

1. UAT-3 completed: **P00001** confirmed or ready to confirm, linked to **P0006_2026**.
2. User has **Inventory** and **Purchase** rights.
3. Warehouse uses **2-step reception** (Input → Stock); SBU reception buffer is under Input (set by module hook).
4. Products on PO are **consumable / stockable** with `purchase_ok` so an incoming picking is created.

## Steps

### 1. Confirm purchase order

1. Open **P00001** → confirm if still draft.
2. Check **Job / project** = commessa **P0006_2026**.
3. Note the **Receipt** smart button (incoming picking).

**Pass:** PO state = Purchase; project filled.

### 2. Receive goods (incoming picking)

1. Open the incoming transfer from the PO or **Project → Logistics → Open receipts**.
2. Verify **Job / project** = P0006_2026 (auto from PO).
3. Set quantities → **Validate**.
4. If 2-step: complete the internal move **Input / SBU buffer → Stock** when prompted.

**Pass:** Picking **Done**; project **Logistics** badge moves toward **Received in warehouse**.

### 3. DDT (transport document)

1. On the done incoming picking, open tab **DDT / transport**.
2. Optional: fill **Carrier**, **Plate**, adjust **Transport reason** (default: Purchase).
3. On validate, **DDT number** is assigned (`DDT/2026/0001` sequence) if empty.
4. Click **Print DDT (SBU)** or **Print → DDT (SBU)** from the action menu.

**Pass:** PDF shows job, supplier as destinatario, lines, DDT number; matches paper DDT if used.

### 4. Project logistics tab

1. Open commessa **P0006_2026** → tab **Logistics**.
2. Check badge, inline list of pickings, stat buttons **Transfers / Receipts / Purchases**.

**Pass:** Incoming picking listed with DDT number; state consistent.

### 5. Optional — deliver to site

1. On the done incoming picking → **Deliver to site**,  
   **or** on the project → **Deliver stock to site**.
2. Validate the internal transfer **Stock → SBU / Site (cantiere)**.

**Pass:** Internal picking created with project; logistics badge **On site** after validation.

## Sign-off

| Step | Tester | Date | OK |
|------|--------|------|-----|
| PO → receipt | | | |
| DDT print | | | |
| Project logistics | | | |
| Site delivery (optional) | | | |

## Troubleshooting

| Symptom | Check |
|---------|--------|
| No receipt on PO | Product type / routes; confirm PO |
| No DDT report | Upgrade `sbu_stock_config`; report bound to `stock.picking` |
| No project on picking | PO `project_id`; upgrade module |
| Site button missing | Incoming must be **Done**; stock lines must have qty |
