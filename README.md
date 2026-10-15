# LeagueHost
Telegram group quiz leagues. Python standard library; SQLite on a persistent Railway volume; one polling replica.

## Deployment
Python 3.13. Set BOT_TOKEN securely, DB_PATH=/data/leaguehost.db, PORT=8080. Mount a persistent volume at /data. Docker copies app.py and billing.py. Run python app.py. /health checks process health; /ready requires recent successful Telegram polling. Never log or commit tokens. Keep one replica and enable volume backups.

## Use
Open @LeagueHostBot and /demo. /invite provides a group invite. Add the bot as a group admin with minimal permissions. Group admins use /newleague and /round. Players answer once within 60 seconds; correct answers earn 10 points. /standings shows completed-round scores for the UTC week. /closeleague ends play. Quiz records expire after 90 days; /mydata and confirmed /delete_me operate privately.

## Plans
Free: 5 rounds/week. Pro: 20 rounds/week at 100 Stars per 30 days. Club: unlimited rounds at 250 Stars per 30 days. Paid plans auto-renew. All tiers use the same 30-question bank; Club repeats questions after exhausting it. No cash prizes or wagering.

## Payment activation
Checkout is OFF by default. Configure OWNER_TELEGRAM_ID (verified numeric operator ID), PAYSUPPORT_CONTACT (actual monitored support contact), then PAYMENTS_ENABLED=true only after payment integration validation and approval of the customer-facing terms. Do not infer an owner's Telegram identity from a group admin or GitHub account. No payment-provider token is needed for Stars.

Group admins read /terms and use /upgrade pro agree or /upgrade club agree. Invoices bind the group, buyer, amount, currency and accepted terms. Only successful_payment grants access. Receipt IDs are unique; repeated updates do not grant duplicate access. Existing paid groups cannot request a second upgrade until expiry. New invoice links expire after 24 hours.

Private /subscription lists purchases; /cancel GROUP_ID stops renewals through Telegram, preserving paid access until expiry. /paysupport and /support show the configured support contact. Payment receipts remain for fulfillment and refund reconciliation; deleting quiz data does not delete payment records or cancel subscriptions.

Owner-only private commands:
- /refund CHARGE_ID confirm: refund a verified stored receipt through Telegram and revoke that receipt's entitlement. Refunds do not automatically cancel all future renewals; review cancellation separately.
- /reconcile OFFSET: audit 100 Telegram transactions starting at offset (default zero), apply matched refunds, and report missing incoming receipts. Continue pages until the end. Missing receipts require investigation; the audit never fabricates subscription expiry or grants access from incomplete transaction data.

## Verification and limitations
python -m unittest discover -v
Tests cover scoring, replay, chat/admin boundaries, expiry, private demo, plan receipts, renewals, cancellation ownership, refund permissions and reconciliation. API calls use test doubles; these tests are NOT evidence of a real Telegram payment. Validate the payment flow in Telegram's dedicated test environment before enabling production purchases. No owner purchase is required by this code.

At-least-once updates may duplicate a notification after a crash; scoring/payment inserts remain idempotent. Reconciliation is an owner-invoked audit, not an automatic restoration of missing receipts. Payment support requires an actual operator. No Mini App, custom question packs, automatic scheduling or cross-group leagues are included. Thirty questions is a deliberately small initial bank.

Watch /ready, logs and volume capacity. A persistent HTTP 409 indicates duplicate polling; HTTP 401 indicates token problems. Existing webhooks are not silently removed. Restore backups into a separate environment before production recovery.

Official API references reviewed 2026-10-15: https://core.telegram.org/bots/api and https://core.telegram.org/bots/payments-stars.

## Bot administrators
Set OWNER_TELEGRAM_ID to the verified owner's numeric Telegram ID in Railway Variables. /myid privately displays the caller's ID. There is no first-user takeover or self-promotion.

In private chat, the owner uses /addadmin USER_ID, /removeadmin USER_ID and /admins. Roles persist in SQLite. Delegated bot admins may run /adminstatus and /reconcile. Only the owner may refund or manage administrators. These commands do not promote Telegram group members; group management still checks actual Telegram group administrator roles.
