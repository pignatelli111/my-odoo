# -*- coding: utf-8 -*-
"""Read bank statements exported by any bank: CSV (Italian or English headers) and ISO 20022 CAMT.053.

Every parser returns {'iban': str|None, 'currency': str|None, 'lines': [line]} where a line is
{'date', 'amount' (money in > 0), 'label', 'ref', 'partner_name', 'partner_iban', 'unique_id'}.
"""
import csv
import hashlib
import io
import re
import unicodedata
from datetime import datetime
from xml.etree import ElementTree

DATE_FORMATS = ('%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y', '%Y-%m-%d', '%d/%m/%y', '%d-%m-%y', '%d.%m.%y', '%Y/%m/%d')
# Header words (lower case, no accents) → field. Checked in this order, first match wins.
HEADER_KEYS = (
    ('value_date', ('data valuta', 'value date', 'valuta')),
    ('date', ('data contabile', 'data operazione', 'data registrazione', 'booking date', 'transaction date',
              'completed date', 'date started', 'data', 'date')),
    ('debit', ('dare', 'addebiti', 'addebito', 'uscite', 'debit', 'money out', 'paid out')),
    ('credit', ('avere', 'accrediti', 'accredito', 'entrate', 'credit', 'money in', 'paid in')),
    ('amount', ('importo', 'amount', 'ammontare', 'movimento')),
    ('iban', ('iban',)),
    ('partner', ('beneficiario', 'ordinante', 'controparte', 'counterparty', 'payee', 'nome', 'name')),
    ('ref', ('riferimento', 'reference', 'cro', 'trn', 'id operazione', 'transaction id')),
    ('label', ('descrizione', 'causale', 'description', 'dettagli', 'details', 'narrative', 'memo')),
    ('currency', ('divisa', 'currency')),
)


class StatementParseError(ValueError):
    pass


def _plain(text):
    text = unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode()
    return re.sub(r'\s+', ' ', text).strip().lower()


def parse_amount(text):
    """'1.234,56' / '1,234.56' / '-12,5' / '12,50-' / '(12.50)' / '€ 1 234,56' → float."""
    raw = str(text or '').strip()
    if not raw:
        return None
    negative = raw.startswith('-') or raw.endswith('-') or (raw.startswith('(') and raw.endswith(')'))
    digits = re.sub(r'[^0-9,.]', '', raw)
    if not re.search(r'\d', digits):
        return None
    if ',' in digits and '.' in digits:
        decimal = ',' if digits.rfind(',') > digits.rfind('.') else '.'
    elif ',' in digits:
        decimal = ','
    else:
        decimal = '.'
    thousands = '.' if decimal == ',' else ','
    value = float(digits.replace(thousands, '').replace(decimal, '.'))
    return -value if negative else value


def parse_date(text):
    raw = str(text or '').strip()
    if not raw:
        return None
    raw = raw.replace('T', ' ').split(' ')[0]
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _unique_id(line, seen):
    base = '|'.join(str(line[k] or '') for k in ('date', 'amount', 'label', 'partner_name'))
    digest = hashlib.sha1(base.encode()).hexdigest()[:16]
    seen[digest] = seen.get(digest, 0) + 1
    return f'h{digest}-{seen[digest]}'  # identical lines of the same day stay distinct


def _decode(data):
    for encoding in ('utf-8-sig', 'cp1252', 'latin-1'):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise StatementParseError('Unreadable file encoding.')


def _map_header(row):
    mapping = {}
    for index, cell in enumerate(row):
        name = _plain(cell)
        if not name:
            continue
        for field, keys in HEADER_KEYS:
            if field in mapping:
                continue
            if any(name == key or name.startswith(key + ' ') or name.startswith(key + ' (') for key in keys):
                mapping[field] = index
                break
    return mapping


def parse_csv(data):
    text = _decode(data)
    sample = '\n'.join(text.splitlines()[:40])
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=';,\t|').delimiter
    except csv.Error:
        delimiter = ';' if sample.count(';') >= sample.count(',') else ','
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    header_index, mapping = None, {}
    for index, row in enumerate(rows[:40]):
        candidate = _map_header(row)
        if ('date' in candidate or 'value_date' in candidate) and (
                'amount' in candidate or 'debit' in candidate or 'credit' in candidate):
            header_index, mapping = index, candidate
            break
    if header_index is None:
        raise StatementParseError('No header row with a date and an amount (or debit / credit) column was found.')
    date_col = mapping.get('date', mapping.get('value_date'))
    seen, lines, currency = {}, [], None

    def cell(row, field):
        index = mapping.get(field)
        return row[index].strip() if index is not None and index < len(row) else ''

    for row in rows[header_index + 1:]:
        if not any(c.strip() for c in row):
            continue
        when = parse_date(row[date_col] if date_col < len(row) else '')
        if 'amount' in mapping:
            amount = parse_amount(cell(row, 'amount'))
        else:
            credit, debit = parse_amount(cell(row, 'credit')), parse_amount(cell(row, 'debit'))
            amount = None if credit is None and debit is None else (credit or 0.0) - abs(debit or 0.0)
        if not when or amount is None:
            continue  # totals, balances, blank lines
        currency = currency or cell(row, 'currency').upper() or None
        line = {
            'date': when,
            'amount': round(amount, 2),
            'label': cell(row, 'label') or cell(row, 'partner') or cell(row, 'ref'),
            'ref': cell(row, 'ref') or None,
            'partner_name': cell(row, 'partner') or None,
            'partner_iban': re.sub(r'\s', '', cell(row, 'iban')).upper() or None,
        }
        line['unique_id'] = f'r{line["ref"]}' if line['ref'] else _unique_id(line, seen)
        lines.append(line)
    return {'iban': None, 'currency': currency, 'lines': lines}


def _local(tag):
    return tag.rsplit('}', 1)[-1]


def _find(node, path):
    """Namespace-agnostic path: 'Acct/Id/IBAN'."""
    current = [node]
    for part in path.split('/'):
        current = [child for parent in current for child in parent if _local(child.tag) == part]
        if not current:
            return None
    return current[0]


def _text(node, path):
    found = _find(node, path) if node is not None else None
    return (found.text or '').strip() if found is not None and found.text else None


def parse_camt053(data):
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError as err:
        raise StatementParseError(f'Invalid CAMT XML: {err}') from err
    statements = [el for el in root.iter() if _local(el.tag) in ('Stmt', 'Rpt')]
    if not statements:
        raise StatementParseError('No <Stmt> found: this is not a CAMT.053 bank statement.')
    iban = currency = None
    seen, lines = {}, []
    for stmt in statements:
        iban = iban or _text(stmt, 'Acct/Id/IBAN')
        currency = currency or _text(stmt, 'Acct/Ccy')
        for entry in (el for el in stmt if _local(el.tag) == 'Ntry'):
            if (_text(entry, 'Sts/Cd') or _text(entry, 'Sts') or 'BOOK') not in ('BOOK', 'BOOKED'):
                continue  # pending entries are not on the statement yet
            amount_node = _find(entry, 'Amt')
            amount = float(amount_node.text) if amount_node is not None and amount_node.text else 0.0
            currency = currency or (amount_node.get('Ccy') if amount_node is not None else None)
            if _text(entry, 'CdtDbtInd') == 'DBIT':
                amount = -amount
            when = parse_date(_text(entry, 'BookgDt/Dt') or _text(entry, 'BookgDt/DtTm')
                              or _text(entry, 'ValDt/Dt') or _text(entry, 'ValDt/DtTm'))
            tx = _find(entry, 'NtryDtls/TxDtls')
            credit = amount > 0
            party = _find(tx, 'RltdPties/Dbtr' if credit else 'RltdPties/Cdtr') if tx is not None else None
            party_account = _find(tx, 'RltdPties/DbtrAcct' if credit else 'RltdPties/CdtrAcct') if tx is not None else None
            remittance = ' '.join(
                (el.text or '').strip() for el in (tx.iter() if tx is not None else []) if _local(el.tag) == 'Ustrd'
            ).strip()
            line = {
                'date': when,
                'amount': round(amount, 2),
                'label': remittance or _text(entry, 'AddtlNtryInf') or '',
                'ref': _text(tx, 'Refs/EndToEndId') if tx is not None else None,
                'partner_name': _text(party, 'Nm') or _text(party, 'Pty/Nm') if party is not None else None,
                'partner_iban': (_text(party_account, 'Id/IBAN') or None) if party_account is not None else None,
            }
            if line['ref'] in ('NOTPROVIDED', ''):
                line['ref'] = None
            unique = _text(entry, 'AcctSvcrRef') or _text(entry, 'NtryRef') or (
                _text(tx, 'Refs/AcctSvcrRef') if tx is not None else None)
            line['unique_id'] = f'c{unique}' if unique else _unique_id(line, seen)
            if when:
                lines.append(line)
    return {'iban': (iban or '').replace(' ', '').upper() or None, 'currency': currency, 'lines': lines}


def parse_statement(data, filename=''):
    head = data.lstrip()[:200]
    if head.startswith(b'<') or (filename or '').lower().endswith(('.xml', '.053')):
        return parse_camt053(data)
    return parse_csv(data)


__all__ = ['StatementParseError', 'parse_statement', 'parse_csv', 'parse_camt053', 'parse_amount', 'parse_date']
