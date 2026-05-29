# -*- coding: utf-8 -*-
"""Helpers for duplicate field-label regression tests (ignore mail.thread fields)."""

MAIL_FIELD_PREFIXES = (
    'message_',
    'activity_',
    'website_message',
)


def is_mail_internal_field(field_name):
    return field_name.startswith(MAIL_FIELD_PREFIXES)


def duplicate_custom_field_labels(env, model_name, field_prefix=None):
    """Return duplicate labels on fields (skip mail.thread / activity).

    When field_prefix is set (e.g. ``sbu_``), only those fields are checked — use
    for inherited models like ``project.project`` that already have core Odoo fields.
    """
    Model = env[model_name]
    by_label = {}
    for fname, field in Model._fields.items():
        if is_mail_internal_field(fname):
            continue
        if field_prefix and not fname.startswith(field_prefix):
            continue
        label = field.string
        if not label:
            continue
        by_label.setdefault(label, []).append(fname)
    return {label: names for label, names in by_label.items() if len(names) > 1}
