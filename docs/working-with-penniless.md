# Working with Penniless

Short operational guide. Deep context (design decisions, gotchas, API details) lives in
`docs/working-with-penniless.md`. This file is just how to run and manage the thing.

## What it is

Local-only finance dashboard. Pulls read-only accounts and transactions from SimpleFIN, categorizes
them from rules you teach it, and reports money in / out / net per period. FastAPI + SQLite on
`127.0.0.1:8000`, Angular 22 on `127.0.0.1:4200`. No auth, no hosting, no remote repo.

## Prerequisites

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- Node 20.19+ or 22.12+ and npm (Angular 22 requirement)
- Optional: a SimpleFIN Bridge setup token (only for live mode)

## Getting started

```bash
cd penniless
npm run install:all      # root npm install, uv sync, ui npm install
npm run dev              # fixture mode, both processes
```

Open `http://127.0.0.1:4200`. In fixture mode, paste the demo setup token from
`api/fixtures/README.md` on the Setup page, then press **Backfill 12 months** on the Dashboard.
Fixture data covers 2026-01-01 through 2026-11-10; outside that range the tables are legitimately
empty.

Modes:

| Command | Behavior |
| --- | --- |
| `npm run dev` | Fixture source, `penniless-dev.sqlite`, no network, no quota |
| `npm run dev:live` | Real SimpleFIN, `penniless.sqlite`, spends quota |
| `npm run dev:api` / `npm run dev:api:fixture` | API only |
| `npm run dev:ui` | UI only (`ng serve`, proxies `/api` to the API) |

Fixture mode wipes `penniless-dev.sqlite` on every startup. That is expected: reconnect and backfill
again, or the UI shows zero rows. The category rules you have taught it are the one thing a fixture
reset keeps.

## First live run

1. Get a setup token from SimpleFIN Bridge.
2. `npm run dev:live`, then connect on the Setup page.
3. Connecting claims the access URL, writes `api/.data/credentials.json` (mode `0600`), and runs the
   12-month backfill in one go (5 calls).
4. In the dashboard, turn off **Counts as cash** for credit cards and brokerages. The Bridge does
   not tell us account type reliably, so every account defaults to cash.
5. Categorize merchants from the **Transactions** page. Nothing is pre-taught, so a fresh database
   starts fully `Uncategorized` and gets better as you work through it.

## Managing state

Everything lives in `api/.data/` (gitignored):

| File | Purpose |
| --- | --- |
| `penniless.sqlite` | live data |
| `penniless-dev.sqlite` | fixture data, rebuilt each fixture startup |
| `credentials.json` | SimpleFIN access URL, mode `0600`, never logged or returned |

- **Start over (live)**: stop the API, delete `api/.data/`, restart, reconnect.
- **Start over (fixture)**: restart the API. Accounts and transactions are rebuilt; learned category
  rules survive. Or delete `api/.data/` if you also want to drop the fixture credential and the rules.
- **Back up**: copy `api/.data/penniless.sqlite`. It is a single file.
- **Never** point live and fixture at the same DB file. Different filenames enforce this unless you
  override `PENNILESS_DB_PATH`.

Env overrides are listed in `api/.env.example` (`PENNILESS_SOURCE`, `PENNILESS_DATA_DIR`,
`PENNILESS_DB_PATH`, `PENNILESS_FIXTURE_DIR`, `PENNILESS_REFRESH_MIN_INTERVAL_HOURS`). Defaults are fine
for normal use.

## Quota discipline

SimpleFIN allows **24 `/accounts` calls per day** per access URL, and every fetch spends one.

- A refresh (one 5-day window) costs 1 call and is refused for `PENNILESS_REFRESH_MIN_INTERVAL_HOURS`
  (default 6) after a success. A `429` from `/api/refresh` is the guard working, not a bug.
- A 12-month backfill costs 5 calls (89-day windows overlapping by 5 days, covering 425 days).
- Nothing fetches on page load. Do not add polling, retries, or fetch-on-render.
- `error_code` values in `gen.api` are advisories: data is complete and the fetch still counts as
  `ok`. Only `con.*`, `act.*`, `gen.auth`, and unknown codes are real failures.

## Managing categories

Categories and rules live in SQLite, in two tables: `categories` (the closed list, with a `position`
that is the order the selects show) and `rules` (one row per exact transaction description). There is
no file to edit.

- Click any transaction row on the **Transactions** page to open **Transaction**, pick a category, and
  save. Every stored row with that exact description moves with it, and rows fetched later arrive
  already categorized. The select opens on the row's current category, so re-picking is a correction.
- A rule matches the whole description. `SPOTIFY USA` and `SPOTIFY USA 877-7781161 NY` are different
  merchants, so a merchant whose description changes has to be taught again.
- Anything without a rule is `Uncategorized`, and `Uncategorized` is a selectable category, so
  selecting it is how a rule is taken back off a merchant.
- `Transfers` is only a category. A row whose category is `Transfers` is a transfer, which excludes it
  from in/out totals and renders it muted.
- Invalid category data fails at startup and before every fetch, so a bad row cannot spend quota.
- Ingest reclassifies on every upsert. To reclassify existing rows, press **Re-apply rules** or
  `POST /api/categories/apply`.
- The live database from before this switch has its rows reset to `Uncategorized`, because the rules
  that produced those labels are gone.

## Migrations and schema

`api/migrations/*.sql` are applied in filename order at startup and recorded in the DB. To add a
column, add a new numbered file; never edit an applied one. Fixture mode drops and recreates its DB,
so the migration path is exercised there on every run.

## Checks before committing

```bash
cd api && uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest
cd ui && npx ng build && npx prettier --check "src/**/*.{ts,html,scss,json}"
```

There is no UI test suite. Verify UI changes by hand in fixture mode, including empty states.
`api/tests/` covers pure functions plus the SQL-level category operations (classification, apply, the
fixture rule snapshot and restore) - it is not a licence to grow a broad Python suite.

## When something looks wrong

| Symptom | Likely cause |
| --- | --- |
| Tables empty in fixture mode | Date outside 2026-01-01 - 2026-11-10, or DB was wiped on restart |
| Empty after restart | Fixture reset cleared rows; run backfill again (credential survives) |
| Refresh returns 429 | Refresh guard, wait for `next_refresh_allowed_at` |
| Startup fails on categories | `categories` table empty or missing `Uncategorized`, or a rule pointing at a category that does not exist |
| Money looks wrong for one account | The **Counts as cash** toggle |
| Uvicorn reloads in a loop | Reload watcher must stay scoped to `app` and `migrations` only |
