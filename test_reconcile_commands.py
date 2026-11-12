"""Reconciliation command regressions with fake API responses and isolated storage."""
import os
import unittest
from unittest.mock import patch

from app import Bot, Store
from test_app import API as FakeAPI


class ReconcileAPI(FakeAPI):
    def __init__(self):
        super().__init__()
        self.transactions = []

    def call(self, method, **data):
        result = super().call(method, **data)
        if method == 'getStarTransactions':
            return {'transactions': self.transactions}
        return result


class ReconcileCommandTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {
            'OWNER_TELEGRAM_ID': '42', 'PAYMENTS_ENABLED': 'false',
        }, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        self.store = Store(':memory:')
        self.addCleanup(self.store.db.close)
        self.store.db.execute('INSERT INTO bot_admins VALUES(99,42,1)')
        self.api = ReconcileAPI()
        self.bot = Bot(self.store, self.api, 'LeagueHostBot')

    def command(self, text, user=42, private=True):
        self.bot.handle({'message': {
            'text': text, 'from': {'id': user},
            'chat': {'id': user if private else -123,
                     'type': 'private' if private else 'group'},
        }})

    def test_invalid_offsets_reject_without_api_or_ledger_changes(self):
        invalid = ('²', '٤٢', '１２', '-1', '+1', '1.0', '1e3', 'abc',
                   '0 extra', '2147483648', '9999999999', '9' * 5_000,
                   '0' * 5_000)
        for user in (42, 99):
            for offset in invalid:
                with self.subTest(user=user, offset=offset[:24]):
                    self.api.calls.clear()
                    before = self.store.db.total_changes
                    self.command('/reconcile ' + offset, user)
                    self.assertEqual([method for method, _ in self.api.calls], ['sendMessage'])
                    self.assertIn('Use /reconcile', self.api.calls[-1][1]['text'])
                    self.assertEqual(self.store.db.total_changes, before)
                    self.command('/adminstatus', user)
                    self.assertIn('Paid checkout: disabled', self.api.calls[-1][1]['text'])

    def test_valid_offsets_work_for_owner_and_admin_with_checkout_disabled(self):
        for user in (42, 99):
            for argument, expected in (('', 0), ('0', 0), ('100', 100),
                                       ('000100', 100), ('2147483647', 2147483647)):
                with self.subTest(user=user, argument=argument):
                    self.api.calls.clear()
                    self.command('/reconcile ' + argument, user)
                    self.assertEqual(self.api.calls[0], (
                        'getStarTransactions', {'offset': expected, 'limit': 100}))
                    self.assertIn('Audited 0 transactions', self.api.calls[-1][1]['text'])

    def test_reconciliation_remains_admin_only_in_private(self):
        for user, private in ((100, True), (42, False), (99, False)):
            with self.subTest(user=user, private=private):
                self.api.calls.clear()
                self.command('/reconcile 0', user, private)
                self.assertEqual([method for method, _ in self.api.calls], ['sendMessage'])
                self.assertIn('Insufficient', self.api.calls[-1][1]['text'])

    def test_full_page_preserves_continuation_offset(self):
        self.api.transactions = [{'id': 'synthetic-' + str(i)} for i in range(100)]
        self.command('/reconcile 100')
        self.assertIn('Continue: /reconcile 200', self.api.calls[-1][1]['text'])


if __name__ == '__main__':
    unittest.main()
