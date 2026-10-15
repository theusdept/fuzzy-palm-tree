# LeagueHost
Standalone Telegram group quiz league pilot. Python standard library, SQLite on a persistent Railway volume, long polling (one replica only).

## Run
Python 3.13. Set BOT_TOKEN securely in the hosting environment. Set DB_PATH to /data/leaguehost.db and attach a volume at /data. Run `python app.py`. Without a token the process exposes setup status and does not connect to Telegram. /health checks process health; /ready requires successful recent polling. Never commit the token.

## Telegram setup
Startup registers commands, description and about text automatically. Add the bot as an administrator of your group (no delete/ban/invite privileges needed), then /newleague and /round. Existing webhooks are never silently replaced. If this bot already has a webhook, verify ownership and remove it before enabling this long-polling deployment. Keep Telegram privacy mode enabled.

## Features
Admin-only league creation, closure and quiz opening; 60-second multiple-choice rounds; 30 authored general-knowledge questions; one answer per Telegram user per round; 10 points for correct answers; weekly UTC standings with live-round scores hidden; durable update offset; replay-safe round creation and scoring; private player export and confirmed deletion; 90-day answer retention. No unsolicited marketing or invitation messages.

## Verification
`python -m unittest discover -v`
Tests cover scoring, duplicate answers, duplicate updates, cross-chat submission, expiry, admin checks, closed leagues and hiding unfinished scores.

## Operational limits
This is a free pilot, not the entire research roadmap. No Stars checkout, subscription entitlement, Mini App, automated schedule, custom topic packs, team branding, cross-group leagues or measured retention yet. No claims of revenue or live Telegram verification until a real BOT_TOKEN is configured and a group round succeeds. Questions repeat across weeks. Do not sell access to this pilot.

At-least-once Telegram delivery can duplicate a response if the process exits after sendMessage but before persisting the update offset; scoring remains unique. SQLite requires exactly one instance. Use Railway volume backups; restore a backup into a separate service before switching production. Logs never intentionally contain tokens or message bodies. Public health routes reveal only service readiness. Watch /ready, deployment logs and volume capacity. A persistent Telegram 409 indicates another polling instance: stop the duplicate instance. Telegram 401 means the token needs correction. No automatic token rotation or deletion of existing webhook configurations.

Platform references reviewed October 14, 2026: https://core.telegram.org/bots/api and https://core.telegram.org/bots/payments-stars. Any future digital purchases inside Telegram must use Stars and verified successful_payment handling.


## Plans and Telegram Stars (staged, disabled by default)
- **Free:** 0 Stars, 5 group quiz rounds per UTC week.
- **Pro:** 100 Stars every 30 days, up to 20 group quiz rounds per UTC week.
- **Club:** 250 Stars every 30 days, unlimited group quiz rounds; the 30-question pool repeats after exhaustion.
- Every tier uses the existing 30-question general-knowledge bank and weekly leaderboard. Paid plans are per group, purchased by a group administrator. These are suggested launch prices, not USD equivalents.
- `/plans` lists tiers and `/upgrade` offers admin-only subscription purchase links when live checkout is explicitly enabled. `/subscription` is private-only and displays subscriptions purchased by the Telegram user; `/paysupport` shows support details. `/demo` is a free private sample question and `/invite` shares the group-installation link.
- Telegram's `createInvoiceLink` with `currency=XTR`, `provider_token=""`, and `subscription_period=2592000` creates recurring 30-day subscriptions. Payment approvals check bot-issued order IDs, buyer, Stars amount, currency, and whether checkout is enabled. **Premium access is awarded only after validated `successful_payment`** and stored Telegram charge ID, never at `pre_checkout_query`.
- Payment records live in the mounted SQLite database, with unique charge IDs and expiration timestamps. Duplicate payment updates do not create duplicate entitlements. Refunds are represented in the ledger; a verified Telegram `refundStarPayment` call and ledger update must occur together in a controlled support workflow.
- Live checkout is **off** unless `PAYMENTS_ENABLED=true`, `PAYSUPPORT_CONTACT` is populated with a verified support contact, and `OWNER_TELEGRAM_ID` is set to a numeric ID. Leave PAYMENTS_ENABLED unset/false until checkout, refunds, renewal/cancellation, and testing are confirmed. Never commit bot tokens.
- The bot does **not yet expose a self-service cancellation or refund command**, and recurring subscriptions can outlive the buyer's admin role unless separately reviewed. Manual support must be provided before activating billing. The group owner should assess whether to enable payments only after those conditions are addressed.
- Validation: `python -m unittest discover -v` covers existing quiz rules and Stars ledger test cases; a successful GitHub CI run is required before merge. Payment processor sandbox testing remains separate from local tests.
