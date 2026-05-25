# -*- coding: utf-8 -*-
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class SbuQontoWebhook(http.Controller):
    @http.route(
        '/qonto/webhook/<string:token>',
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False,
    )
    def qonto_webhook(self, token, **kwargs):
        """Receive Qonto webhooks; token must match res.company.sbu_qonto_webhook_token."""
        if not token:
            return request.make_response('Unauthorized', status=401)
        company = request.env['res.company'].sudo().search(
            [('sbu_qonto_webhook_token', '=', token)],
            limit=1,
        )
        if not company:
            return request.make_response('Unauthorized', status=401)
        raw = request.httprequest.get_data(cache=False, as_text=True)
        try:
            Transaction = request.env['sbu.qonto.transaction'].sudo().with_company(company)
            count = Transaction.qonto_process_webhook_payload(company, raw)
            if count:
                Transaction._sbu_post_import_process(company)
        except Exception:
            _logger.exception('Qonto webhook processing failed for company %s', company.id)
            return request.make_response('Error', status=500)
        return request.make_response('OK', status=200)
