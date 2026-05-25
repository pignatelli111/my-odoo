# -*- coding: utf-8 -*-
"""Idempotent SQL cleanup if sbu_ui_help is still marked installed (no ORM uninstall)."""


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        "SELECT 1 FROM ir_module_module WHERE name = %s AND state = 'installed'",
        ('sbu_ui_help',),
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        UPDATE ir_module_module
           SET state = 'uninstalled', latest_version = NULL
         WHERE name = 'sbu_ui_help'
        """
    )
    cr.execute(
        """
        DELETE FROM ir_module_module_dependency
         WHERE module_id IN (SELECT id FROM ir_module_module WHERE name = 'sbu_ui_help')
            OR name = 'sbu_ui_help'
        """
    )
    cr.execute("DELETE FROM ir_model_data WHERE module = 'sbu_ui_help'")
    cr.execute("DELETE FROM ir_asset WHERE path LIKE %s", ('%sbu_ui_help%',))
