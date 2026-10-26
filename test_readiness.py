"""Isolated payment and deployment regression checks; no Telegram purchases."""
import io
import os
import tempfile
import time
import unittest
from unittest.mock import patch

import billing
from app import API, Bot, Store, TERMS, runtime_configuration
from test_app import API as FakeAPI


class ReadinessTests(unittest.TestCase):
    def test_test_api_routing(self):
        for testing, suffix in ((False, '/getMe'), (True, '/test/getMe')):
            with patch('urllib.request.urlopen', return_value=io.BytesIO(b'{"ok":true,"result":{}}')) as request:
                API('dummy', testing).call('getMe')
                self.assertEqual(request.call_args.args[0].full_url, 'https://api.telegram.org/botdummy' + suffix)

    def test_test_mode_isolation(self):
        base = {'TELEGRAM_TEST_ENVIRONMENT': 'true', 'TEST_BOT_TOKEN': 'test-only', 'TEST_DB_PATH': '/tmp/test-leaguehost.db'}
        with patch.dict(os.environ, base, clear=True):
            self.assertEqual(runtime_configuration(), ('test-only', '/tmp/test-leaguehost.db', True))
            for extra in ({'TEST_BOT_TOKEN': ''}, {'BOT_TOKEN': 'test-only'}, {'TEST_DB_PATH': ''},
                          {'DB_PATH': '/tmp/test-leaguehost.db'}, {'RAILWAY_ENVIRONMENT_NAME': 'production'},
                          {'TELEGRAM_TEST_ENVIRONMENT': 'typo'}):
                with self.subTest(extra=extra), patch.dict(os.environ, extra):
                    with self.assertRaises(ValueError):
                        runtime_configuration()

    def test_production_defaults_unchanged(self):
        with patch.dict(os.environ, {'BOT_TOKEN': 'dummy'}, clear=True):
            self.assertEqual(runtime_configuration(), ('dummy', '/data/leaguehost.db', False))

    def test_activation_requires_valid_owner_and_support(self):
        import json
        checks = {name: {'passed': True, 'evidence': 'independent-verification-reference'}
                  for name in billing.READINESS_CHECKS}
        record = json.dumps({'release_sha': 'verifiedsha123', 'approved_by': 'verified-operator', 'checks': checks})
        env = {'PAYMENTS_ENABLED': 'true', 'PAYSUPPORT_CONTACT': '@operator',
               'PAYMENT_RELEASE_SHA': 'verifiedsha123', 'PAYMENT_READINESS_EVIDENCE': record}
        with patch.dict(os.environ, env, clear=True):
            for owner in ('', '0', '-1', '²', str(2**52), '@operator'):
                with self.subTest(owner=owner), patch.dict(os.environ, {'OWNER_TELEGRAM_ID': owner}):
                    self.assertFalse(billing.checkout_enabled())
            with patch.dict(os.environ, {'OWNER_TELEGRAM_ID': '42'}):
                self.assertTrue(billing.checkout_enabled())
                with patch.dict(os.environ, {'PAYSUPPORT_CONTACT': '  '}):
                    self.assertFalse(billing.checkout_enabled())
                with patch.dict(os.environ, {'PAYMENT_READINESS_EVIDENCE': ''}):
                    self.assertFalse(billing.checkout_enabled())

    def test_plan_limits_expiry_and_group_isolation(self):
        for tier, allowed in (('free', 5), ('pro', 20), ('club', 35)):
            with self.subTest(tier=tier):
                store = Store(':memory:')
                self.addCleanup(store.db.close)
                store.db.execute("INSERT INTO leagues VALUES(-1,'Test',1)")
                if tier != 'free':
                    payload = billing.create_order(store.db, -1, 42, tier, True)
                    payment = dict(invoice_payload=payload, currency='XTR', total_amount=billing.PLANS[tier]['stars'],
                                   is_recurring=True, telegram_payment_charge_id='receipt', subscription_expiration_date=int(time.time()) + 3600)
                    self.assertTrue(billing.record_payment(store.db, payment, 42))
                    self.assertEqual(billing.current_plan(store.db, -2)[0], 'free')
                for index in range(allowed):
                    self.assertIn('id', store.open_round(-1, index))
                    store.db.execute('UPDATE rounds SET expires=0')
                if tier != 'club':
                    self.assertIn('error', store.open_round(-1, allowed))
                store.db.execute('UPDATE billing_receipts SET expires=0')
                self.assertEqual(billing.current_plan(store.db, -1)[0], 'free')

    def test_receipts_reject_wrong_buyer_currency_amount_or_missing_id(self):
        store = Store(':memory:')
        self.addCleanup(store.db.close)
        payload = billing.create_order(store.db, -1, 42, 'pro', True)
        payment = dict(invoice_payload=payload, currency='XTR', total_amount=100, is_recurring=True,
                       telegram_payment_charge_id='receipt', subscription_expiration_date=int(time.time()) + 3600)
        self.assertFalse(billing.record_payment(store.db, payment, 99))
        for change in ({'currency': 'USD'}, {'total_amount': 250}, {'telegram_payment_charge_id': ''},
                       {'invoice_payload': 'lh1:unknown'}, {'subscription_expiration_date': 1}):
            self.assertFalse(billing.record_payment(store.db, payment | change, 42))
        self.assertEqual(billing.current_plan(store.db, -1)[0], 'free')

    def test_support_and_terms_commands(self):
        store = Store(':memory:')
        self.addCleanup(store.db.close)
        api = FakeAPI()
        bot = Bot(store, api, 'LeagueHostBot')
        with patch.dict(os.environ, {'PAYSUPPORT_CONTACT': '@test_support'}):
            for command in ('support', 'paysupport', 'terms'):
                bot.handle({'message': {'text': '/' + command, 'from': {'id': 42}, 'chat': {'id': 42, 'type': 'private'}}})
                self.assertIn(TERMS if command == 'terms' else '@test_support', api.calls[-1][1]['text'])

    def test_database_reopen_preserves_records_and_admins(self):
        with tempfile.TemporaryDirectory() as folder:
            path = folder + '/leaguehost.db'
            store = Store(path)
            store.db.execute("INSERT INTO leagues VALUES(-1,'Existing',1)")
            store.db.execute('INSERT INTO bot_admins VALUES(99,42,1)')
            store.db.commit()
            store.db.close()
            store = Store(path)
            self.assertEqual(store.db.execute('SELECT title FROM leagues').fetchone()[0], 'Existing')
            self.assertTrue(Bot(store, FakeAPI(), 'LeagueHostBot').is_admin(99))
            self.assertEqual(store.db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            store.db.close()


if __name__ == '__main__':
    unittest.main()
