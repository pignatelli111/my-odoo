# -*- coding: utf-8 -*-
"""Safe field domains for Odoo 19 web client (empty rhs breaks Domain parser)."""


def sbu_domain_same_estimate(estimate):
    """Filter rows by estimate_id, or match nothing when estimate is unset."""
    if estimate:
        return [('estimate_id', '=', estimate.id)]
    return [('id', '=', False)]
