# -*- coding: utf-8 -*-
"""Backfill English source labels on closure document types (Italian via i18n/it.po only)."""

CLOSURE_LABELS_EN = {
    'sbu_closure.closure_doc_type_dop': 'DOP / Closure offer documentation',
    'sbu_closure.closure_doc_type_cert': 'Certifications (compliance / safety / testing)',
    'sbu_closure.closure_doc_type_collaudo': 'Handover / completion report',
    'sbu_closure.closure_doc_type_asbuilt': 'As-built drawings / executive documentation',
    'sbu_closure.closure_doc_type_consegna': 'Final documentation delivery to customer',
}


def _sync_closure_document_type_labels(env):
    for xmlid, en_label in CLOSURE_LABELS_EN.items():
        rec = env.ref(xmlid, raise_if_not_found=False)
        if rec:
            rec.write({'name': en_label})


def post_init_hook(env):
    _sync_closure_document_type_labels(env)
