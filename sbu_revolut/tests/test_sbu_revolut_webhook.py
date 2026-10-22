# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
import time
from unittest.mock import patch

from odoo.tests import HttpCase, tagged

from odoo.addons.sbu_revolut.services import revolut_client as rc


@tagged('post_install', '-at_install')
class TestSbuRevolutWebhook(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.sudo().write({
            'sbu_revolut_webhook_token': 'tok-123',
            'sbu_revolut_webhook_secret': 'wsk_secret',
        })
        cls.env['sbu.revolut.account'].create({
            'company_id': cls.company.id, 'revolut_account_id': 'acc-eur', 'name': 'Main',
            'currency_id': cls.company.currency_id.id,
        })

    def _post(self, body, secret='wsk_secret', token='tok-123'):
        ts = str(int(time.time() * 1000))
        sig = 'v1=' + hmac.new(secret.encode(), f'v1.{ts}.{body}'.encode(), hashlib.sha256).hexdigest()
        return self.url_open(
            f'/revolut/webhook/{token}', data=body.encode(),
            headers={'Revolut-Request-Timestamp': ts, 'Revolut-Signature': sig, 'Content-Type': 'application/json'},
        )

    def test_webhook_requires_valid_signature(self):
        body = json.dumps({'event': 'TransactionCreated', 'data': {
            'id': 'wh-1', 'state': 'completed', 'created_at': '2026-10-01T10:00:00Z',
            'legs': [{'leg_id': 'wh-1-leg', 'account_id': 'acc-eur', 'amount': 42.0, 'currency': 'EUR'}],
        }})
        Movement = self.env['sbu.revolut.transaction']
        self.assertEqual(self._post(body, token='wrong').status_code, 401)
        self.assertEqual(self._post(body, secret='forged').status_code, 401)
        self.assertFalse(Movement.search([('revolut_remote_id', '=', 'wh-1')]))
        with patch.object(rc, '_http', side_effect=AssertionError('no API call expected')):
            response = self._post(body)
        self.assertEqual(response.status_code, 200)
        movement = Movement.search([('revolut_remote_id', '=', 'wh-1')])
        self.assertEqual(movement.amount_signed, 42.0)
        self.assertEqual(movement.source, 'webhook')
