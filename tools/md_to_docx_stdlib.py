#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimal Markdown → DOCX using stdlib only (no python-docx)."""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

WNS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def strip_md(text: str) -> str:
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    return text.strip()


def para(text: str = '', style: str | None = None) -> str:
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ''
    if not text:
        return f'<w:p {WNS}>{ppr}</w:p>'
    return (
        f'<w:p {WNS}>{ppr}'
        f'<w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r>'
        f'</w:p>'
    )


def heading(text: str, level: int) -> str:
    style = {0: 'Title', 1: 'Heading1', 2: 'Heading2', 3: 'Heading3'}.get(level, 'Heading2')
    return para(strip_md(text), style)


def table_xml(headers: list[str], rows: list[list[str]]) -> str:
    ncols = len(headers)
    grid = ''.join(f'<w:gridCol w:w="2400"/>' for _ in range(ncols))
    parts = [f'<w:tbl {WNS}><w:tblGrid>{grid}</w:tblGrid>']
    for r_idx, row in enumerate([headers] + rows):
        parts.append('<w:tr>')
        for c in range(ncols):
            val = row[c] if c < len(row) else ''
            bold = r_idx == 0
            rpr = '<w:rPr><w:b/></w:rPr>' if bold else ''
            parts.append(
                f'<w:tc><w:p {WNS}><w:r>{rpr}<w:t>{escape(strip_md(val))}</w:t></w:r></w:p></w:tc>'
            )
        parts.append('</w:tr>')
    parts.append('</w:tbl>')
    return ''.join(parts)


def is_table_sep(line: str) -> bool:
    return bool(re.match(r'^\|[\s\-:|]+\|$', line.strip()))


def parse_table_row(line: str) -> list[str]:
    return [strip_md(c.strip()) for c in line.strip().strip('|').split('|')]


def convert(md_path: Path, docx_path: Path) -> None:
    lines = md_path.read_text(encoding='utf-8').splitlines()
    body: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if s == '---':
            i += 1
            continue
        if s.startswith('# '):
            body.append(heading(s[2:], 0))
            i += 1
            continue
        if s.startswith('## '):
            body.append(heading(s[3:], 1))
            i += 1
            continue
        if s.startswith('### '):
            body.append(heading(s[4:], 2))
            i += 1
            continue
        if s.startswith('|') and i + 1 < len(lines) and is_table_sep(lines[i + 1]):
            headers = parse_table_row(s)
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                rows.append(parse_table_row(lines[i]))
                i += 1
            body.append(table_xml(headers, rows))
            body.append(para())
            continue
        if s.startswith('- '):
            body.append(para('• ' + strip_md(s[2:])))
            i += 1
            continue
        m = re.match(r'^(\d+)\.\s+(.+)$', s)
        if m:
            body.append(para(f'{m.group(1)}. {strip_md(m.group(2))}'))
            i += 1
            continue
        if not s:
            i += 1
            continue
        body.append(para(strip_md(s)))
        i += 1

    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document {WNS} xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<w:body>{"".join(body)}<w:sectPr/></w:body></w:document>'
    )

    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>'''

    rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''

    doc_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''

    styles = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:rPr><w:b/><w:sz w:val="24"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:rPr><w:b/><w:sz w:val="22"/></w:rPr></w:style>
</w:styles>'''

    docx_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(docx_path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', content_types)
        z.writestr('_rels/.rels', rels)
        z.writestr('word/_rels/document.xml.rels', doc_rels)
        z.writestr('word/document.xml', document_xml)
        z.writestr('word/styles.xml', styles)
    print(f'Wrote {docx_path}')


if __name__ == '__main__':
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('docs/REPORT_FEEDBACK_COSIMO_18_PUNTI_IT.md')
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix('.docx')
    convert(src.resolve(), dst.resolve())
