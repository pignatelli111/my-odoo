# -*- coding: utf-8 -*-
"""Helpers for duplicate field-label regression tests (ignore mail.thread fields)."""

MAIL_FIELD_PREFIXES = (
    'message_',
    'activity_',
    'website_message',
)


def is_mail_internal_field(field_name):
    return field_name.startswith(MAIL_FIELD_PREFIXES)


def duplicate_custom_field_labels(env, model_name):
    """Return duplicate labels on SBU-owned fields (skip mail.thread / activity)."""
    Model = env[model_name]
    by_label = {}
    for fname, field in Model._fields.items():
        if is_mail_internal_field(fname):
            continue
        label = field.string
        if not label:
            continue
        by_label.setdefault(label, []).append(fname)
    return {label: names for label, names in by_label.items() if len(names) > 1}
