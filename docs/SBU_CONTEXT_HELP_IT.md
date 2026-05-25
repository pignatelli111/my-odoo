# SBU context help (removed)

The **`sbu_ui_help`** module (floating **?** button, systray **Screen help**, RPC on every screen) was **removed from the repository** because it caused **memory pressure and container kills** on Odoo.sh production.

## After deploy

1. **Apps** → search **SBU Context Help** → **Uninstall** (on each database where it was installed).
2. Or Odoo.sh shell:
   ```python
   mod = env['ir.module.module'].search([('name', '=', 'sbu_ui_help')], limit=1)
   if mod.state == 'installed':
       mod.button_immediate_uninstall()
   ```
3. **Ctrl+F5** in the browser so backend assets reload without the help JS.

## User documentation

Use **`docs/guide/`** and **`docs/presentazione-cliente/`** for training material instead of in-app help.
