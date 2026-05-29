# UAT Phase C — Qonto import, partners, auto customer payments

**Module:** `sbu_qonto` **19.0.1.0.7+**  
**Scope:** Import, beneficiary sync, auto customer payment register; **not** bank statement line reconciliation.

## Setup (once)

1. **Settings → SBU integrations** (or company tab **Qonto (SBU)**):
   - Qonto API login + secret key + IBAN
   - **Enable Qonto import cron** = on
   - **Sync Qonto beneficiaries on import** = on (default)
   - **Auto-register customer payments** = on (default)
   - **Auto-register vendor payments** = off until UAT outbound
2. Confirm **Scheduled Actions → SBU Qonto: import movements** is **Active**.
3. Optional: webhook URL `https://<your-odoo>/qonto/webhook/<token>`.

## UAT flow

### 0. Partner sync (punto 14)

1. **Sync Qonto suppliers** (settings or company tab).
2. **Contacts** — new/updated supplier with Qonto IBAN / beneficiary id.

**Pass:** At least one beneficiary from Qonto appears as supplier.

### 1. Import

1. Post a **customer invoice** in Odoo (known residual).
2. Receive equivalent inbound movement in Qonto (or sandbox).
3. **Import Qonto movements now** (or cron).

**Pass:** Movement imported; counterparty linked when IBAN known.

### 2. Auto reconcile customer invoice (punto 10)

1. Movement **inbound**, reference contains invoice number, amount = residual.
2. After import pipeline: `state` = **Matched**, customer invoice residual = 0.

**Pass:** Payment created without manual **Register payment** (high confidence).

### 3. Suggest / manual (exceptions)

1. Ambiguous amount → **Suggest match** → review hint.
2. Medium confidence → **Apply suggestion** or **Register customer payment**.

### 4. Vendor outbound (optional)

1. Post vendor bill; outbound movement with matching reference.
2. Enable **Auto-register vendor payments** only after review.
3. Or use **Register vendor payment** on the movement form.

### 5. Ignore noise

Bank fee / internal transfer → **Ignore**.

## Out of scope (next phase)

- Odoo bank statement ↔ Qonto journal reconciliation
- Webhook HMAC verification

## Sign-off

| Step | OK |
|------|-----|
| Partner sync | |
| Cron import | |
| Auto customer payment (high) | |
| Manual suggest/match | |
| Vendor payment (manual or auto) | |
| Ignore | |
