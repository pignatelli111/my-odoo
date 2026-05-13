# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Enable MTO for product selection, attach SBU internal route to the main warehouse, tighten reception."""
    # Global MTO route (standard xml id) — often inactive by default
    mto = env.ref('stock.route_warehouse0_mto', raise_if_not_found=False)
    if mto:
        mto.sudo().write({
            'active': True,
            'product_selectable': True,
            'product_categ_selectable': True,
        })

    wh = env.ref('stock.warehouse0', raise_if_not_found=False)
    route_internal = env.ref('sbu_stock_config.route_sbu_internal_site', raise_if_not_found=False)
    if wh and route_internal and route_internal not in wh.route_ids:
        wh.sudo().write({'route_ids': [(4, route_internal.id)]})

    # Buy route is created by purchase_stock; ensure main warehouse resupplies from purchase
    if wh and 'buy_to_resupply' in wh._fields and not wh.buy_to_resupply:
        try:
            wh.sudo().write({'buy_to_resupply': True})
        except Exception as exc:
            _logger.warning('SBU stock_config: could not enable buy_to_resupply on %s: %s', wh.display_name, exc)

    # Reception: move from 1-step to 2-step (Input → Stock) when still on default
    if wh and wh.reception_steps == 'one_step':
        try:
            wh.sudo().write({'reception_steps': 'two_steps'})
        except Exception as exc:
            _logger.warning(
                'SBU stock_config: could not set two-step reception on %s (enable Storage Locations if needed): %s',
                wh.display_name,
                exc,
            )
