-- Run on Odoo.sh branch "real" via the SQL button (works when Shell is disabled).
-- Targets the LIVE production database (not a failed red build container).
-- Safe to run more than once.

-- 1) Check current state
SELECT id, name, state, latest_version
  FROM ir_module_module
 WHERE name = 'sbu_ui_help';

-- 2) Mark uninstalled (so the next build does not load this addon at startup)
UPDATE ir_module_module
   SET state = 'uninstalled',
       latest_version = NULL
 WHERE name = 'sbu_ui_help';

-- 3) Drop dependency rows
DELETE FROM ir_module_module_dependency
 WHERE module_id IN (SELECT id FROM ir_module_module WHERE name = 'sbu_ui_help')
    OR name = 'sbu_ui_help';

-- 4) Remove module metadata and backend assets
DELETE FROM ir_model_data WHERE module = 'sbu_ui_help';
DELETE FROM ir_asset WHERE path LIKE '%sbu_ui_help%';

-- 5) Confirm
SELECT id, name, state FROM ir_module_module WHERE name = 'sbu_ui_help';
