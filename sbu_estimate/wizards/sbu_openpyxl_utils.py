# -*- coding: utf-8 -*-
"""Shared openpyxl helpers (suppress harmless header/footer parse noise on Odoo.sh)."""
import io
import warnings
from contextlib import contextmanager


@contextmanager
def _ignore_openpyxl_header_footer_warnings():
    with warnings.catch_warnings():
        warnings.filterwarnings(
            'ignore',
            message='Cannot parse header or footer.*',
            category=UserWarning,
        )
        yield


def load_openpyxl_workbook(source, **kwargs):
    """Load workbook from path or raw bytes; ignore openpyxl header/footer UserWarning."""
    import openpyxl

    with _ignore_openpyxl_header_footer_warnings():
        if isinstance(source, (bytes, bytearray)):
            return openpyxl.load_workbook(io.BytesIO(source), **kwargs)
        return openpyxl.load_workbook(source, **kwargs)
