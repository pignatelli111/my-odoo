# -*- coding: utf-8 -*-
import json
import logging
import secrets

from odoo import http
from odoo.http import request

from odoo.addons.sbu_revolut.services.revolut_client import verify_webhook_signature

_logger = logging.getLogger(__name__)


class SbuRevolutController(http.Controller):

    @http.route('/revolut/webhook/<string:token>', type='http', auth='public', methods=['POST'], csrf=False)
    def revolut_webhook(self, token, **kwargs):
        """Revolut webhook v2: URL token + HMAC signature (Revolut-Signature) are both required."""
        companies = request.env['res.company'].sudo().search([('sbu_revolut_webhook_token', '!=', False)])
        company = next(
            (c for c in companies if secrets.compare_digest(c.sbu_revolut_webhook_token, token or '')),
            None,
        )
        if not company:
            return request.make_response('Unauthorized', status=401)
        raw = request.httprequest.get_data(cache=False)
        headers = request.httprequest.headers
        if not verify_webhook_signature(
            company.sbu_revolut_webhook_secret,
            headers.get('Revolut-Request-Timestamp'),
            raw,
            headers.get('Revolut-Signature'),
        ):
            _logger.warning('Revolut webhook rejected: invalid signature (company %s)', company.id)
            return request.make_response('Invalid signature', status=401)
        try:
            event = json.loads(raw)
        except ValueError:
            return request.make_response('Invalid JSON', status=400)
        try:
            request.env['sbu.revolut.transaction'].sudo().with_company(company).revolut_process_webhook_event(
                company, event,
            )
        except Exception:
            _logger.exception('Revolut webhook processing failed for company %s', company.id)
            return request.make_response('Error', status=500)
        return request.make_response('OK', status=200)

    @http.route('/revolut/oauth/callback', type='http', auth='user', methods=['GET'])
    def revolut_oauth_callback(self, code=None, state=None, error=None, **kwargs):
        """Revolut redirects here after "Authorize" with ?code=…; the admin must be logged in to Odoo."""
        company_id, _sep, nonce = (state or '').partition(':')
        Company = request.env['res.company']
        company = Company.browse(int(company_id)) if company_id.isdigit() else Company
        if not request.env.user.has_group('base.group_system'):
            return request.make_response('Only an administrator can connect Revolut.', status=403)
        company = company.sudo().exists()
        if not state:
            # Revolut may not echo "state": accept only one pending authorization started from Odoo.
            pending = Company.sudo().search([
                ('sbu_revolut_connection_state', '=', 'pending'), ('sbu_revolut_oauth_state', '!=', False),
            ])
            if len(pending) == 1:
                company, nonce = pending, pending.sbu_revolut_oauth_state
        if not company or not company.sbu_revolut_oauth_state or not secrets.compare_digest(
            company.sbu_revolut_oauth_state, nonce,
        ):
            return request.make_response('Unknown or expired Revolut authorization request.', status=400)
        company.sbu_revolut_oauth_state = False
        if error or not code:
            company._sbu_revolut_set_error(f'Revolut authorization refused: {error or "no code"}')
        else:
            try:
                company._sbu_revolut_exchange_code(code)
                request.env['sbu.revolut.account'].sudo()._sbu_sync_company_accounts(company)
            except Exception as err:  # noqa: BLE001 — shown to the admin on the company form
                _logger.exception('Revolut token exchange failed')
                company._sbu_revolut_set_error(str(err))
        return request.redirect(f'/odoo/action-base.action_res_company_form/{company.id}')
