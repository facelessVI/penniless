# Working with Penniless

Short operational guide. Deep context (design decisions, gotchas, API details) lives in
`docs/working-with-penniless.md`. This file is just how to run and manage the thing.

## What it is

Local-only finance dashboard. Pulls read-only accounts and transactions from SimpleFIN, categorizes
them from `api/categories.yaml`, and reports money in / out / net per period. FastAPI + SQLite on
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
again, or the UI shows zero rows.

## First live run

1. Get a setup token from SimpleFIN Bridge.
2. `npm run dev:live`, then connect on the Setup page.
3. Connecting claims the access URL, writes `api/.data/credentials.json` (mode `0600`), and runs the
   12-month backfill in one go (5 calls).
4. In the dashboard, turn off **Counts as cash** for credit cards and brokerages. The Bridge does
   not tell us account type reliably, so every account defaults to cash.
5. Edit `api/categories.yaml` for your merchants, then press **Apply rules** on the Dashboard. No
   restart needed.

## Managing state

Everything lives in `api/.data/` (gitignored):

| File | Purpose |
| --- | --- |
| `penniless.sqlite` | live data |
| `penniless-dev.sqlite` | fixture data, rebuilt each fixture startup |
| `credentials.json` | SimpleFIN access URL, mode `0600`, never logged or returned |

- **Start over (live)**: stop the API, delete `api/.data/`, restart, reconnect.
- **Start over (fixture)**: restart the API. Or delete `api/.data/` if you also want to drop the
  fixture credential.
- **Back up**: copy `api/.data/penniless.sqlite`. It is a single file.
- **Never** point live and fixture at the same DB file. Different filenames enforce this unless you
  override `PENNILESS_DB_PATH`.

Env overrides are listed in `api/.env.example` (`PENNILESS_SOURCE`, `PENNILESS_DATA_DIR`,
`PENNILESS_DB_PATH`, `PENNILESS_FIXTURE_DIR`, `PENNILESS_CATEGORIES_PATH`,
`PENNILESS_REFRESH_MIN_INTERVAL_HOURS`). Defaults are fine for normal use.

## Quota discipline

SimpleFIN allows **24 `/accounts` calls per day** per access URL, and every fetch spends one.

- A refresh (one 5-day window) costs 1 call and is refused for `PENNILESS_REFRESH_MIN_INTERVAL_HOURS`
  (default 6) after a success. A `429` from `/api/refresh` is the guard working, not a bug.
- A 12-month backfill costs 5 calls (89-day windows overlapping by 5 days, covering 425 days).
- Nothing fetches on page load. Do not add polling, retries, or fetch-on-render.
- `error_code` values in `gen.api` are advisories: data is complete and the fetch still counts as
  `ok`. Only `con.*`, `act.*`, `gen.auth`, and unknown codes are real failures.

## Managing categories

`api/categories.yaml` is the only source. `categories` is a closed list and must include
`Uncategorized`; `rules` are ordered, first match wins, `match.description` is a regex applied with
`re.search`, and `transfer: true` excludes a row from in/out totals while keeping it visible.

- Invalid rules fail at startup and before every fetch, so a typo cannot spend quota.
- Ingest reclassifies on every upsert. To reclassify existing rows, press **Apply rules** or
  `POST /api/categories/apply`.

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
`api/tests/` covers pure functions only (window planning, error classification).

## When something looks wrong

| Symptom | Likely cause |
| --- | --- |
| Tables empty in fixture mode | Date outside 2026-01-01 - 2026-11-10, or DB was wiped on restart |
| Empty after restart | Fixture reset cleared rows; run backfill again (credential survives) |
| Refresh returns 429 | Refresh guard, wait for `next_refresh_allowed_at` |
| Startup fails on categories | `categories.yaml` syntax, unknown category, or missing `Uncategorized` |
| Money looks wrong for one account | The **Counts as cash** toggle |
| Uvicorn reloads in a loop | Reload watcher must stay scoped to `app` and `migrations` only |
