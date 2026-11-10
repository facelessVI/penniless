# Fixtures

Four fake SimpleFIN `/accounts` (protocol v2) responses, one per 2026 quarter, used when
`PENNILESS_SOURCE=fixture`. They are **not** real data and were not captured from a real bank. They
were written by hand to look exactly like a Bridge response so the fetch, ingest, and query paths
run unchanged without spending SimpleFIN quota or touching the network.

| File | Window | Fake transactions |
| --- | --- | --- |
| `accounts-2026-q1.json` | 2026-01-01 - 2026-03-31 | 66 |
| `accounts-2026-q2.json` | 2026-04-01 - 2026-06-30 | 66 |
| `accounts-2026-q3.json` | 2026-07-01 - 2026-09-30 | 66 |
| `accounts-2026-q4.json` | 2026-10-01 - 2026-11-10 | 33 |

Three accounts, all on one connection (`CON-FIXTURE-1`, "Fixture Credit Union"):

- `ACT-CHECKING` "Everyday Checking", `extra.type` `checking`, so it counts as cash.
- `ACT-SAVINGS` "Rainy Day Savings", `extra.type` `savings`, so it counts as cash.
- `ACT-CREDIT` "Everyday Rewards Card", `extra.type` `credit card`, so it does not count as cash.

Recurring descriptions (rent, payroll, utilities, groceries, a card payment, transfers between the
two depository accounts) exist so category rules have something recognizable to match.

## How the fixture source uses them

`app/simplefin.py` merges every file in this directory, deduplicates transactions by
`(connection, account, transaction id)`, and then filters transactions to the requested
`start-date`/`end-date` window, exactly like a server would. Accounts and balances are always
returned. Overlapping 5-day windows therefore hand the same transaction back twice, which is what
exercises the upsert.

## Demo setup tokens

Both are base64 of a claim URL. Nothing is claimed and no request is made in fixture mode.

- Success: `aHR0cHM6Ly9maXh0dXJlLmludmFsaWQvc2ltcGxlZmluL2NsYWltL2RlbW8=`
  (decodes to `https://fixture.invalid/simplefin/claim/demo`)
- Rejected, to exercise the "already used or compromised" path:
  `aHR0cHM6Ly9maXh0dXJlLmludmFsaWQvc2ltcGxlZmluL2NsYWltL3VzZWQ=`
  (decodes to `https://fixture.invalid/simplefin/claim/used`)

Any other valid base64 token decodes to a claim URL and succeeds. A token that is not valid base64
is rejected with the same message the live path gives.

## The fixture access URL

A successful fixture claim stores `https://fixture.invalid/accounts` as the access URL. `.invalid`
can never resolve, so a fixture run that accidentally tried to reach the network would fail rather
than send data anywhere. The fixture source never dials it: it reads these files instead.

## Coverage in time

The dataset stops at 2026-11-10. A fixture backfill walks back 12 months from today, so it picks up
whatever falls inside its windows: run it in 2026 and the demo has data through the current month;
run it in 2027 and the windows no longer overlap these dates, so the app starts empty and the
tables show their empty states. Regenerating the files for a new period is the fix, not changing
code.
