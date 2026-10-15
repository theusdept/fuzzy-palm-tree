import unittest
import time
from app import Store, Bot, QUESTIONS
class API:
 def __init__(self,role='member'):self.role=role;self.calls=[]
 def call(self,method,**data):
  self.calls.append((method,data))
  return {'status':self.role} if method=='getChatMember' else True
class Tests(unittest.TestCase):
 def setUp(self):
  self.s=Store(':memory:');self.s.db.execute("INSERT INTO leagues VALUES(-1,'Test',1)")
 def tearDown(self):self.s.db.close()
 def test_replay_round(self):
  r=self.s.open_round(-1,1);self.assertEqual(r,self.s.open_round(-1,1));self.assertIn('error',self.s.open_round(-1,2))
 def test_scoring_and_duplicates(self):
  r=self.s.open_round(-1,1);answer=QUESTIONS[r['question']][2]
  self.s.answer(r['id'],-1,42,'A',answer);self.s.answer(r['id'],-1,42,'A',answer)
  self.assertEqual(self.s.db.execute('SELECT SUM(points) FROM answers').fetchone()[0],10)
 def test_chat_scope(self):
  r=self.s.open_round(-1,1);self.s.answer(r['id'],-2,42,'A',0)
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM answers').fetchone()[0],0)
 def test_expiry(self):
  r=self.s.open_round(-1,1);self.s.db.execute('UPDATE rounds SET expires=0')
  self.assertIn('ended',self.s.answer(r['id'],-1,42,'A',0))
 def test_hidden_live_scores(self):
  r=self.s.open_round(-1,1);self.s.answer(r['id'],-1,42,'A',QUESTIONS[r['question']][2])
  self.assertNotIn('10 pts',self.s.standings(-1));self.s.db.execute('UPDATE rounds SET expires=0');self.assertIn('10 pts',self.s.standings(-1))
 def test_non_admin(self):
  api=API();Bot(self.s,api,'LeagueHostBot').handle({'update_id':2,'message':{'text':'/round','chat':{'id':-1,'type':'group'},'from':{'id':42}}})
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM rounds').fetchone()[0],0)
 def test_private_demo(self):
  api=API();Bot(self.s,api,'LeagueHostBot').handle({'update_id':10,'message':{'text':'/demo','chat':{'id':42,'type':'private'},'from':{'id':42}}})
  self.assertEqual(api.calls[0][0],'sendMessage')
  self.assertIn('Sample quiz',api.calls[0][1]['text'])
  data=api.calls[0][1]['reply_markup']['inline_keyboard'][0][0]['callback_data']
  self.assertTrue(data.startswith('d:'))
  Bot(self.s,api,'LeagueHostBot').handle({'callback_query':{'id':'cb1','from':{'id':42},'message':{'chat':{'id':42,'type':'private'}},'data':data}})
  self.assertEqual(api.calls[-1][0],'answerCallbackQuery')
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM answers').fetchone()[0],0)
 def test_demo_not_accepted_in_group(self):
  api=API();Bot(self.s,api,'LeagueHostBot').handle({'callback_query':{'id':'cb2','from':{'id':42},'message':{'chat':{'id':-1,'type':'group'}},'data':'d:0:0'}})
  self.assertEqual(api.calls[-1][1]['text'],'Invalid action.')
 def test_invite_link(self):
  api=API();Bot(self.s,api,'LeagueHostBot').handle({'update_id':11,'message':{'text':'/invite','chat':{'id':42,'type':'private'},'from':{'id':42}}})
  self.assertIn('https://t.me/LeagueHostBot?startgroup=league',api.calls[-1][1]['text'])
 def test_other_bot(self):
  api=API();Bot(self.s,api,'LeagueHostBot').handle({'update_id':2,'message':{'text':'/round@OtherBot','chat':{'id':-1,'type':'group'},'from':{'id':42}}});self.assertEqual(api.calls,[])
 def test_closed_league(self):
  self.s.db.execute('UPDATE leagues SET active=0');self.assertIn('error',self.s.open_round(-1,1))
if __name__=='__main__':unittest.main()


class AdminTests(unittest.TestCase):
 def setUp(self):
  from unittest.mock import patch
  self.env=patch.dict('os.environ',{'OWNER_TELEGRAM_ID':'42'});self.env.start()
  self.s=Store(':memory:');self.api=API();self.bot=Bot(self.s,self.api,'LeagueHostBot')
 def tearDown(self):self.s.db.close();self.env.stop()
 def command(self,user,text,private=True):
  self.bot.handle({'message':{'text':text,'from':{'id':user},'chat':{'id':user if private else -1,'type':'private' if private else 'group'}}})
 def test_owner_add_remove(self):
  self.command(42,'/addadmin 99');self.assertTrue(self.bot.is_admin(99))
  self.command(42,'/addadmin 99');self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM bot_admins').fetchone()[0],1)
  self.command(42,'/removeadmin 99');self.assertFalse(self.bot.is_admin(99))
 def test_no_self_promotion_or_delegated_promotion(self):
  self.command(99,'/addadmin 99');self.assertFalse(self.bot.is_admin(99))
  self.command(42,'/addadmin 99');self.command(99,'/addadmin 100');self.assertFalse(self.bot.is_admin(100))
 def test_owner_only_in_private(self):
  self.command(42,'/addadmin 99',False);self.assertFalse(self.bot.is_admin(99))
 def test_invalid_ids(self):
  for value in ('@someone','-1','0','999999999999999999999999','42 extra'):
   self.command(42,'/addadmin '+value)
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM bot_admins').fetchone()[0],0)
 def test_admin_cannot_refund(self):
  self.command(42,'/addadmin 99');self.command(99,'/refund charge confirm')
  self.assertFalse(any(c[0]=='refundStarPayment' for c in self.api.calls))
 def test_owner_cannot_remove_self(self):
  self.command(42,'/removeadmin 42');self.assertTrue(self.bot.is_owner(42))
 def test_unconfigured_owner_cannot_be_claimed(self):
  from unittest.mock import patch
  with patch.dict('os.environ',{'OWNER_TELEGRAM_ID':''}):
   self.command(42,'/addadmin 42');self.assertFalse(self.bot.is_admin(42))
