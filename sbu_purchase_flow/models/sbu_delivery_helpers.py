# -*- coding: utf-8 -*-
"""Resolve default delivery destination text for PR lines (Cosimo point 17)."""

from .sbu_budget_helpers import sbu_cost_family_for_pr_line


def sbu_delivery_destination_for_line(env, pr_line, project=None, overwrite=False):
    """Return destination string or False if no rule / line already has destination."""
    if not pr_line:
        return False
    if pr_line.destination and not overwrite:
        return False
    project = project or pr_line.request_id.project_id
    rule = env['sbu.delivery.standard'].match_for_pr_line(pr_line, project)
    if not rule:
        return False
    return rule.format_destination(project)
