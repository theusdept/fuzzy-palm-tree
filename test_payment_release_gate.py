"""Release-gate regressions using synthetic fixtures and isolated SQLite only."""
import copy
import json
import os
import time
import unittest
from unittest.mock import patch

import billing
from app import Bot, Store
from test_app import API as FakeAPI


class PaymentReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.release = 'a' * 40
        self.record = {
            'release_sha': self.release,
            'approved_by': 'unit-test-operator',
            'checks': {
                name: {'passed': True, 'evidence': 'unit-test-fixture:' + name}
                for name in billing.READINESS_CHECKS
            },
        }
        self.env = {
            'PAYMENTS_ENABLED': 'true',
            'OWNER_TELEGRAM_ID': '42',
            'PAYSUPPORT_CONTACT': '@unit_test_support',
            'PAYMENT_RELEASE_SHA': self.release,
            'PAYMENT_READINESS_EVIDENCE': json.dumps(self.record),
        }
        self.environment = patch.dict(os.environ, self.env, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def assert_record_blocked(self, record):
        with patch.dict(os.environ, {'PAYMENT_READINESS_EVIDENCE': json.dumps(record)}):
            self.assertIs(billing.checkout_enabled(), False)

    def test_complete_fixture_accepts_matching_fallback_revision(self):
        self.assertIs(billing.checkout_enabled(), True)

    def test_complete_fixture_accepts_matching_railway_revision(self):
        with patch.dict(os.environ, {'RAILWAY_GIT_COMMIT_SHA': self.release,
                                     'PAYMENT_RELEASE_SHA': 'b' * 40}):
            self.assertIs(billing.checkout_enabled(), True)

    def test_fallback_cannot_override_railway_revision(self):
        with patch.dict(os.environ, {'RAILWAY_GIT_COMMIT_SHA': 'b' * 40}):
            self.assertIs(billing.checkout_enabled(), False)

    def test_release_is_required_and_must_match_exactly(self):
        for release in ('', '   ', 'abcdef', self.release[:7], 'b' * 40):
            with self.subTest(release=release), patch.dict(os.environ, {'PAYMENT_RELEASE_SHA': release}):
                self.assertIs(billing.checkout_enabled(), False)
        for release in (None, 123, True, [], {}, self.release[:7], self.release + '0'):
            with self.subTest(record_release=release):
                self.assert_record_blocked(self.record | {'release_sha': release})

    def test_each_top_level_field_is_required(self):
        for field in ('release_sha', 'approved_by', 'checks'):
            record = copy.deepcopy(self.record)
            del record[field]
            with self.subTest(field=field):
                self.assert_record_blocked(record)

    def test_missing_or_malformed_json_blocks_checkout(self):
        for raw in ('', ' ', '{', '{"release_sha":', 'null', 'true', '0', '[]', '"text"'):
            with self.subTest(raw=raw), patch.dict(os.environ, {'PAYMENT_READINESS_EVIDENCE': raw}):
                self.assertIs(billing.checkout_enabled(), False)

    def test_excessively_nested_json_fails_closed_without_raising(self):
        raw = '[' * 20_000 + '0' + ']' * 20_000
        with patch.dict(os.environ, {'PAYMENT_READINESS_EVIDENCE': raw}):
            self.assertIs(billing.checkout_enabled(), False)

    def test_approving_operator_is_required(self):
        for operator in (None, '', ' \t\n', 42, True, [], {}):
            with self.subTest(operator=operator):
                self.assert_record_blocked(self.record | {'approved_by': operator})

    def test_checks_must_be_an_object(self):
        for checks in (None, '', True, [], 12):
            with self.subTest(checks=checks):
                self.assert_record_blocked(self.record | {'checks': checks})

    def test_every_readiness_check_is_mandatory(self):
        self.assertEqual(len(billing.READINESS_CHECKS), 12)
        for name in billing.READINESS_CHECKS:
            record = copy.deepcopy(self.record)
            del record['checks'][name]
            with self.subTest(check=name):
                self.assert_record_blocked(record)

    def test_check_items_and_passed_flags_are_strict(self):
        for name in billing.READINESS_CHECKS:
            for item in (None, True, [], 'passed', {},
                         {'passed': False, 'evidence': 'unit-fixture'},
                         {'passed': 1, 'evidence': 'unit-fixture'},
                         {'passed': 'true', 'evidence': 'unit-fixture'}):
                record = copy.deepcopy(self.record)
                record['checks'][name] = item
                with self.subTest(check=name, item=item):
                    self.assert_record_blocked(record)

    def test_every_check_requires_a_nonempty_evidence_reference(self):
        for name in billing.READINESS_CHECKS:
            for reference in (None, '', ' \t\n', 'short', True, 123, [], {}):
                record = copy.deepcopy(self.record)
                record['checks'][name]['evidence'] = reference
                with self.subTest(check=name, reference=reference):
                    self.assert_record_blocked(record)
            record = copy.deepcopy(self.record)
            del record['checks'][name]['evidence']
            with self.subTest(check=name, reference='missing'):
                self.assert_record_blocked(record)

    def test_invalid_owner_identities_fail_closed(self):
        invalid = ('', '0', '-1', '+42', '42.0', '1e3', '@operator', '²', '٤٢',
                   '00042', '042', str(2**52), '9' * 5_000)
        for owner in invalid:
            with self.subTest(owner=owner[:24]), patch.dict(os.environ, {'OWNER_TELEGRAM_ID': owner}):
                self.assertIs(billing.checkout_enabled(), False)

    def test_valid_owner_boundaries_are_recognized_by_bot(self):
        store = Store(':memory:')
        self.addCleanup(store.db.close)
        bot = Bot(store, FakeAPI(), 'LeagueHostBot')
        for owner in ('1', '42', str(2**52 - 1), ' 42 '):
            with self.subTest(owner=owner), patch.dict(os.environ, {'OWNER_TELEGRAM_ID': owner}):
                self.assertIs(billing.checkout_enabled(), True)
                self.assertTrue(bot.is_owner(int(owner)))

    def test_support_is_required(self):
        for contact in ('', ' ', '\t\r\n'):
            with self.subTest(contact=contact), patch.dict(os.environ, {'PAYSUPPORT_CONTACT': contact}):
                self.assertIs(billing.checkout_enabled(), False)
        del os.environ['PAYSUPPORT_CONTACT']
        self.assertIs(billing.checkout_enabled(), False)

    def test_explicit_activation_is_required_even_with_complete_fixture(self):
        for enabled in ('', 'false', '0', '1', 'yes', ' true '):
            with self.subTest(enabled=enabled), patch.dict(os.environ, {'PAYMENTS_ENABLED': enabled}):
                self.assertIs(billing.checkout_enabled(), False)
        del os.environ['PAYMENTS_ENABLED']
        self.assertIs(billing.checkout_enabled(), False)

    def blocked_configurations(self):
        yield 'disabled', {'PAYMENTS_ENABLED': 'false'}
        yield 'missing evidence', {'PAYMENT_READINESS_EVIDENCE': ''}
        yield 'malformed evidence', {'PAYMENT_READINESS_EVIDENCE': '{'}
        yield 'excessively nested evidence', {'PAYMENT_READINESS_EVIDENCE': '[' * 20_000 + '0' + ']' * 20_000}
        yield 'missing support', {'PAYSUPPORT_CONTACT': ''}
        yield 'invalid owner', {'OWNER_TELEGRAM_ID': '00042'}
        yield 'overlong owner', {'OWNER_TELEGRAM_ID': '9' * 5_000}
        yield 'release mismatch', {'RAILWAY_GIT_COMMIT_SHA': 'b' * 40}
        for name in billing.READINESS_CHECKS:
            record = copy.deepcopy(self.record)
            del record['checks'][name]
            yield name, {'PAYMENT_READINESS_EVIDENCE': json.dumps(record)}

    def test_complete_fixture_enables_both_plan_invoices_and_precheckout(self):
        for name, stars in (('pro', 100), ('club', 250)):
            with self.subTest(plan=name):
                store = Store(':memory:')
                self.addCleanup(store.db.close)
                api = FakeAPI(role='administrator')
                bot = Bot(store, api, 'LeagueHostBot')
                bot.handle({'message': {'text': '/upgrade ' + name + ' agree', 'from': {'id': 42},
                                        'chat': {'id': -123, 'type': 'group'}}})
                invoices = [data for method, data in api.calls if method == 'createInvoiceLink']
                self.assertEqual(len(invoices), 1)
                invoice = invoices[0]
                self.assertEqual(invoice['currency'], 'XTR')
                self.assertEqual(invoice['prices'][0]['amount'], stars)
                self.assertEqual(invoice['provider_token'], '')
                self.assertEqual(invoice['subscription_period'], 2_592_000)
                bot.handle({'pre_checkout_query': {'id': 'unit-precheckout', 'from': {'id': 42},
                                                   'invoice_payload': invoice['payload'],
                                                   'currency': 'XTR', 'total_amount': stars}})
                self.assertEqual(api.calls[-1][0], 'answerPreCheckoutQuery')
                self.assertIs(api.calls[-1][1]['ok'], True)

    def test_blocked_gate_prevents_invoice_and_order_creation(self):
        store = Store(':memory:')
        self.addCleanup(store.db.close)
        api = FakeAPI(role='administrator')
        bot = Bot(store, api, 'LeagueHostBot')
        for name, change in self.blocked_configurations():
            with self.subTest(configuration=name), patch.dict(os.environ, change):
                api.calls.clear()
                previous_orders = store.db.execute('SELECT COUNT(*) FROM billing_orders').fetchone()[0]
                bot.handle({'message': {'text': '/upgrade pro agree', 'from': {'id': 42},
                                        'chat': {'id': -123, 'type': 'group'}}})
                self.assertFalse(any(method == 'createInvoiceLink' for method, _ in api.calls))
                self.assertEqual(store.db.execute('SELECT COUNT(*) FROM billing_orders').fetchone()[0], previous_orders)
                self.assertIn('not active', api.calls[-1][1]['text'])

    def test_blocked_gate_explicitly_rejects_existing_invoice_precheckout(self):
        store = Store(':memory:')
        self.addCleanup(store.db.close)
        api = FakeAPI()
        bot = Bot(store, api, 'LeagueHostBot')
        payload = billing.create_order(store.db, -123, 42, 'pro', accepted_terms=True)
        query = {'id': 'unit-precheckout', 'invoice_payload': payload, 'currency': 'XTR',
                 'total_amount': 100, 'from': {'id': 42}}
        for name, change in self.blocked_configurations():
            with self.subTest(configuration=name), patch.dict(os.environ, change):
                bot.handle({'pre_checkout_query': query})
                self.assertEqual(api.calls[-1][0], 'answerPreCheckoutQuery')
                self.assertIs(api.calls[-1][1]['ok'], False)
                self.assertTrue(api.calls[-1][1]['error_message'])
        self.assertEqual(store.db.execute('SELECT COUNT(*) FROM billing_receipts').fetchone()[0], 0)

    def test_closing_gate_preserves_receipts_and_subscription_servicing(self):
        store = Store(':memory:')
        self.addCleanup(store.db.close)
        api = FakeAPI()
        bot = Bot(store, api, 'LeagueHostBot')
        payload = billing.create_order(store.db, -123, 42, 'pro', accepted_terms=True)
        payment = {'invoice_payload': payload, 'currency': 'XTR', 'total_amount': 100,
                   'is_recurring': True, 'is_first_recurring': True,
                   'telegram_payment_charge_id': 'unit-test-receipt',
                   'subscription_expiration_date': int(time.time()) + 3600}
        with patch.dict(os.environ, {'PAYMENT_READINESS_EVIDENCE': ''}):
            bot.handle({'message': {'from': {'id': 42}, 'chat': {'id': 42, 'type': 'private'},
                                    'successful_payment': payment}})
            self.assertEqual(billing.current_plan(store.db, -123)[0], 'pro')
            bot.handle({'message': {'text': '/cancel -123', 'from': {'id': 42},
                                    'chat': {'id': 42, 'type': 'private'}}})
            self.assertTrue(any(method == 'editUserStarSubscription' for method, _ in api.calls))
            self.assertEqual(billing.current_plan(store.db, -123)[0], 'pro')
            bot.handle({'message': {'text': '/refund unit-test-receipt confirm', 'from': {'id': 42},
                                    'chat': {'id': 42, 'type': 'private'}}})
            self.assertTrue(any(method == 'refundStarPayment' for method, _ in api.calls))
            self.assertEqual(billing.current_plan(store.db, -123)[0], 'free')
            self.assertEqual(store.db.execute('SELECT COUNT(*) FROM billing_receipts').fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()
