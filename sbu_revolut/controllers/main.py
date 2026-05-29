# -*- coding: utf-8 -*-
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class SbuRevolutWebhook(http.Controller):
    @http.route(
        '/revolut/webhook/<string:token>',
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False,
    )
    def revolut_webhook(self, token, **kwargs):
        if not token:
            return request.make_response('Unauthorized', status=401)
        company = request.env['res.company'].sudo().search(
            [('sbu_revolut_webhook_token', '=', token)],
            limit=1,
        )
        if not company:
            return request.make_response('Unauthorized', status=401)
        raw = request.httprequest.get_data(cache=False, as_text=True)
        try:
            request.env['sbu.revolut.transaction'].sudo().with_company(company).revolut_process_webhook_payload(
                company, raw
            )
        except Exception:
            _logger.exception('Revolut webhook processing failed for company %s', company.id)
            return request.make_response('Error', status=500)
        return request.make_response('OK', status=200)
