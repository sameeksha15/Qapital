# Website

React 19 + TypeScript + Vite + Tailwind + Plotly, with React Router (real URLs) and TanStack Query (server data).
Pages: **Optimise** (`/`), a run's progress (`/runs/:id`), **results** (`/results/:id`), **Backtest** (`/backtest`,
`/backtest/:id`), **Data**, **History**, **Research** and **How it works**.

## Run it (from this folder)

    npm ci             # first time only; installs into web/node_modules
    npm run dev        # http://localhost:5173

With the API running too (from the repo root: `uvicorn qapital.api.main:create_app --factory --reload`), copy
`.env.example` to `.env.local`; it points the site at `http://localhost:8000`.

## Live engine, saved runs, and the switch between them

`VITE_API_URL` is the only setting. On load the site asks the API's `/health`:

- **live**: the API answers, so runs can start. Progress arrives as a live event stream (`/jobs/{id}/events`),
  falling back to polling if the stream breaks.
- **waking**: no answer yet (free hosting sleeps when idle). The site shows the **saved runs** and keeps asking for
  about four minutes, then switches to live by itself.
- **saved**: no API configured, or it stayed asleep. Saved runs only; "retry" in the header asks again.

Saved runs live in `public/saved/`: real runs on the current price snapshot, in exactly the API's shapes. Rebuild
them after a new snapshot (about 2 minutes, from the repo root): `python -m scripts.build_saved_site`.

## The contract with the API

The API's types are generated, never written by hand:

    python -m scripts.export_openapi   # repo root: the API's description → src/api/openapi.json
    npm run gen:api                    # → src/api/schema.d.ts (src/api/types.ts names the shapes)

CI fails if `schema.d.ts` is out of date, and a Python test fails if `openapi.json` is.

## Checks

    npm run typecheck   # TypeScript, strict
    npm test            # Vitest: helpers, the API client, components (jsdom)
    npm run e2e         # Playwright in the installed Edge: smoke tests on the saved runs
    E2E_API_URL=http://localhost:8000 npm run e2e   # plus a real run through a running API
    npm run build

## Where things are

    src/api/          types.ts (from the generated schema.d.ts), client.ts (live and saved clients, job following),
                      connection.tsx (live / waking / saved), queries.ts (TanStack hooks), research.ts, fetchJson.ts
    src/state/        draft.tsx (the optimise form, kept for the session), runs.ts (start and follow runs)
    src/lib/          format.ts, series.ts (drawdowns, rolling figures), history.ts (runs kept in this browser), theme.ts
    src/pages/        optimise/, results/, backtest/, data/, research/, how/, RunningPage, HistoryPage, Layout
    src/components/   ui.tsx, inputs.tsx, motion.tsx, WaveField, Header, StockPicker, MarketSwitch, SavedRuns,
                      charts/ (Plotly, loaded only on pages that draw charts)
    e2e/              Playwright tests
