# Telegram Stars release gate

The LeagueHost `billing.checkout_enabled()` guard now requires all of the following: `PAYMENTS_ENABLED=true`, canonical positive decimal `OWNER_TELEGRAM_ID` below `2**52` (no leading zeros), monitored `PAYSUPPORT_CONTACT`, and a release-bound JSON `PAYMENT_READINESS_EVIDENCE` with independently recorded evidence for all required checks. Without this record checkout remains off.

## Evidence schema

`PAYMENT_READINESS_EVIDENCE` is a JSON object containing `release_sha` (matching `RAILWAY_GIT_COMMIT_SHA`, or `PAYMENT_RELEASE_SHA` if Railway does not expose it), `approved_by` (verified operator), and `checks` (objects with `passed:true` and a nonempty `evidence` reference). Required check keys are in `billing.READINESS_CHECKS`. A recorded reference is an operator assertion, not cryptographic proof: reviewers must check the underlying evidence. Never fabricate evidence, use production funds to test, or paste secrets into GitHub.

The guard checks structure and release equality. It does not authenticate the approving operator, contact support, inspect backups, or verify the referenced records. Unit-test fixtures must never be copied into deployment variables. See [the October 26 validation record](PAYMENT_GATE_VALIDATION_2026-10-26.md) for current evidence and outstanding operational checks.

## Rollout

1. Review and merge the PR after CI and code review; deployment should preserve the existing single polling replica and persistent volume.
2. Confirm `/ready`, database backups, restored backup test, support availability and the customer-facing terms and privacy policy.
3. Use a separate Telegram test-server bot, token, isolated Railway service and volume. Test actual Stars invoices, receipts, duplicates, refunds, reconciliation and subscription cancellation; record references.
4. Verify platform, legal, payout and account prerequisites. Populate the readiness record and verified release SHA in Railway secrets; only then enable checkout. Keep a rollback by setting `PAYMENTS_ENABLED=false`.
5. Do not accept the shared Venture Studio staging patch (77 changes) just to activate LeagueHost; it contains unrelated new services and may incur costs.

The Venture Studio Builder in this repository is a read-only portfolio catalog; its commercial scores are hypotheses, not payment-readiness signals. This change does not deploy additional bots or authorize spending.
