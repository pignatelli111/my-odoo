# -*- coding: utf-8 -*-


def post_init_hook(env):
    env['res.company']._sbu_sync_qonto_cron_active()
