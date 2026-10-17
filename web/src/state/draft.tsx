import { createContext, use, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import type { BacktestRequest, Holding, OptimiseRequest, Settings } from "../api/types";

/**
 * What the visitor is asking for, shared by the Optimise and Backtest pages and kept for the browser session, so
 * going to a result and back keeps the form as it was. `tickers` empty means the whole market.
 */
export type Draft = OptimiseRequest & { tickers: string[]; holdings: Holding[] };
export type BacktestDraft = BacktestRequest & { tickers: string[] };

export const DEFAULT_SETTINGS: Settings = {
  k: 4, risk_aversion: 1, sector_cap: 1, pairs_kept: 1, depth: 2, optimiser: "COBYLA", mixer: "xy", cvar_alpha: 0.25,
  noisy: false, mitigate_readout: true, run_pruning_study: false, seed: 42,
};

/** A round, typical amount for each market's currency. */
export const DEFAULT_CASH: Record<string, number> = { nifty50: 1_000_000, sp100: 100_000 };

export function defaultDraft(market = "nifty50"): Draft {
  return {
    market, tickers: [], settings: DEFAULT_SETTINGS, cash: DEFAULT_CASH[market] ?? 1_000_000, holdings: [],
    estimator: "shrunk-lw", window_years: 3, horizon_years: 1, as_of: null,
  };
}

/** The backtest of the same question: same market, stocks, settings and estimates; history from 2018. */
export function backtestOf(draft: Draft): BacktestDraft {
  return {
    market: draft.market, tickers: draft.tickers, settings: { ...draft.settings, noisy: false, run_pruning_study: false },
    start: "2018-01-01", end: null, frequency: "quarterly", capital: draft.cash > 0 ? draft.cash : DEFAULT_CASH[draft.market] ?? 1_000_000,
    estimator: draft.estimator, window_years: draft.window_years, horizon_years: draft.horizon_years, include_quantum: false,
  };
}

const KEY = "qapital.draft.v1";

function load(): Draft {
  try {
    const saved = sessionStorage.getItem(KEY);
    if (saved) {
      const draft = JSON.parse(saved) as Draft;
      return {
        ...defaultDraft(draft.market), ...draft, tickers: draft.tickers ?? [], holdings: draft.holdings ?? [],
        settings: { ...DEFAULT_SETTINGS, ...draft.settings },
      };
    }
  } catch {
    // storage unavailable or old format: start fresh
  }
  return defaultDraft();
}

interface DraftContextValue {
  draft: Draft;
  /** Load a request (e.g. from a result) into the form. */
  setDraft: (request: OptimiseRequest) => void;
  update: <K extends keyof Draft>(key: K, value: Draft[K]) => void;
  setSettings: (settings: Partial<Settings>) => void;
  /** Switch market: the stock list and holdings belong to the old market, so they are cleared. */
  setMarket: (market: string) => void;
}

const DraftContext = createContext<DraftContextValue | null>(null);

export function DraftProvider({ children }: { children: ReactNode }) {
  const [draft, setDraft] = useState<Draft>(load);

  useEffect(() => {
    try {
      sessionStorage.setItem(KEY, JSON.stringify(draft));
    } catch {
      // not saved: the form still works for this page view
    }
  }, [draft]);

  const update = useCallback(<K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((d) => ({ ...d, [key]: value })), []);
  const setSettings = useCallback((settings: Partial<Settings>) => setDraft((d) => ({ ...d, settings: { ...d.settings, ...settings } })), []);
  const setMarket = useCallback((market: string) => setDraft((d) => (d.market === market ? d : {
    ...d, market, tickers: [], holdings: [], cash: DEFAULT_CASH[market] ?? d.cash,
  })), []);

  const loadRequest = useCallback((request: OptimiseRequest) => setDraft({
    ...defaultDraft(request.market), ...request, tickers: request.tickers ?? [], holdings: request.holdings ?? [],
    settings: { ...DEFAULT_SETTINGS, ...request.settings },
  }), []);
  const value = useMemo(() => ({ draft, setDraft: loadRequest, update, setSettings, setMarket }), [draft, loadRequest, update, setSettings, setMarket]);
  return <DraftContext value={value}>{children}</DraftContext>;
}

export function useDraft(): DraftContextValue {
  const value = use(DraftContext);
  if (!value) throw new Error("useDraft needs a DraftProvider above it.");
  return value;
}
