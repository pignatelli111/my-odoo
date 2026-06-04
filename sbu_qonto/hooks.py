# -*- coding: utf-8 -*-


def _sbu_qonto_refresh_transfer_dates(env):
    """Backfill transfer_date (runs on install; upgrade uses migrations/)."""
    env['sbu.qonto.transaction'].sudo()._sbu_qonto_refresh_all_dates()
    env.cr.execute(
        """
        UPDATE sbu_qonto_transaction
        SET transfer_at = COALESCE(settled_at, emitted_at),
            transfer_date = (COALESCE(settled_at, emitted_at))::date
        WHERE transfer_date IS NULL
          AND (settled_at IS NOT NULL OR emitted_at IS NOT NULL)
        """
    )


def post_init_hook(env):
    env['res.company']._sbu_sync_qonto_cron_active()
    _sbu_qonto_refresh_transfer_dates(env)
