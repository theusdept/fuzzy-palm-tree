# LeagueHost payment-gate validation — October 26, 2026

## Result

PR #6 is deployed in production. Paid checkout remains disabled. The validation branch fixes three reproduced input-validation defects; those fixes are not part of the production deployment recorded below. No production configuration or data was changed by this validation.

## Observed production state

- Project: `67be097b-61d0-4dcc-8333-b1379d197bc2` (LeagueHost).
- Environment: `2413f4ff-9a46-473d-83bd-c41178447d41` (production).
- Service: `3c86c7ac-1016-4890-9536-3d0e79f336c2` (leaguehost-bot).
- Active deployment: `8a19a01c-d5a3-40a5-ae8b-da0e4406d9d2`, status `SUCCESS`, commit `da4b990d4834af9750f2d771d87b85035989a329` (PR #6). It was created October 25 at 9:20 p.m. America/Chicago (October 26, 02:20 UTC).
- Source remains `theusdept/fuzzy-palm-tree`, branch `main`. One configured replica in `sfo`; older deployments are marked `REMOVED`. No second production poller was started by this review.
- Existing 500 MB `leaguehost-data` volume, ID `39a315ce-3b3f-4c1e-a8a9-921afef6f2f7`, remains mounted at `/data`.
- At October 26, 12:25:34 p.m. America/Chicago (17:25:34 UTC), `GET https://leaguehost-bot-production.up.railway.app/ready` returned HTTP 200 with `{"service":"LeagueHost","configured":true,"telegram_ready":true}`. The readiness endpoint checks recent polling, not billing or SQLite integrity.
- Runtime logs record `Telegram connected: @LeagueHostBot` and one later `Poll retry: URLError`. The successful readiness response is a point-in-time observation, not proof of continuous availability.
- `OWNER_TELEGRAM_ID` and `PAYSUPPORT_CONTACT` are now configured by name, alongside `BOT_TOKEN`, `DB_PATH`, and `PORT`. Their values are redacted by Railway OAuth. The October 19 readiness document is historical; its statement that owner/support variables are absent is no longer current.
- `PAYMENTS_ENABLED`, `PAYMENT_READINESS_EVIDENCE`, and `PAYMENT_RELEASE_SHA` are absent from the rendered variable-name inventory. The first two independently keep checkout off. This review did not read the runtime value of Railway's injected commit SHA.
- LeagueHost has only its production environment and service. No LeagueHost test-server service or readable test credentials were available through the connected tools.
- Neither LeagueHost production nor the referenced Venture Studio staging environment had a pending staged patch when inspected. No patch was accepted, deployed, discarded, or edited by this review.

## Automated validation and corrections

The exact PR #6 commit passed all 45 existing unittest cases locally. Its GitHub push workflow also succeeded: https://github.com/theusdept/fuzzy-palm-tree/actions/runs/40252472928.

Three defects were reproduced before correction:

1. `OWNER_TELEGRAM_ID=00042` enabled checkout with otherwise complete synthetic evidence, while `Bot.is_owner(42)` returned false. Invoice creation and pre-checkout approval could proceed without a recognized refund/admin owner. The guard now requires canonical decimal IDs.
2. A 5,000-digit owner ID raised `ValueError` instead of returning false, interrupting invoice/pre-checkout handling. A length bound now rejects it before integer conversion.
3. Excessively nested JSON evidence raised `RecursionError` instead of returning false. The evidence parser now treats that error as invalid evidence.

The corrected branch passes 65 unittest cases on local Python 3.12, including 20 new test methods with parameterized cases. The repository workflow runs on Python 3.13. `git diff --check` also passes. CI results for the correction branch must be checked on its pull request.

The new tests verify every required check is mandatory; missing/wrong JSON types, approving operator, evidence references, and non-boolean pass flags are rejected; releases match exactly; a fallback SHA cannot override Railway's SHA; owner bounds and support/activation requirements hold; both Pro and Club have positive synthetic invoice/pre-checkout controls; blocked gates create no invoice or order and explicitly reject existing-invoice pre-checkout requests. They also verify that closing the gate preserves receipt fulfillment, cancellation, refund handling, and retained receipt records.

All API responses in these tests are simulated. All SQLite records are synthetic and isolated from production. These tests are regression evidence only. They are not Telegram test-server transactions, production data integrity checks, backups, or operator approval. No test fixture was placed in Railway.

## Evidence against the 12 actual requirements

No release-bound `PAYMENT_READINESS_EVIDENCE` record is configured. Available observations must be independently reviewed before any check is marked passed.

| Required check | Available evidence | Still required |
| --- | --- | --- |
| `owner_verified` | Variable name exists; format/bounds/owner consistency tested locally. | Read the configured value securely and match it to the operator's actual private `/myid`; record verified identity and authority. |
| `production_healthy` | Successful PR #6 deployment, one configured replica, Telegram startup log, current HTTP 200 `/ready`. | Release-specific operator review of runtime stability and incident handling; repeat readiness after deploying corrections. |
| `terms_approved` | `TERMS` text and `/terms` handler in deployed source; explicit agreement covered by unit tests. | Operator approval of the exact customer terms for the intended release, plus actual customer-visible response verification. |
| `privacy_published` | `PRIVACY` text, `/privacy`, export and deletion handlers in deployed source. | Verify the live policy is reachable and accurately describes actual storage, retention and support arrangements; record the policy/version. |
| `support_verified` | `PAYSUPPORT_CONTACT` name exists; support handlers tested with a fake API. | Verify its value, reachability, monitored ownership, response process and refund support independently. |
| `prices_approved` | Pro 100 XTR/30 days, Club 250 XTR/30 days; Free 5/week, Pro 20/week, Club unlimited; source and tests agree. | Release-specific approval and actual test invoice/client display verification, including automatic renewal disclosure. |
| `test_invoice_and_fulfillment` | Synthetic XTR invoice, buyer/currency/amount and receipt validation tests. | Actual isolated Telegram test-server invoices, pre-checkout, successful-payment charge IDs, and entitlement expiry records for both plans. |
| `test_duplicate_and_refund` | Synthetic duplicate, refund, cancellation and owner-scope regressions. | Actual test-server replay/duplicate behavior, refunds, unauthorized actor rejection, and cancellation observations. Record renewal limitations honestly. |
| `test_reconciliation` | Synthetic `getStarTransactions` reconciliation and refund tests. | Compare actual test-server transaction IDs/amounts with the isolated ledger, including missing receipts and refunds. |
| `storage_and_restore` | Existing `/data` volume metadata; temporary-database reopen/integrity tests. | Secure runtime verification of actual `DB_PATH`, production SQLite integrity, backup schedule, and a successful restore into separate storage. No production database inspection or restore occurred. |
| `monitoring` | Health route, runtime logs; Railway tracing currently disabled. | Verify polling/readiness and payment failure alerts, reconciliation discrepancies, support escalation, alert delivery and accountable response. Tracing state alone does not establish whether other monitoring exists. |
| `platform_requirements` | XTR-only invoice implementation and Telegram test API isolation tests; current official documentation reviewed. | Operator confirmation of bot ownership, account protection, accepted platform terms, applicable account/reward requirements and readiness to handle disputes. |

## Safe activation sequence

1. Review and merge the narrow correction PR after CI; deploy only LeagueHost with checkout disabled. Preserve the existing volume, configured database path and single polling instance. Verify the deployed revision and `/ready` again.
2. Obtain a separate Telegram **test-server** account and BotFather-created bot. Store its token securely as `TEST_BOT_TOKEN` in an isolated service with separate storage. Do not reuse production tokens, variables or volume. The connected tools in this review could not create that Telegram test-server account or read such credentials.
3. Telegram documents free Stars payment testing in its dedicated test environment. Requests must use `https://api.telegram.org/bot<TOKEN>/test/METHOD`. No production Stars purchase or real funds are needed.
4. Run actual test-server payment and lifecycle checks and preserve their real records. The production readiness gate also runs in the current test-mode application: setting `PAYMENTS_ENABLED=true` alone cannot bootstrap a first test. Use a separately reviewed, isolated test-server payment driver for that initial validation; do not invent completed checks or copy unit-test evidence into any deployment. The historical October 19 test-setup instructions do not by themselves satisfy the newer PR #6 gate.
5. Complete the independent operational verifications in the table. Bind evidence to the exact production release: the guard prioritizes `RAILWAY_GIT_COMMIT_SHA`, using `PAYMENT_RELEASE_SHA` only when the former is empty. Set a real identified approving operator and independently reviewed references for all 12 checks. A commit change invalidates an older evidence record.
6. Enable production checkout only after those records are genuine, complete and approved. Verify support, free access, invoice presentation and rejection behavior. The immediate checkout kill switch is `PAYMENTS_ENABLED=false`; it does not erase valid receipts or disable cancellation/refund servicing.

## Sources

- PR #6: https://github.com/theusdept/fuzzy-palm-tree/pull/6
- Release requirements: [STARS_RELEASE_GATE.md](STARS_RELEASE_GATE.md)
- Historical readiness record: [PAYMENT_READINESS.md](PAYMENT_READINESS.md)
- Gate and regression coverage: [billing.py](billing.py), [test_payment_release_gate.py](test_payment_release_gate.py), [test_readiness.py](test_readiness.py)
- Railway service: https://railway.com/project/67be097b-61d0-4dcc-8333-b1379d197bc2/service/3c86c7ac-1016-4890-9536-3d0e79f336c2?environmentId=2413f4ff-9a46-473d-83bd-c41178447d41
- Telegram Stars testing and live checklist: https://core.telegram.org/bots/payments-stars#testing-payments
- Separate test accounts/bots and API routing: https://core.telegram.org/bots/features#dedicated-test-environment
