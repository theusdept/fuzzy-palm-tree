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
