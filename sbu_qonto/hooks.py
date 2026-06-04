# -*- coding: utf-8 -*-


def post_init_hook(env):
    env['res.company']._sbu_sync_qonto_cron_active()
    env['sbu.qonto.transaction'].sudo().search(
        [('raw_json', '!=', False)]
    )._sbu_rebuild_dates_from_raw_json()
