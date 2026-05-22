# -*- coding: utf-8 -*-
"""Shared REV + date labels for SBU documents (Cosimo point 18)."""

from odoo import fields


def sbu_revision_sort_key(revision):
    """Order REV00 < REV01 < REV10."""
    rev = (revision or 'REV00').strip().upper()
    if rev.startswith('REV'):
        suffix = rev[3:]
        try:
            return int(suffix) if suffix else 0
        except ValueError:
            pass
    return 0


def sbu_date_label(value):
    if not value:
        return False
    if hasattr(value, 'date') and callable(value.date):
        value = value.date()
    return fields.Date.to_string(value)


def sbu_format_revision_label(*parts, separator=' · '):
    cleaned = [str(p).strip() for p in parts if p and str(p).strip()]
    return separator.join(cleaned)


def sbu_doc_name_with_revision(doc_name, revision_label, separator=' · '):
    """Prefix operational doc ref with job REV label."""
    doc = (doc_name or '').strip()
    rev = (revision_label or '').strip()
    if doc and rev:
        return f'{doc}{separator}{rev}'
    return doc or rev


def sbu_estimate_revision_label(estimate):
    """e.g. P2026-0042 BLACKROCK · REV02 · 2026-05-20"""
    name = (estimate.name or '').strip()
    if name in ('', 'New', 'Nuovo'):
        name = False
    site = (estimate.job_site or '').strip()
    if name and site:
        head = f'{name} {site}'
    else:
        head = name or site
    return sbu_format_revision_label(
        head,
        (estimate.revision or '').strip(),
        sbu_date_label(estimate.date),
    )


def sbu_project_revision_label(project):
    """e.g. [P0015_2026] BLACKROCK · REV02 · 2026-05-20"""
    code = (project.sbu_project_code or '').strip()
    site = (project.sbu_job_site or '').strip()
    title = (project.name or '').strip()
    if code:
        head = f'[{code}]'
        if site:
            head = f'{head} {site}'
        elif title and not title.startswith('['):
            head = f'{head} {title}'
        else:
            head = title or head
    else:
        head = title or site
    est = project.sbu_estimate_id
    rev = (est.revision or '').strip() if est else ''
    if est and est.date:
        dt = sbu_date_label(est.date)
    else:
        dt = sbu_date_label(project.create_date)
    return sbu_format_revision_label(head, rev, dt)
