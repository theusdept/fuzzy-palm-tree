import sqlite3
import time
import unittest
from unittest.mock import patch
import billing

class BillingTests(unittest.TestCase):
 def setUp(self):
  self.db=sqlite3.connect(':memory:')
  billing.create_tables(self.db)
  self.payload=billing.create_order(self.db,-123,42,'pro',accepted_terms=True)
 def tearDown(self):self.db.close()
 def query(self,**kw):
  d={'invoice_payload':self.payload,'currency':'XTR','total_amount':100,'from':{'id':42}}
  d.update(kw);return d
 def payment(self,**kw):
  d={'invoice_payload':self.payload,'currency':'XTR','total_amount':100,'is_recurring':True,'is_first_recurring':True,'subscription_expiration_date':int(time.time())+3600,'telegram_payment_charge_id':'one'}
  d.update(kw);return d
 def test_precheckout(self):
  self.assertFalse(billing.is_precheckout_valid(self.db,self.query(),False))
  self.assertTrue(billing.is_precheckout_valid(self.db,self.query(),True))
  self.assertFalse(billing.is_precheckout_valid(self.db,self.query(total_amount=300),True))
  self.assertFalse(billing.is_precheckout_valid(self.db,self.query(currency='USD'),True))
 def test_payment_and_replay(self):
  self.assertEqual(billing.current_plan(self.db,-123)[0],'free')
  self.assertFalse(billing.record_payment(self.db,self.payment(is_recurring=False),42))
  self.assertTrue(billing.record_payment(self.db,self.payment(),42))
  self.assertFalse(billing.record_payment(self.db,self.payment(),42))
  self.assertEqual(billing.current_plan(self.db,-123)[0],'pro')
 def test_refund(self):
  billing.record_payment(self.db,self.payment(),42)
  self.assertTrue(billing.record_refund(self.db,'one'))
  self.assertEqual(billing.current_plan(self.db,-123)[0],'free')
 def test_club_priority(self):
  billing.record_payment(self.db,self.payment(),42)
  club=billing.create_order(self.db,-123,77,'club',accepted_terms=True)
  self.assertTrue(billing.record_payment(self.db,self.payment(invoice_payload=club,total_amount=250,telegram_payment_charge_id='two'),77))
  self.assertEqual(billing.current_plan(self.db,-123)[0],'club')
 def test_checkout_off_without_configuration(self):
  with patch.dict('os.environ',{'PAYMENTS_ENABLED':'false'}):
   self.assertFalse(billing.checkout_enabled())

if __name__=='__main__':unittest.main()


class LifecycleTests(BillingTests):
 def test_requires_explicit_terms(self):
  with self.assertRaises(ValueError):billing.create_order(self.db,-123,42,'pro')
 def test_renewal_visible_after_initial_expiry(self):
  billing.record_payment(self.db,self.payment(),42)
  self.db.execute('UPDATE billing_receipts SET expires=1')
  billing.record_payment(self.db,self.payment(telegram_payment_charge_id='renewal',is_first_recurring=False),42)
  entries=billing.subscription_for_buyer(self.db,42)
  self.assertEqual(len(entries),1)
  self.assertEqual(entries[0][3],'one')
 def test_reconcile_refund(self):
  billing.record_payment(self.db,self.payment(),42)
  class Remote:
   def call(self,*a,**kw):return {'transactions':[{'id':'one','receiver':{'type':'user','user':{'id':42}}}]}
  self.assertEqual(billing.reconcile(self.db,Remote()),(1,0,1))
  self.assertEqual(billing.current_plan(self.db,-123)[0],'free')
 def test_cancellation_owner_scoped(self):
  from app import Bot,Store
  from test_app import API
  store=Store(':memory:');api=API()
  payload=billing.create_order(store.db,-123,42,'pro',accepted_terms=True)
  billing.record_payment(store.db,self.payment(invoice_payload=payload),42)
  bot=Bot(store,api,'LeagueHostBot')
  for user in (99,42):
   bot.handle({'message':{'text':'/cancel -123','from':{'id':user},'chat':{'id':user,'type':'private'}}})
  calls=[c for c in api.calls if c[0]=='editUserStarSubscription']
  self.assertEqual(len(calls),1);self.assertEqual(calls[0][1]['user_id'],42)
  self.assertEqual(billing.current_plan(store.db,-123)[0],'pro')
  store.db.close()
 def test_refund_requires_owner(self):
  from app import Bot,Store
  from test_app import API
  store=Store(':memory:');api=API()
  with patch.dict('os.environ',{'OWNER_TELEGRAM_ID':'42'}):
   Bot(store,api,'LeagueHostBot').handle({'message':{'text':'/refund one confirm','from':{'id':99},'chat':{'id':99,'type':'private'}}})
  self.assertFalse(any(c[0]=='refundStarPayment' for c in api.calls));store.db.close()
