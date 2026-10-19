import json
import billing
import os
import secrets
import signal
import sqlite3
import threading
import time
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer

QUESTIONS = [
 ('Which planet is known as the Red Planet?', ['Venus','Mars','Jupiter','Mercury'],1),
 ('How many sides does a hexagon have?', ['5','6','7','8'],1),
 ('What is the largest ocean?', ['Atlantic','Indian','Pacific','Arctic'],2),
 ('Which element has the symbol Au?', ['Silver','Gold','Argon','Copper'],1),
 ('What is 12 squared?', ['24','124','144','169'],2),
 ('Who wrote Pride and Prejudice?', ['Jane Austen','Mary Shelley','Emily Brontë','Virginia Woolf'],0),
 ('Which is a prime number?', ['21','27','29','33'],2),
 ('What is the capital of Japan?', ['Kyoto','Seoul','Tokyo','Osaka'],2),
 ('How many bones are in a typical adult human skeleton?', ['206','186','226','246'],0),
 ('Which gas do plants absorb during photosynthesis?', ['Oxygen','Carbon dioxide','Helium','Hydrogen'],1),
 ('What is the smallest prime number?', ['0','1','2','3'],2),
 ('Which instrument measures atmospheric pressure?', ['Thermometer','Barometer','Hygrometer','Anemometer'],1),
 ('Which continent contains the Sahara?', ['Asia','Africa','Europe','Australia'],1),
 ('How many degrees are in a triangle?', ['90','180','270','360'],1),
 ('Which animal is a mammal?', ['Shark','Dolphin','Trout','Octopus'],1),
 ('What is the chemical formula for water?', ['CO2','H2O','O2','NaCl'],1),
 ('Which language is primarily spoken in Brazil?', ['Spanish','Portuguese','French','Italian'],1),
 ('Which planet is closest to the Sun?', ['Mercury','Venus','Earth','Mars'],0),
 ('What is the square root of 81?', ['7','8','9','10'],2),
 ('Which organ pumps blood?', ['Liver','Lung','Heart','Kidney'],2),
 ('How many minutes are in three hours?', ['120','150','180','210'],2),
 ('Which city is home to the Colosseum?', ['Athens','Rome','Paris','Madrid'],1),
 ('Which is the largest planet in our solar system?', ['Saturn','Jupiter','Neptune','Earth'],1),
 ('What is the freezing point of water at standard pressure in Celsius?', ['0','10','32','100'],0),
 ('Which number is represented by the Roman numeral X?', ['5','10','50','100'],1),
 ('Which country gifted the Statue of Liberty to the United States?', ['Italy','France','Spain','Germany'],1),
 ('What is 15 percent of 200?', ['15','20','30','40'],2),
 ('Which is the longest side of a right triangle?', ['Radius','Hypotenuse','Diameter','Median'],1),
 ('Which ocean lies between Africa and Australia?', ['Pacific','Atlantic','Indian','Arctic'],2),
 ('Which scientist is associated with the theory of general relativity?', ['Newton','Einstein','Darwin','Pasteur'],1),
]
COMMANDS = {'start':'Welcome and setup','demo':'Try a private sample quiz','invite':'Add LeagueHost to your group','newleague':'Create a group league (admin)', 'round':'Open a 60-second quiz (admin)', 'standings':'Weekly group leaderboard','help':'Commands and rules','privacy':'Data and privacy','mydata':'Export your stored player data','delete_me':'Delete your player data','closeleague':'Close league (admin)','plans':'Current access and plans','upgrade':'Upgrade group league','paysupport':'Stars payment support','subscription':'Your Stars subscriptions','cancel':'Cancel renewal in private chat','terms':'Plan terms','support':'Contact support','myid':'Show your Telegram ID privately','addadmin':'Add bot administrator (owner)','removeadmin':'Remove bot administrator (owner)','admins':'List bot administrators (owner)','adminstatus':'Bot administrator status'}
HELP = 'LeagueHost 🏆\nTurn your group into a friendly weekly quiz league.\n\nAdd me to your group as an admin, then use /newleague. Group admins run /round; members tap one answer within 60 seconds. Correct answers earn 10 points. One answer per person. Scores reset on the weekly leaderboard each Monday (UTC).\n\n/standings — leaderboard\n/privacy — data information\n/mydata — export (private chat)\n/delete_me — delete (private chat)\n\nTry /demo for a private sample question or /invite for a group invitation link.\n\nFree: 5 rounds/week. See /plans for optional host plans. No cash prizes.'
PRIVACY = 'LeagueHost stores Telegram user IDs, display names, group IDs, quiz answers, timestamps and scores to run leagues. It does not read unrelated chat history. Group standings show player names and scores. Quiz records older than 90 days are removed. Payment receipts and buyer/group IDs are retained for subscription fulfillment, reconciliation and refunds; deleting quiz data does not cancel subscriptions or erase payment records. /mydata exports your records in private chat. /delete_me requests confirmation to erase them. Deleting records removes your scores and can permit replay of an active question. Telegram retains messages under its own policy. Contact the group admin for league concerns.'

TERMS = 'Plans apply to one group: Free 5 rounds/week; Pro 20 rounds/week at 100 Stars/30 days; Club unlimited rounds at 250 Stars/30 days. Paid plans renew automatically until canceled. All plans share 30 questions; Club repeats questions after exhausting the bank. Use /cancel in private chat to stop renewal; paid access lasts until expiry. Contact /paysupport for payment problems or refund requests. Telegram support cannot resolve purchases from this bot. Confirm agreement with /upgrade pro agree or /upgrade club agree in your group.'

class Store:
 def __init__(self,path):
  self.db=sqlite3.connect(path)
  self.db.execute('PRAGMA journal_mode=WAL')
  self.db.executescript('''CREATE TABLE IF NOT EXISTS leagues(chat INTEGER PRIMARY KEY, title TEXT, active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS rounds(id TEXT PRIMARY KEY, chat INTEGER, question INTEGER, expires INTEGER, week TEXT);
CREATE TABLE IF NOT EXISTS answers(round TEXT, user INTEGER, name TEXT, choice INTEGER, points INTEGER, created INTEGER, PRIMARY KEY(round,user));
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS actions(update_id INTEGER PRIMARY KEY, result TEXT);
CREATE TABLE IF NOT EXISTS bot_admins(user INTEGER PRIMARY KEY, added_by INTEGER NOT NULL, created INTEGER NOT NULL);''')
  billing.create_tables(self.db)
 def week(self): return time.strftime('%G-W%V',time.gmtime())
 def open_round(self,chat,update_id):
  old=self.db.execute('SELECT result FROM actions WHERE update_id=?',(update_id,)).fetchone()
  if old:return json.loads(old[0])
  if not self.db.execute('SELECT 1 FROM leagues WHERE chat=? AND active=1',(chat,)).fetchone():return {'error':'An admin must create a league with /newleague first.'}
  if self.db.execute('SELECT 1 FROM rounds WHERE chat=? AND expires>?',(chat,time.time())).fetchone():return {'error':'A round is already open. Wait 60 seconds.'}
  tier,_=billing.current_plan(self.db,chat)
  cap={'free':5,'pro':20,'club':None}[tier]
  count=self.db.execute('SELECT COUNT(*) FROM rounds WHERE chat=? AND week=?',(chat,self.week())).fetchone()[0]
  if cap is not None and count>=cap:return {'error':'Weekly round limit reached. Use /plans for upgrades.'}
  used={r[0] for r in self.db.execute('SELECT question FROM rounds WHERE chat=? AND week=?',(chat,self.week()))}
  options=[i for i in range(len(QUESTIONS)) if i not in used]
  if not options:
   if tier!='club':return {'error':'Question pool exhausted. Try next week or use /plans.'}
   options=list(range(len(QUESTIONS)))
  result={'id':secrets.token_hex(8),'question':secrets.choice(options)}
  with self.db:
   self.db.execute('INSERT INTO rounds VALUES(?,?,?,?,?)',(result['id'],chat,result['question'],int(time.time())+60,self.week()))
   self.db.execute('INSERT INTO actions VALUES(?,?)',(update_id,json.dumps(result)))
  return result
 def answer(self,rid,chat,user,name,choice):
  row=self.db.execute('SELECT question,expires FROM rounds WHERE id=? AND chat=?',(rid,chat)).fetchone()
  if not row or row[1]<time.time():return 'This round has ended.'
  if not 0<=choice<4:return 'Invalid answer.'
  points=10 if QUESTIONS[row[0]][2]==choice else 0
  with self.db:
   cur=self.db.execute('INSERT OR IGNORE INTO answers VALUES(?,?,?,?,?,?)',(rid,user,name[:64],choice,points,int(time.time())))
  return 'Answer saved. Check /standings after the round.' if cur.rowcount else 'You already answered this round.'
 def standings(self,chat):
  rows=self.db.execute('SELECT a.user,MAX(a.name),SUM(a.points) FROM answers a JOIN rounds r ON r.id=a.round WHERE r.chat=? AND r.week=? AND r.expires<=? GROUP BY a.user ORDER BY SUM(a.points) DESC,a.user LIMIT 20',(chat,self.week(),time.time())).fetchall()
  return '🏆 Weekly standings · '+self.week()+'\n\n'+ ('\n'.join(f'{i+1}. {r[1]} — {r[2]} pts' for i,r in enumerate(rows)) if rows else 'No finished rounds yet. Admins: /round')
 def cleanup(self):
  with self.db:
   self.db.execute('DELETE FROM answers WHERE created<?',(time.time()-90*86400,))
   self.db.execute('DELETE FROM rounds WHERE expires<?',(time.time()-90*86400,))
   self.db.execute('DELETE FROM actions WHERE update_id < COALESCE((SELECT MAX(update_id)-10000 FROM actions),0)')

class API:
 def __init__(self,token,test_environment=False):
  self.token=token
  self.base_url='https://api.telegram.org/bot'+token+('/test/' if test_environment else '/')
 def call(self,method,**data):
  req=urllib.request.Request(self.base_url+method,data=json.dumps(data).encode(),headers={'Content-Type':'application/json'})
  try:
   with urllib.request.urlopen(req,timeout=40) as response:result=json.load(response)
  except urllib.error.HTTPError as error:
   raise RuntimeError('Telegram HTTP '+str(error.code)) from None
  if not result.get('ok'):raise RuntimeError('Telegram rejected '+method)
  return result['result']

class Bot:
 def __init__(self,db,api,username):self.store=db;self.api=api;self.username=username
 def is_owner(self,uid):return str(uid)==os.getenv('OWNER_TELEGRAM_ID','').strip()
 def is_admin(self,uid):return self.is_owner(uid) or bool(self.store.db.execute('SELECT 1 FROM bot_admins WHERE user=?',(uid,)).fetchone())
 def send(self,chat,text,**kw):return self.api.call('sendMessage',chat_id=chat,text=text,**kw)
 def handle(self,u):
  cb=u.get('callback_query')
  if cb:
   m=cb.get('message',{});chat=m.get('chat',{}).get('id');uid=cb['from']['id'];data=cb.get('data','')
   if data=='delete_confirm' and m.get('chat',{}).get('type')=='private' and chat==uid:
    with self.store.db:self.store.db.execute('DELETE FROM answers WHERE user=?',(uid,))
    result='Your stored player records have been deleted.'
   elif data.startswith('d:') and m.get('chat',{}).get('type')=='private' and chat==uid:
    parts=data.split(':')
    if len(parts)==3 and parts[1].isdigit() and parts[2] in ('0','1','2','3') and 0<=int(parts[1])<len(QUESTIONS):
     question=QUESTIONS[int(parts[1])]
     result='Correct! 🏆' if int(parts[2])==question[2] else 'Not quite. Correct answer: '+question[1][question[2]]
    else:result='Invalid sample question.'
   else:
    parts=data.split(':')
    result=self.store.answer(parts[1],chat,uid,cb['from'].get('first_name','Player'),int(parts[2])) if len(parts)==3 and parts[0]=='a' and parts[2] in ['0','1','2','3'] else 'Invalid action.'
   self.api.call('answerCallbackQuery',callback_query_id=cb['id'],text=result,show_alert=True);return
  pre=u.get('pre_checkout_query')
  if pre:
   ok=billing.is_precheckout_valid(self.store.db,pre,billing.checkout_enabled())
   args={'pre_checkout_query_id':pre['id'],'ok':ok}
   if not ok:args['error_message']='Checkout unavailable; request a fresh group upgrade link.'
   self.api.call('answerPreCheckoutQuery',**args);return
  m=u.get('message',{});text=m.get('text','');sender=m.get('from',{})
  if m.get('refunded_payment'):
   refund=m['refunded_payment'];receipt=billing.receipt_for_refund(self.store.db,refund.get('telegram_payment_charge_id'))
   if receipt and receipt[0]==sender.get('id') and refund.get('currency')=='XTR' and refund.get('total_amount')==receipt[3]:billing.record_refund(self.store.db,refund['telegram_payment_charge_id'])
   return
  if m.get('successful_payment'):
   pay=m['successful_payment'];buyer=m.get('from',{}).get('id')
   if buyer and billing.record_payment(self.store.db,pay,buyer):
    self.send(m['chat']['id'],'Stars payment confirmed. Group plan activated. Use /subscription for details.')
   return
  if not text.startswith('/') or sender.get('is_bot') or m.get('sender_chat'):return
  chat=m['chat']['id'];private=m['chat']['type']=='private';uid=sender['id'];first=text.split()[0];cmd=first.split('@')[0][1:]
  if '@' in first and first.split('@')[1].lower()!=self.username.lower():return
  if cmd=='myid':
   if not private:self.send(chat,'Send /myid in my private chat.');return
   self.send(chat,'Your Telegram user ID: '+str(uid));return
  if cmd in ('addadmin','removeadmin','admins'):
   if not private or not self.is_owner(uid):self.send(chat,'Only the configured bot owner can manage bot administrators in private chat.');return
   if cmd=='admins':
    ids=[str(r[0]) for r in self.store.db.execute('SELECT user FROM bot_admins ORDER BY user')]
    self.send(chat,'Owner: '+str(uid)+'\nBot administrators: '+(', '.join(ids) or 'None'));return
   args=text.split()[1:]
   if len(args)!=1 or not args[0].isascii() or not args[0].isdigit() or not 0<int(args[0])<2**52:
    self.send(chat,'Use /'+cmd+' NUMERIC_TELEGRAM_USER_ID. Ask that person to send /myid here first.');return
   target=int(args[0])
   if self.is_owner(target):self.send(chat,'The owner is already an administrator and cannot be removed here.');return
   with self.store.db:
    if cmd=='addadmin':self.store.db.execute('INSERT OR IGNORE INTO bot_admins VALUES(?,?,?)',(target,uid,int(time.time())))
    else:self.store.db.execute('DELETE FROM bot_admins WHERE user=?',(target,))
   self.send(chat,('Added' if cmd=='addadmin' else 'Removed')+' bot administrator '+str(target)+'. Bot admins can view /adminstatus and run /reconcile; refunds and admin changes remain owner-only. Telegram group roles are unchanged.');return
  if cmd=='adminstatus':
   if not private or not self.is_admin(uid):self.send(chat,'Bot administrators only, in private chat.');return
   active=self.store.db.execute('SELECT COUNT(*) FROM leagues WHERE active=1').fetchone()[0]
   self.send(chat,'Active leagues: '+str(active)+'\nPaid checkout: '+('enabled' if billing.checkout_enabled() else 'disabled'));return
  if cmd in ('start','help'):self.send(chat,HELP);return
  if cmd=='terms':self.send(chat,TERMS);return
  if cmd=='privacy':self.send(chat,PRIVACY);return
  if cmd=='plans':
   tier,expiry=billing.current_plan(self.store.db,chat)
   self.send(chat,'🏆 LeagueHost\nFree: 5 group rounds/week, 0 Stars\nPro: 20 group rounds/week, 100 Stars per 30 days\nClub: unlimited group rounds/week, 250 Stars per 30 days\n\nPaid plans renew automatically every 30 days. All tiers use the 30-question bank and weekly standings. Current tier: '+tier.title()+'\nGroup admins use /upgrade.')
   return
  if cmd in ('paysupport','support'):
   self.send(chat,'Telegram Stars support: '+(os.getenv('PAYSUPPORT_CONTACT','Not configured') or 'Not configured')+'. To request cancellation or a refund, contact support with your group ID and payment date. Never send tokens.')
   return
  if cmd=='subscription':
   if not private:self.send(chat,'Use /subscription in private chat.');return
   entries=billing.subscription_for_buyer(self.store.db,uid)
   self.send(chat,'Active purchases: '+('; '.join(str(r[0])+' '+r[1]+' ends '+time.strftime('%Y-%m-%d UTC',time.gmtime(r[2])) for r in entries) if entries else 'None')+'. To stop renewal send /cancel GROUP_ID here.')
   return
  if cmd=='upgrade':
   if private:self.send(chat,'Send /upgrade in a group where you are an admin.');return
   if self.api.call('getChatMember',chat_id=chat,user_id=uid).get('status') not in ('administrator','creator'):self.send(chat,'Only group admins can upgrade.');return
   if not billing.checkout_enabled():self.send(chat,'Paid checkout is not active yet. Free play remains available.');return
   args=text.split()[1:]
   if len(args)!=2 or args[0] not in billing.PLANS or args[1].lower()!='agree':self.send(chat,TERMS);return
   if billing.current_plan(self.store.db,chat)[0]!='free':self.send(chat,'This group already has a paid plan. Cancel renewal and wait for expiry before changing plans.');return
   name=args[0];plan=billing.PLANS[name]
   payload=billing.create_order(self.store.db,chat,uid,name,accepted_terms=True)
   url=self.api.call('createInvoiceLink',title=plan['name'],description='Recurring 30-day group quiz subscription. Shared 30-question bank.',payload=payload,provider_token='',currency='XTR',prices=[{'label':plan['name'],'amount':plan['stars']}],subscription_period=billing.PERIOD_SECONDS)
   self.send(chat,'Group '+str(chat)+' — '+plan['name']+'. Renews every 30 days. Only the requesting admin can pay. Use /cancel in private chat to stop renewal.',reply_markup={'inline_keyboard':[[{'text':str(plan['stars'])+' Stars / 30 days','url':url}]]});return
  if cmd=='cancel':
   if not private:self.send(chat,'Send /cancel GROUP_ID in my private chat.');return
   args=text.split()[1:]
   entries=billing.subscription_for_buyer(self.store.db,uid)
   matches=[r for r in entries if len(args)==1 and str(r[0])==args[0]]
   if not matches:self.send(chat,'No matching active purchase. Use /subscription to find your group ID.');return
   for r in matches:self.api.call('editUserStarSubscription',user_id=uid,telegram_payment_charge_id=r[3],is_canceled=True)
   self.send(chat,'Renewal canceled. Paid access remains until the end of the paid period.');return
  if cmd in ('refund','reconcile'):
   if not private or not (self.is_owner(uid) if cmd=='refund' else self.is_admin(uid)):self.send(chat,'Insufficient bot administrator permissions. Use private chat.');return
   args=text.split()[1:]
   if cmd=='reconcile':
    if len(args)>1 or (args and not args[0].isdigit()):self.send(chat,'Use /reconcile OFFSET (default 0).');return
    offset=int(args[0]) if args else 0
    count,missing,refunds=billing.reconcile(self.store.db,self.api,offset)
    self.send(chat,f'Audited {count} transactions from offset {offset}. Missing receipts: {missing}; refunds applied: {refunds}. '+(f'Continue: /reconcile {offset+count}' if count==100 else 'End of current transaction list.'));return
   if len(args)!=2 or args[1]!='confirm':self.send(chat,'Use /refund CHARGE_ID confirm after reviewing the customer request.');return
   receipt=billing.receipt_for_refund(self.store.db,args[0])
   if not receipt:self.send(chat,'Receipt not found.');return
   if receipt[4]:self.send(chat,'Already refunded.');return
   self.api.call('refundStarPayment',user_id=receipt[0],telegram_payment_charge_id=args[0])
   billing.record_refund(self.store.db,args[0]);self.send(chat,'Refund confirmed; access from that receipt removed.');return
  if cmd=='invite':
   self.send(chat,'Add LeagueHost to your group:\nhttps://t.me/'+self.username+'?startgroup=league\n\nAfter adding me as an admin, use /newleague, then /round to play.');return
  if cmd=='demo':
   if not private:self.send(chat,'Open my private chat and send /demo to try a question.');return
   idx=secrets.randbelow(len(QUESTIONS));q=QUESTIONS[idx]
   self.send(chat,'🏆 Sample quiz — no account or payment required\n\n'+q[0]+'\n\nTry an answer below, then send /invite to start a group league.',reply_markup={'inline_keyboard':[[{'text':v,'callback_data':f'd:{idx}:{i}'}] for i,v in enumerate(q[1])]});return
  if cmd in ('mydata','delete_me'):
   if not private:self.send(chat,'For your privacy, send /'+cmd+' in a private chat with me.');return
   if cmd=='delete_me':self.send(chat,'Delete all your saved answers and scores? This cannot be undone.',reply_markup={'inline_keyboard':[[{'text':'Delete my player data','callback_data':'delete_confirm'}]]});return
   rows=self.store.db.execute('SELECT round,name,choice,points,created FROM answers WHERE user=?',(uid,)).fetchall()
   payments=self.store.db.execute('SELECT charge_id,chat,plan,stars,paid_at,expires,refunded FROM billing_receipts WHERE buyer=?',(uid,)).fetchall()
   content=json.dumps({'user_id':uid,'answers':rows,'payments':payments},ensure_ascii=False)
   for offset in range(0,len(content),3500):self.send(chat,content[offset:offset+3500])
   return
  if cmd not in ('newleague','round','standings','closeleague'):self.send(chat,'Use /help to see the commands.');return
  if private:self.send(chat,'Use this command in your Telegram group. Add me as a group admin first.');return
  if cmd=='standings':self.send(chat,self.store.standings(chat));return
  status=self.api.call('getChatMember',chat_id=chat,user_id=uid).get('status')
  if status not in ('administrator','creator'):self.send(chat,'Only group admins can manage the league.');return
  if cmd=='newleague':
   with self.store.db:self.store.db.execute('INSERT INTO leagues VALUES(?,?,1) ON CONFLICT(chat) DO UPDATE SET active=1,title=excluded.title',(chat,m['chat'].get('title','League')))
   self.send(chat,'🏆 League ready! An admin can use /round to open a question. Each round lasts 60 seconds. Correct answers earn 10 points.');return
  if cmd=='closeleague':
   with self.store.db:
    self.store.db.execute('UPDATE leagues SET active=0 WHERE chat=?',(chat,))
    self.store.db.execute('UPDATE rounds SET expires=MIN(expires,?) WHERE chat=?',(int(time.time())-1,chat))
   self.send(chat,'League closed. Existing standings remain available. /newleague reopens it.');return
  result=self.store.open_round(chat,u['update_id'])
  if 'error' in result:self.send(chat,result['error']);return
  q=QUESTIONS[result['question']]
  self.send(chat,'⚡ 60-second round\n\n'+q[0]+'\n\nChoose once. 10 points for a correct answer.',reply_markup={'inline_keyboard':[[{'text':v,'callback_data':f"a:{result['id']}:{i}"}] for i,v in enumerate(q[1])]})

STATUS={'configured':False,'connected':False,'last_poll':0}
class Health(BaseHTTPRequestHandler):
 def do_GET(self):
  if self.path not in ('/','/health','/ready'):self.send_error(404);return
  ready=STATUS['connected'] and time.time()-STATUS['last_poll']<90
  self.send_response(200 if self.path!='/ready' or ready else 503);self.send_header('Content-Type','application/json');self.end_headers()
  self.wfile.write(json.dumps({'service':'LeagueHost','configured':STATUS['configured'],'telegram_ready':ready}).encode())
 def log_message(self,*args):pass

def runtime_configuration():
 mode=os.getenv('TELEGRAM_TEST_ENVIRONMENT','false').strip().lower()
 if mode not in ('true','false'):raise ValueError('TELEGRAM_TEST_ENVIRONMENT must be true or false')
 if mode=='false':return os.getenv('BOT_TOKEN',''),os.getenv('DB_PATH','/data/leaguehost.db'),False
 if os.getenv('RAILWAY_ENVIRONMENT_NAME','').lower()=='production':
  raise ValueError('Telegram test mode requires a separate staging environment')
 token=os.getenv('TEST_BOT_TOKEN','').strip();path=os.getenv('TEST_DB_PATH','').strip()
 if not token or token==os.getenv('BOT_TOKEN'):
  raise ValueError('Set a separate TEST_BOT_TOKEN from the Telegram test server')
 if not path or os.path.realpath(path)==os.path.realpath(os.getenv('DB_PATH','/data/leaguehost.db')):
  raise ValueError('Set a separate TEST_DB_PATH on an isolated staging volume')
 return token,path,True

def main():
 token,path,test_environment=runtime_configuration()
 threading.Thread(target=HTTPServer(('0.0.0.0',int(os.getenv('PORT','8080'))),Health).serve_forever,daemon=True).start()
 stop=threading.Event()
 for s in (signal.SIGTERM,signal.SIGINT):signal.signal(s,lambda *_:stop.set())
 STATUS['configured']=bool(token)
 if not token:
  print('Setup required: add BOT_TOKEN in Railway Variables.',flush=True)
  stop.wait();return
 os.makedirs(os.path.dirname(os.path.abspath(path)),exist_ok=True)
 store=Store(path);api=API(token,test_environment=test_environment)
 while not stop.is_set():
  try:
   me=api.call('getMe');wh=api.call('getWebhookInfo')
   if wh.get('url'):raise RuntimeError('Existing webhook detected; remove it only after confirming this bot belongs to LeagueHost')
   api.call('setMyCommands',commands=[{'command':k,'description':v} for k,v in COMMANDS.items()])
   api.call('setMyDescription',description='Host friendly quiz leagues in your Telegram group. Play quick rounds, earn points, and climb the weekly leaderboard. Add LeagueHost to a group to start.')
   api.call('setMyShortDescription',short_description='Your group. Your league. Quick quizzes and weekly bragging rights.')
   bot=Bot(store,api,me['username']);STATUS['connected']=True;print('Telegram connected: @'+me['username'],flush=True);break
  except Exception as e:print('Setup retry: '+type(e).__name__+': '+str(e),flush=True);stop.wait(15)
 while not stop.is_set():
  try:
   row=store.db.execute("SELECT value FROM meta WHERE key='offset'").fetchone();offset=int(row[0]) if row else 0
   updates=api.call('getUpdates',offset=offset,timeout=25,allowed_updates=['message','callback_query','pre_checkout_query'])
   STATUS['last_poll']=time.time();store.cleanup()
   for u in updates:
    if stop.is_set():break
    try:bot.handle(u)
    except RuntimeError as e:
     # 400/403 are permanent delivery failures; transient errors retry without advancing.
     if str(e) not in ('Telegram HTTP 400','Telegram HTTP 403'):raise
     print('Skipped undeliverable update '+str(u['update_id']),flush=True)
    with store.db:store.db.execute("INSERT OR REPLACE INTO meta VALUES('offset',?)",(str(u['update_id']+1),))
  except Exception as e:print('Poll retry: '+type(e).__name__,flush=True);stop.wait(5)
 store.db.close()
if __name__=='__main__':main()

