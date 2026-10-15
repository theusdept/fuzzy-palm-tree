"""Telegram Stars subscription ledger and group entitlements for LeagueHost."""
import os
import secrets
import time

PERIOD_SECONDS = 2_592_000
PLANS = {
    'pro': {'name': 'LeagueHost Pro', 'stars': 100, 'rank': 1},
    'club': {'name': 'LeagueHost Club', 'stars': 250, 'rank': 2},
}


def checkout_enabled():
    return (
        os.getenv('PAYMENTS_ENABLED', '').lower() == 'true'
        and os.getenv('PAYSUPPORT_CONTACT', '').strip() != ''
        and os.getenv('OWNER_TELEGRAM_ID', '').strip().isdigit()
    )


def create_tables(db):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS billing_orders (
            id TEXT PRIMARY KEY,
            chat INTEGER NOT NULL,
            buyer INTEGER NOT NULL,
            plan TEXT NOT NULL,
            stars INTEGER NOT NULL,
            created INTEGER NOT NULL,
            accepted_terms INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS billing_receipts (
            charge_id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            chat INTEGER NOT NULL,
            buyer INTEGER NOT NULL,
            plan TEXT NOT NULL,
            stars INTEGER NOT NULL,
            paid_at INTEGER NOT NULL,
            expires INTEGER NOT NULL,
            first_recurring INTEGER NOT NULL DEFAULT 0,
            refunded INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_billing_active ON billing_receipts(chat, expires, refunded);
        CREATE INDEX IF NOT EXISTS idx_billing_buyer ON billing_receipts(buyer, paid_at);
    ''')


def current_plan(db, chat, now=None):
    now = int(time.time()) if now is None else int(now)
    row = db.execute('''
        SELECT plan, MAX(expires) FROM billing_receipts
        WHERE chat=? AND expires>? AND refunded=0
        GROUP BY plan
        ORDER BY CASE plan WHEN 'club' THEN 2 WHEN 'pro' THEN 1 ELSE 0 END DESC LIMIT 1
    ''', (chat, now)).fetchone()
    return (row[0], row[1]) if row else ('free', None)


def create_order(db, chat, buyer, plan):
    if plan not in PLANS or int(chat) >= 0 or int(buyer) <= 0:
        raise ValueError('Invalid plan or group')
    order_id = secrets.token_urlsafe(18)
    with db:
        db.execute('INSERT INTO billing_orders VALUES(?,?,?,?,?,?,1)',
                   (order_id, int(chat), int(buyer), plan, PLANS[plan]['stars'], int(time.time())))
    return 'lh1:' + order_id


def lookup_order(db, payload):
    if not isinstance(payload, str) or not payload.startswith('lh1:'):
        return None
    order_id = payload[4:]
    if len(order_id) > 60 or not order_id:
        return None
    return db.execute('SELECT id,chat,buyer,plan,stars,created,accepted_terms FROM billing_orders WHERE id=?',
                      (order_id,)).fetchone()


def is_precheckout_valid(db, query, enabled, now=None):
    if not enabled:
        return False
    order = lookup_order(db, query.get('invoice_payload'))
    if not order or not order[6] or order[3] not in PLANS:
        return False
    if (query.get('currency') != 'XTR' or query.get('total_amount') != order[4]
            or query.get('from', {}).get('id') != order[2]):
        return False
    # Initial invoices have a 24-hour payment window; paid recurring orders remain valid.
    prior = db.execute('SELECT 1 FROM billing_receipts WHERE order_id=? LIMIT 1', (order[0],)).fetchone()
    now = int(time.time()) if now is None else int(now)
    return bool(prior) or (now - order[5] <= 86_400)


def record_payment(db, payment, buyer, now=None):
    order = lookup_order(db, payment.get('invoice_payload'))
    if not order or order[2] != buyer or order[3] not in PLANS:
        return False
    if payment.get('currency') != 'XTR' or payment.get('total_amount') != order[4]:
        return False
    # Do not grant entitlements for an unmatched one-off payment or a missing charge ID.
    if payment.get('is_recurring') is not True:
        return False
    charge_id = payment.get('telegram_payment_charge_id')
    if not isinstance(charge_id, str) or not charge_id:
        return False
    now = int(time.time()) if now is None else int(now)
    expires = payment.get('subscription_expiration_date')
    if not isinstance(expires, int):
        # Telegram documents this field as optional; preserve one paid 30-day period.
        expires = now + PERIOD_SECONDS
    if expires <= now:
        return False
    with db:
        inserted = db.execute('''INSERT OR IGNORE INTO billing_receipts
            (charge_id,order_id,chat,buyer,plan,stars,paid_at,expires,first_recurring,refunded)
            VALUES(?,?,?,?,?,?,?,?,?,0)''',
            (charge_id, order[0], order[1], buyer, order[3], order[4], now, expires,
             int(bool(payment.get('is_first_recurring'))))).rowcount
    return bool(inserted)


def record_refund(db, charge_id):
    if not isinstance(charge_id, str) or not charge_id:
        return False
    with db:
        changed = db.execute('UPDATE billing_receipts SET refunded=1 WHERE charge_id=? AND refunded=0',
                             (charge_id,)).rowcount
    return bool(changed)


def subscription_for_buyer(db, buyer):
    return db.execute('''SELECT r.chat,r.plan,r.expires,r.charge_id FROM billing_receipts r
        WHERE r.buyer=? AND r.first_recurring=1 AND r.refunded=0 AND r.expires>?
        ORDER BY r.paid_at DESC''', (buyer, int(time.time()))).fetchall()


def receipt_for_refund(db, charge_id):
    return db.execute('SELECT buyer,chat,plan,stars,refunded FROM billing_receipts WHERE charge_id=?',
                      (charge_id,)).fetchone()


def gross_stars(db):
    row = db.execute('SELECT COUNT(*),COALESCE(SUM(stars),0),COALESCE(SUM(CASE WHEN refunded=0 THEN stars ELSE 0 END),0) FROM billing_receipts').fetchone()
    return row
