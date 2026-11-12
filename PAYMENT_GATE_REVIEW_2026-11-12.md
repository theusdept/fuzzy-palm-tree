# Payment-gate integration review — November 12, 2026

## Scope and result

Reviewed current main `da4b990d4834af9750f2d771d87b85035989a329` against PR #7
head `c575a85482b7c780a2bfa83b6ecadb242c9e8b6c`, then corrected the remaining
reconciliation command parsing defect in this follow-up. The payment-gate
corrections are technically ready for integration. This record does not approve
deployment or payment activation.

The original three failures were independently reproduced on main: leading-zero
owner IDs enabled checkout, 5,000-digit IDs raised `ValueError`, and excessively
nested readiness JSON raised `RecursionError`. PR #7 rejects all three safely.
Accepted owner IDs match `Bot.is_owner()` for numeric Telegram identities,
including surrounding configuration whitespace and the upper accepted boundary.
Group administrator permission and original-buyer pre-checkout checks remain
separate and protected.

## Additional correction

`/reconcile ²` previously passed `isdigit()` and failed during integer conversion.
Because the polling offset advances only after handling completes, a malformed
authorized command could leave polling retrying the same update. This existed on
both main and the original PR head.

The command now validates ASCII digits and a maximum input length before integer
conversion. A local defensive offset limit of 0 through 2,147,483,647 is enforced
and disclosed in the usage response. Missing offsets still default to zero;
bounded leading-zero offsets retain their existing numeric meaning. Invalid
commands return without Telegram transaction requests or ledger changes.

Four regression test methods cover invalid and oversized inputs, subsequent
command processing, valid offsets and boundaries, owner/delegated administrator
permissions, private-chat restrictions, disabled checkout, and pagination.

## Verification performed

- Clean Python 3.13.5 virtual environment with no installed dependencies, cleared
  environment variables, fake Telegram responses, isolated SQLite data, and
  outbound socket connections blocked during the full suite.
- Current main: all 45 existing unittest cases passed.
- Original PR #7 head: all 65 unittest cases passed.
- Eight additional independent checks passed; one explicitly reproduced the
  pre-existing reconciliation defect rather than asserting it was fixed.
- The four new reconciliation regression methods failed against the original
  implementation and pass after the correction.
- Updated branch: all 69 discovered unittest cases passed.
- `git diff --check` passed.

The suites cover disabled invoice/order creation and pre-checkout rejection,
receipt fulfillment and renewals while checkout is closed, duplicate suppression,
subscription lookup, buyer-scoped cancellation, owner-only refunds, delegated
administrator restrictions, free access, entitlement expiry, group isolation,
and database persistence. All payment records and API responses are synthetic.
The updated commit's GitHub Actions result must be checked separately; the
October 26 successful workflow only covers the original PR head.

## Production boundary

No production configuration was independently verified during this review.
The October 26 operational record remains historical. No production changes,
deployment, merge, payment activation, or real charges were performed.

Readiness JSON validates structure and release equality, not the truth of
operator assertions. Actual isolated Telegram test-server transactions and the
operational requirements in `STARS_RELEASE_GATE.md` remain necessary before
payment activation. Production changes require explicit owner approval.
