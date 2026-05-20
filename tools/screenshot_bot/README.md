# Screenshot bot — automatic PNGs for SBU documentation

Small **Playwright** helper: saves screenshots into `docs/guide/screenshots/` when you open Odoo URLs (batch, manual, or **watch** on every navigation).

This is **not** a browser extension. It opens **Chromium** controlled by Python on your PC.

## Install (once)

From the `my-odoo` folder:

```powershell
pip install playwright
playwright install chromium
```

## 1) Save Odoo login (once)

```powershell
cd "f:\TASK\20 . Odoo\my-odoo"
python tools/screenshot_bot/capture.py login
```

- Browser opens → log in to production Odoo.
- When you see the home / SBU apps, go back to the terminal and press **Enter**.
- Creates `tools/screenshot_bot/auth.json` (gitignored — do not commit).

## 2) Automatic batch (URL list)

```powershell
copy tools\screenshot_bot\capture_plan.example.json tools\screenshot_bot\capture_plan.json
```

Edit `capture_plan.json`:

- Set `base_url`
- For each shot: `file` (PNG name) + `path` (URL path after domain)
- Odoo 19 URLs often look like `/odoo/action-123/...` — open the screen in your browser, **copy the path** from the address bar.

Run:

```powershell
python tools/screenshot_bot/capture.py run
```

## 3) Manual mode (best for wizards and popups)

You click through Odoo; the bot saves when you ask.

```powershell
python tools/screenshot_bot/capture.py manual
```

- Navigate in the browser.
- In the terminal, type the filename (e.g. `18-wizard-import-anaco-opzioni.png`) and press **Enter**.
- Type `q` to quit.

## 4) Watch mode — screenshot on every URL change

**Closest to “photo when I open a URL”:**

```powershell
python tools/screenshot_bot/capture.py watch
```

- Browse Odoo normally (same logged-in session).
- Each time the **address bar URL changes**, after ~1.5s a PNG is saved as `watch-001-….png`, `watch-002-….png`, …
- Close the browser window to stop.
- Rename the good files to `20-distinta-caso-perdita-44.png`, etc.

## Output

Default folder: `docs/guide/screenshots/` (same as Cosimo’s guide).

## Security

- `auth.json` contains session cookies — **never commit** or share.
- Do not screenshot Qonto API secrets; blur if needed.
- Use production only if you intend real UI; otherwise use a test DB.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `playwright not found` | `pip install playwright` + `playwright install chromium` |
| Login page instead of SBU | Run `capture.py login` again |
| Blank / loading screenshot | Increase `wait_ms` in `capture_plan.json` |
| Wrong Odoo URL in plan | Copy path from browser after opening the exact screen |

## Link to shot list

See `docs/guide/GUIDA_TEST_AUTONOMO_COSIMO.md` — section “Priority 1 / 2” for recommended filenames.
