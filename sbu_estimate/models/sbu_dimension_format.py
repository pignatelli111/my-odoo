# -*- coding: utf-8 -*-
"""Shared L×H×P + mq labels for distinta → RDA → RFQ → PO."""


def format_sbu_dimensions(
    width_mm=0.0,
    height_mm=0.0,
    depth_mm=0.0,
    sqm_per_piece=0.0,
    sqm_total=0.0,
):
    parts = []
    dim_parts = []
    if width_mm:
        dim_parts.append('L %.0f' % width_mm)
    if height_mm:
        dim_parts.append('H %.0f' % height_mm)
    if depth_mm:
        dim_parts.append('P %.0f' % depth_mm)
    if dim_parts:
        parts.append(' × '.join(dim_parts) + ' mm')
    if sqm_per_piece:
        parts.append('%.3f mq/cad' % sqm_per_piece)
    if sqm_total and abs(sqm_total - sqm_per_piece) > 0.0001:
        parts.append('%.3f mq tot' % sqm_total)
    elif sqm_total and not sqm_per_piece:
        parts.append('%.3f mq tot' % sqm_total)
    return ' · '.join(parts)
