# -*- coding: utf-8 -*-
"""Map ANACO workflow route codes to SBU purchase request document types."""

WORKFLOW_ROUTE_TO_REQUEST_TYPE = {
    'VC/VS': 'vt',
    'ST': 'st',
    'PAN': 'rda',
    'LA': 'rda',
    'LZ': 'fe',
    'PRF': 'rda',
    'FT/FTF': 'rda',
    'SE': 'rda',
    'ASS': 'aco',
    'ACC': 'aco',
    'GUA': 'aco',
    'TRN': 'lds',
    'POS': 'acp',
    'PM': 'other',
    'CNT': 'other',
    'EXT': 'other',
}


def workflow_route_to_request_type(route_code):
    return WORKFLOW_ROUTE_TO_REQUEST_TYPE.get((route_code or '').strip(), 'other')
