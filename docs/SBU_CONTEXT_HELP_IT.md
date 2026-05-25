# SBU context help (removed)

The **`sbu_ui_help`** module (floating **?** button, systray **Screen help**, RPC on every screen) was **removed** because it caused **memory pressure and container kills** on Odoo.sh production.

A **minimal stub** (`sbu_ui_help` **19.0.1.0.10**, no JS/assets) is kept in git only so production can **load the DB** and run a migration that **uninstalls** the app. After a **green** production build, the stub can be deleted from git in a follow-up commit.

## After deploy

1. Wait for a **green** build on branch **`real`** (stub auto-uninstalls on upgrade).
2. If help still appears: **Apps** → **SBU Context Help** → **Uninstall**.
3. **Ctrl+F5** in the browser so backend assets reload without the help JS.

## User documentation

Use **`docs/guide/`** and **`docs/presentazione-cliente/`** for training material instead of in-app help.
