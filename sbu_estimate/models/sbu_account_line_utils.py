# -*- coding: utf-8 -*-
"""Helpers for invoice / move / PO lines (Odoo 19 display_type='product')."""

# Section and note lines only; product lines use display_type False or 'product'.
SBU_SKIP_DISPLAY_TYPES = frozenset({'line_section', 'line_note'})


def sbu_is_product_line(line):
    """True for normal product/account lines (not section/note)."""
    display_type = line.display_type or 'product'
    return display_type not in SBU_SKIP_DISPLAY_TYPES
