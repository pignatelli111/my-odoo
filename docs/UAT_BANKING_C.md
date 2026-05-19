# UAT Phase C — Qonto import + matching (no full reconciliation)

**Module:** `sbu_qonto` **19.0.1.0.4+**  
**Scope:** Scheduled import + improved suggestions; **not** automatic bank journal reconciliation.

## Setup (once)

1. **Settings → SBU integrations** (or company tab **Qonto**):
   - Qonto API login + secret key + IBAN
   - **Enable Qonto import cron** = on
   - **Suggest matches after import** = on (default)
2. Confirm **Scheduled Actions → SBU Qonto: import movements** is **Active** (auto when step 1 is on).
3. Optional: webhook URL `https://<your-odoo>/qonto/webhook/<token>`.

## UAT flow

### 1. Import

1. Post a **customer inbound payment** in Odoo (known amount + payment reference).
2. **Settings → Import Qonto movements now** (or wait for hourly cron).
3. **Accounting → Qonto movements** — new line with same amount/reference.

**Pass:** Movement imported; `state` = Imported.

### 2. Suggest match

1. Select movement(s) → **Suggest match** (or wait for post-import suggestion).
2. Check **Match confidence** + **Suggested payment** / **Suggested invoice** + **Match hint**.

**Pass:** High confidence when reference and amount align; medium when amount-only in date window.

### 3. Confirm link (manual)

| Confidence | Action |
|------------|--------|
| High | **Match (high confidence)** → `Matched in Odoo` |
| Medium / low | Review → **Apply suggestion** or pick payment/invoice manually |

**Pass:** `match_payment_id` or `match_invoice_id` set; still **no** automatic reconciliation on bank journal.

### 4. Ignore noise

1. Bank fee / internal transfer → **Ignore**.

**Pass:** `state` = Ignored; excluded from next match run.

## Out of scope (Phase C)

- Odoo bank statement reconciliation
- Webhook HMAC verification
- Revolut (same pattern in `sbu_revolut` — separate enablement)

## Sign-off

| Step | OK |
|------|-----|
| Cron import | |
| Suggestion after import | |
| High-confidence match | |
| Apply medium suggestion | |
| Ignore | |
