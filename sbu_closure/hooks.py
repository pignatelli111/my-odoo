# -*- coding: utf-8 -*-
"""Ensure closure document type labels use English as DB source (Italian via it.po)."""

CLOSURE_LABELS = {
    'sbu_closure.closure_doc_type_dop': (
        'DOP / Closure offer documentation',
        'DOP / Documentazione di offerta in chiusura',
    ),
    'sbu_closure.closure_doc_type_cert': (
        'Certifications (compliance / safety / testing)',
        'Certificazioni (conformità / sicurezza / collaudi)',
    ),
    'sbu_closure.closure_doc_type_collaudo': (
        'Handover / completion report',
        'Verbale di collaudo / fine lavori',
    ),
    'sbu_closure.closure_doc_type_asbuilt': (
        'As-built drawings / executive documentation',
        'Elaborati as-built / redazione esecutiva',
    ),
    'sbu_closure.closure_doc_type_consegna': (
        'Final documentation delivery to customer',
        'Consegna documentazione finale al cliente',
    ),
}


def _it_lang_active(env):
    """True when Italian is installed (Odoo.sh test DBs are often en_US only)."""
    return bool(
        env['res.lang'].with_context(active_test=False).search(
            [('code', '=', 'it_IT')], limit=1,
        )
    )


def _sync_closure_document_type_translations(env):
    apply_it = _it_lang_active(env)
    for xmlid, (en_label, it_label) in CLOSURE_LABELS.items():
        rec = env.ref(xmlid, raise_if_not_found=False)
        if not rec:
            continue
        rec.write({'name': en_label})
        if apply_it:
            rec.with_context(lang='it_IT').write({'name': it_label})


def post_init_hook(env):
    _sync_closure_document_type_translations(env)
