# Working with Penniless

Short operational guide: how to run and manage the thing.

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
cd penniless              # the repo root
npm run install:all      # root npm install, uv sync, ui npm install
npm run dev              # fixture mode, both processes
```

Open `http://127.0.0.1:4200`. In fixture mode, paste the demo setup token from
`api/fixtures/README.md` on the Setup page, then press **Backfill 12 months** on **Settings -> Data**.
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
   starts fully `Uncategorized` and gets better as you work through it. Clicking a row opens a
   **Keyword** select and a **Category** select. The keyword list is built from that description -
   the whole description, its words, and two-word phrases - plus any rule that already matches it,
   and each option shows how many stored transactions it would move. Pick a keyword, pick a
   category, and save: every transaction containing that keyword moves, including ones fetched
   later. Picking `Uncategorized` with a keyword removes that rule instead.

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

- **Settings** -> **Categories** (the gear at the right of the top nav, `/settings/categories`) is
  where categories are managed. The page lists every category in the order the selects show them,
  with how many transactions and rules currently carry it.
    - **Create category** opens a dialog with one name field and appends the category to the end of
      the list.
    - Each row has a grip handle at its left: drag it to move the category, and the new order is
      saved when you let go of it. Dropping outside the list leaves the order as it was, and the
      whole list is renumbered from 1 every time, so a gap a delete left behind is closed by the
      next move. `Transfers` and `Uncategorized` move like any other category.
    - The pencil renames, through the same dialog. The rename cascades to every rule and transaction
      that carries the name, so nothing needs reclassifying afterwards.
    - The trashcan asks first, then deletes. Deleting a category that is in use moves its
      transactions to `Uncategorized` and deletes the rules that pointed at it; the confirmation says
      how many of each will move. No transaction is lost.
    - `Transfers` and `Uncategorized` cannot be renamed or deleted: the first is how the app
      recognizes a transfer, and the second is where unmatched transactions land.
    - A name is trimmed, may not be blank or contain a slash, may be at most 40 characters, and may
      not collide with an existing name in any case.
- Click any transaction row on the **Transactions** page to open **Transaction**. The **Keyword**
  select opens on the rule that decides the row (or on the whole description when nothing matches
  it) and the **Category** select opens on the row's current category. Saving writes or re-points that
  pattern and re-labels every row it matches, across accounts and the whole history; rows fetched
  later arrive already categorized.
- A rule is a pattern with a match type. `exact` matches the whole description and stays
  case-sensitive; `contains` matches a case-insensitive substring, which is what makes
  `SPOTIFY USA 877-7781161 NY` follow a `SPOTIFY USA` rule. When several rules match, the most
  specific one wins: `exact` first, then the longer pattern, then the most recently updated rule, so
  a description that has its own exact rule keeps it even when a keyword also covers it.
- Anything without a rule is `Uncategorized`, and `Uncategorized` is a selectable category: choosing
  it with a keyword deletes that keyword's rule, and its rows fall back to the next matching rule.
  That is the only way a rule is removed, so a keyword that no longer matches any stored row cannot
  be deleted from the UI yet.
- `Transfers` is only a category. A row whose category is `Transfers` is a transfer, which excludes it
  from in/out totals and renders it muted.
- Invalid category data fails at startup and before every fetch, so a bad row cannot spend quota.
- Ingest reclassifies on every upsert. To reclassify existing rows, press **Re-apply rules** on
  **Settings -> Data** or call `POST /api/categories/apply`.
- The live database from before this switch has its rows reset to `Uncategorized`, because the rules
  that produced those labels are gone.

## Managing data

**Settings** -> **Data** (the gear at the right of the top nav, `/settings/data`) describes what this
machine currently holds and holds the two actions that rewrite it. Connecting stays on **Setup**, and
fetches of new postings stay on the dashboard's **Refresh**.

- The metadata panel reads `GET /api/status` on every visit and lists: **Connection**, **Source**
  (live or fixture), **Credential claimed**, **Accounts**, **Transactions**, **Last fetch** (with the
  error code when the last fetch failed, in red) and **Refresh** (allowed now, or when it is allowed
  next). A line under it states the minimum gap between refreshes.
- **Re-apply rules** re-runs every category rule over every stored transaction and reports how many
  rows moved. It reads local rows only, so it spends no SimpleFIN calls, and it works even when the
  app is disconnected.
- **Backfill 12 months** asks first, because it spends 5 of the 24 daily SimpleFIN calls, then
  refetches the last year in five windows. Existing transactions are updated in place, not duplicated.
  It is disabled with a link to **Setup** when no access URL is stored.
- Both actions report through a snackbar and disable themselves while running. They share one slot
  with **Refresh**, so a backfill running from this page also disables **Refresh** on the dashboard,
  and the reverse.
- Nothing is fetched on page load: the page only reads status. A fixture restart still leaves the app
  connected with zero rows, so backfill again.

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
| Empty after restart | Fixture reset cleared rows; run **Backfill 12 months** on **Settings -> Data** (the credential survives) |
| Refresh returns 429 | Refresh guard, wait for `next_refresh_allowed_at` |
| Startup fails on categories | `categories` table empty or missing `Uncategorized`, or a rule pointing at a category that does not exist |
| Money looks wrong for one account | The **Counts as cash** toggle |
| Uvicorn reloads in a loop | Reload watcher must stay scoped to `app` and `migrations` only |
