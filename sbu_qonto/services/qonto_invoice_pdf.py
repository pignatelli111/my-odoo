# -*- coding: utf-8 -*-
"""Read the VAT summary of Italian e-invoice PDFs exported by Qonto.

Qonto renders FatturaPA invoices with a summary block::

    Imponibile Imposta IVA (%) Natura/Esigibilità Rif. Normativo
    €88,64 €8,86 10
    €1.200,00 €0,00 0 N6.3 Inversione contabile
    Importo totale documento
    €    97,50
"""
import io
import re

_AMOUNT = r'-?\s?€?\s?-?[\d.]*\d,\d{2}'
_ROW_RE = re.compile(
    rf'€\s?(?P<net>-?[\d.]*\d,\d{{2}})\s+€\s?(?P<tax>-?[\d.]*\d,\d{{2}})\s+(?P<rate>\d{{1,2}}(?:[.,]\d+)?)(?P<rest>[^\n]*)'
)
_NATURE_RE = re.compile(r'\bN\d(?:\.\d{1,2})?\b')
_TOTAL_RE = re.compile(r'Importo totale documento\s*€?\s*(?P<total>-?[\d.]*\d,\d{2})')
_SDI_RE = re.compile(r'Identificativo SDI:\s*(\d+)')
_HEADER = 'Imponibile Imposta IVA'


def parse_it_amount(text):
    return float(text.replace(' ', '').replace('€', '').replace('.', '').replace(',', '.'))


def extract_pdf_text(pdf_bytes):
    """Plain text of a PDF (Odoo's PyPDF2 / pypdf wrapper)."""
    from odoo.tools.pdf import PdfFileReader  # noqa: PLC0415 — keeps the parser importable without Odoo
    reader = PdfFileReader(io.BytesIO(pdf_bytes), strict=False)
    return '\n'.join((page.extract_text() or '') for page in reader.pages)


def parse_vat_summary(text):
    """Return {'lines': [{'net', 'tax', 'rate', 'nature'}], 'total', 'sdi_id'} or None."""
    if not text or _HEADER not in text:
        return None
    block = text.split(_HEADER, 1)[1]
    block = block.split('Importo totale documento', 1)[0]
    lines = []
    for match in _ROW_RE.finditer(block):
        nature = _NATURE_RE.search(match.group('rest') or '')
        lines.append({
            'net': parse_it_amount(match.group('net')),
            'tax': parse_it_amount(match.group('tax')),
            'rate': float(match.group('rate').replace(',', '.')),
            'nature': nature.group(0) if nature else False,
        })
    if not lines:
        return None
    total = _TOTAL_RE.search(text)
    sdi = _SDI_RE.search(text)
    return {
        'lines': lines,
        'total': parse_it_amount(total.group('total')) if total else None,
        'sdi_id': sdi.group(1) if sdi else False,
    }
