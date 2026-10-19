# LeagueHost payment readiness — 2026-10-19

## Verified live deployment

- Railway project `67be097b-61d0-4dcc-8333-b1379d197bc2`, production environment `2413f4ff-9a46-473d-83bd-c41178447d41`, service `3c86c7ac-1016-4890-9536-3d0e79f336c2`.
- Deployment `405f8ee9-642f-48ca-b8e9-334906925e12` is SUCCESS, running commit `cbd2ddcb9e0e732f9c467ab342e3559785e2c9f7` from main.
- One polling replica in sfo. Existing 500 MB `leaguehost-data` volume mounted at `/data`.
- Startup logs identify `@LeagueHostBot`; public `/ready` returned HTTP 200 and `telegram_ready: true`.
- Configured custom variable names: BOT_TOKEN, DB_PATH, PORT. OWNER_TELEGRAM_ID, PAYSUPPORT_CONTACT and PAYMENTS_ENABLED are absent. The running code therefore disables paid checkout.
- OAuth exposes variable names, not values. Actual DB_PATH, on-disk data, integrity and backups could not be inspected. Do not claim they were verified or overwrite DB_PATH based on an assumption.
- No production variables, volume, records, replica count or deployment were changed by this review. No second polling process was started.
- The separate Venture Studio Builder service and its six pre-existing staged changes were left untouched.

## Executed checks

The deployed commit passes all 33 existing unittest cases. This branch passes 41 cases after adding test-server routing, isolation checks, positive owner-ID validation, actual 5/20/unlimited round-limit checks, entitlement expiry/group isolation, invalid receipts, terms/support handlers and database reopen persistence checks.

Cancellation ownership, refund ownership, receipt replay, renewal lookup, reconciliation and administrator permissions are covered by the existing suite. All API interactions in these tests are simulated. Database checks use temporary databases, not customer data. These results are not a Telegram test-server transaction or production purchase.

## Test environment setup (no real Stars purchase)

Official references checked 2026-10-19:
- https://core.telegram.org/bots/payments-stars#testing-payments
- https://core.telegram.org/bots/features#dedicated-test-environment
- https://core.telegram.org/bots/api#createinvoicelink

Telegram's dedicated test server requires its own user account and BotFather-created bot. The authenticated tools available for this review cannot create that user account or obtain its bot token.

1. In Telegram Desktop: Settings, Shift+Alt+right-click Add Account, select Test Server. Create a test account and a bot through BotFather in that server.
2. Put that test bot token in a secure staging variable `TEST_BOT_TOKEN`; never paste it into issues or commits. Use an isolated staging service and volume, never clone production variables or mount the production volume.
3. Deploy this branch with one replica, `TELEGRAM_TEST_ENVIRONMENT=true`, `TEST_DB_PATH=/data/leaguehost-test.db`, the test account's `OWNER_TELEGRAM_ID`, a monitored staging `PAYSUPPORT_CONTACT`, and `PAYMENTS_ENABLED=true`. Do not set BOT_TOKEN. Test mode uses `/bot<TOKEN>/test/METHOD` for every call and refuses a Railway environment named production, a reused BOT_TOKEN, or the configured production DB_PATH.
4. Verify `/ready`, `/myid`, `/terms`, `/support`, `/paysupport`, `/demo`, and group `/newleague`. Verify the support contact actually receives and handles requests.
5. In separate test groups exercise `/upgrade pro agree` and `/upgrade club agree`. Complete test-server checkout using test Stars. Record actual pre-checkout and successful-payment receipt evidence, amounts 100/250 XTR and entitlement expiry; do not manufacture these records.
6. Verify another account cannot use the buyer-bound invoice or cancel the purchase. Verify `/subscription`, `/cancel GROUP_ID`, owner `/refund CHARGE_ID confirm`, and `/reconcile`. Verify cancellation preserves the paid period, refund removes only the refunded receipt's entitlement, and delegated admins cannot refund or manage admins.
7. Verify restart persistence and restore a backup into a separate test volume. Do not restore over the production database. Record remaining renewal observations honestly if a recurring renewal has not occurred.

## Production activation gates

- Ashley verifies her numeric Telegram ID using private `/myid` at @LeagueHostBot; do not infer it from GitHub identity or group membership.
- Ashley identifies an actually monitored payment-support contact and approves the existing customer terms: Free 5/week, Pro 20/week at 100 Stars/30 days, Club unlimited at 250 Stars/30 days, automatic renewal, shared 30-question bank, cancellation at period end, and refund requests through support. Runtime terms are in `app.py` as TERMS and exposed by `/terms`.
- Finish real test-server validation above. A production purchase by Ashley is not required.
- With authorized runtime access, verify DB_PATH resolves inside the existing mounted volume, SQLite integrity, backup schedule and successful isolated restore. Keep the original volume and one replica.
- Configure OWNER_TELEGRAM_ID and PAYSUPPORT_CONTACT only with verified values. Set PAYMENTS_ENABLED=true only after the preceding gates pass and activation remains authorized. Redeploy only LeagueHost, verify readiness and `/paysupport`, and confirm Free users remain intact.

Paid plans remain unavailable until these gates are satisfied. Creating a PR or passing mocked tests does not activate them.
