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
