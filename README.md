<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="ui/public/brand/penniless-horizontal-dark.svg">
    <img src="ui/public/brand/penniless-horizontal.png" alt="Penniless" width="420">
  </picture>
</p>

# Penniless

A local-only personal finance dashboard. It pulls read-only accounts and transactions from
[SimpleFIN](https://www.simplefin.org/), categorizes them with rules you teach it, and reports money
in, money out, and net for any period.

Nothing is hosted. The API binds `127.0.0.1`, has no authentication and no CORS, and account data
never leaves the machine except in the requests it makes to SimpleFIN.

## Stack

| Piece | Path | Stack |
| --- | --- | --- |
| API | `api/` | Python 3.12, FastAPI, SQLite through the stdlib `sqlite3`, `httpx`, uv, ruff, pyright |
| UI | `ui/` | Angular 22, standalone components, signals, zoneless, Angular Material 22 |
| Orchestration | root | `npm` with `concurrently`; no Nx, no workspaces, no container |

## Requirements

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- Node 20.19+ or 22.12+ and npm
- Optional: a SimpleFIN Bridge setup token, only for live mode

## Run it

```bash
npm run install:all      # root npm install, uv sync, ui npm install
npm run dev              # fixture mode: both processes, no network, no quota
```

The UI is at `http://127.0.0.1:4200` and the API at `http://127.0.0.1:8000`.

Fixture mode replays the hand-written SimpleFIN responses in `api/fixtures/`, so the app is fully
usable with fake data and without a SimpleFIN account: paste the demo setup token from
`api/fixtures/README.md` on the **Setup** page, then press **Backfill 12 months** on the
**Dashboard**. The fixture database is rebuilt on every startup, so accounts and transactions are
empty until you backfill again; the category rules you taught it survive.

Then categorize from the **Transactions** page: click a row, pick a keyword, pick a category, save.
Every transaction that keyword matches moves, including ones fetched later.

## Live mode

```bash
npm run dev:live         # real SimpleFIN, real database
```

SimpleFIN allows **24 `/accounts` calls per day** per access URL and every fetch spends one, so the
app never fetches on page load, never polls, and refuses a manual refresh for six hours after a
success. A 12-month backfill is five calls; a refresh is one. Read
[`api/fixtures/README.md`](api/fixtures/README.md) for the fixture format and the demo tokens.

## Other commands

| Command | What it does |
| --- | --- |
| `npm run dev:api` / `npm run dev:api:fixture` | API only |
| `npm run dev:ui` | UI only |
| `cd api && uv run pytest` | Python tests (pure functions plus the SQL-level category operations) |
| `cd api && uv run ruff check . && uv run ruff format --check . && uv run pyright` | Python checks |
| `cd ui && npx ng build` | UI typecheck plus bundle |
| `cd ui && npx prettier --check "src/**/*.{ts,html,scss,json}"` | UI formatting |

There is no UI test suite; UI correctness is verified by hand against fixture data.

## Layout

```
api/app/                          one package per entity, one folder per layer
  accounts/ categories/ fetches/ setup/ transactions/
  common/                         shared config, db, dates, money, errors, SimpleFIN client
  migrations/*.sql                the schema, applied in filename order at startup
  fixtures/                       fake SimpleFIN responses for fixture mode
ui/src/app/
  shared/api/<component>/         the wire models, one folder per backend component
  pages/ dialogs/ components/     setup, dashboard, transactions, settings/categories
docs/working-with-penniless.md    how to run it, manage state, and work on it
```

## Documentation

[`docs/working-with-penniless.md`](docs/working-with-penniless.md) covers running the app, the
files under `api/.data/`, quota discipline, how categories and rules work, migrations, and the
checks to run before committing.

## License

[MIT](LICENSE).
