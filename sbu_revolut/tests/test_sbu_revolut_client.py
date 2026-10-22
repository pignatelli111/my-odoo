# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
import json
import time

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

from odoo.tests import BaseCase, tagged

from odoo.addons.sbu_revolut.services import revolut_client as rc


def _b64decode(part):
    return base64.urlsafe_b64decode(part + '=' * (-len(part) % 4))


@tagged('post_install', '-at_install')
class TestSbuRevolutClient(BaseCase):

    def test_client_assertion_is_valid_rs256_jwt(self):
        key_pem, cert_pem = rc.generate_private_key_and_certificate('Suburban SRL')
        jwt = rc.build_client_assertion(key_pem, 'client-123', 'suburban.odoo.com')
        header, payload, signature = jwt.split('.')
        self.assertEqual(json.loads(_b64decode(header)), {'alg': 'RS256', 'typ': 'JWT'})
        claims = json.loads(_b64decode(payload))
        self.assertEqual(claims['iss'], 'suburban.odoo.com')
        self.assertEqual(claims['sub'], 'client-123')
        self.assertEqual(claims['aud'], 'https://revolut.com')
        self.assertGreater(claims['exp'], time.time())
        public_key = x509.load_pem_x509_certificate(cert_pem.encode()).public_key()
        public_key.verify(  # raises if the signature does not match the uploaded certificate
            _b64decode(signature), f'{header}.{payload}'.encode(), padding.PKCS1v15(), hashes.SHA256(),
        )

    def test_issuer_and_consent_url(self):
        self.assertEqual(
            rc.issuer_from_redirect_uri('https://suburban.odoo.com/revolut/oauth/callback'), 'suburban.odoo.com',
        )
        url = rc.consent_url(False, 'cid', 'https://x.odoo.com/revolut/oauth/callback', '1:abc')
        self.assertTrue(url.startswith('https://business.revolut.com/app-confirm?'))
        self.assertIn('response_type=code', url)
        self.assertIn('state=1%3Aabc', url)
        self.assertTrue(rc.consent_url(True, 'cid', 'https://x').startswith('https://sandbox-business.revolut.com/'))

    def test_webhook_signature(self):
        secret = 'wsk_test_secret'
        body = '{"event":"TransactionCreated","data":{"id":"t1"}}'
        ts = str(int(time.time() * 1000))
        good = 'v1=' + hmac.new(secret.encode(), f'v1.{ts}.{body}'.encode(), hashlib.sha256).hexdigest()
        self.assertTrue(rc.verify_webhook_signature(secret, ts, body, good))
        self.assertTrue(rc.verify_webhook_signature(secret, ts, body.encode(), f'v1=deadbeef,{good}'))
        self.assertFalse(rc.verify_webhook_signature(secret, ts, body + ' ', good))
        self.assertFalse(rc.verify_webhook_signature('other', ts, body, good))
        self.assertFalse(rc.verify_webhook_signature(secret, ts, body, None))
        self.assertFalse(rc.verify_webhook_signature('', ts, body, good))
        stale = str(int(time.time() * 1000) - 10 * 60 * 1000)
        stale_sig = 'v1=' + hmac.new(secret.encode(), f'v1.{stale}.{body}'.encode(), hashlib.sha256).hexdigest()
        self.assertFalse(rc.verify_webhook_signature(secret, stale, body, stale_sig))
