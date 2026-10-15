import sqlite3
import time
import unittest
from unittest.mock import patch
import billing

class BillingTests(unittest.TestCase):
 def setUp(self):
  self.db=sqlite3.connect(':memory:')
  billing.create_tables(self.db)
  self.payload=billing.create_order(self.db,-123,42,'pro')
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
  club=billing.create_order(self.db,-123,77,'club')
  self.assertTrue(billing.record_payment(self.db,self.payment(invoice_payload=club,total_amount=250,telegram_payment_charge_id='two'),77))
  self.assertEqual(billing.current_plan(self.db,-123)[0],'club')
 def test_checkout_off_without_configuration(self):
  with patch.dict('os.environ',{'PAYMENTS_ENABLED':'false'}):
   self.assertFalse(billing.checkout_enabled())

if __name__=='__main__':unittest.main()
