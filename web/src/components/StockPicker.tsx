import { useMemo, useState } from "react";
import type { StockInfo } from "../api/types";
import { percent, shortName } from "../lib/format";
import { SearchIcon } from "./icons";

interface StockPickerProps {
  stocks: StockInfo[];
  selected: string[];
  onChange: (tickers: string[]) => void;
  locked?: boolean;
}

/** Stocks grouped by sector as toggle chips, with a search box. Stocks that can't be used are shown but disabled. */
export function StockPicker({ stocks, selected, onChange, locked = false }: StockPickerProps) {
  const [query, setQuery] = useState("");
  const chosen = new Set(selected);
  const groups = useMemo(() => {
    const bySector = new Map<string, StockInfo[]>();
    for (const stock of stocks) bySector.set(stock.sector, [...(bySector.get(stock.sector) ?? []), stock]);
    return [...bySector.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [stocks]);
  const matches = (stock: StockInfo) => `${stock.ticker} ${stock.name ?? ""} ${stock.sector}`.toLowerCase().includes(query.trim().toLowerCase());

  function toggle(ticker: string) {
    onChange(chosen.has(ticker) ? selected.filter((t) => t !== ticker) : [...selected, ticker]);
  }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-rule pb-3">
        <label className="relative flex w-full max-w-xs items-center">
          <span className="sr-only">Search stocks</span>
          <SearchIcon className="pointer-events-none absolute left-0 h-4 w-4 text-muted" />
          <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search a name, ticker or sector"
                 className="w-full bg-transparent py-1.5 pl-6 text-sm text-ink placeholder:text-muted focus:outline-none" />
        </label>
        {!locked && (
          <div className="flex gap-4 text-sm">
            <button type="button" className="text-accent hover:underline" onClick={() => onChange(stocks.filter((s) => !s.excluded).map((s) => s.ticker))}>Select all</button>
            <button type="button" className="text-accent hover:underline" onClick={() => onChange([])}>Clear</button>
          </div>
        )}
      </div>
      <div className="max-h-90 overflow-y-auto pr-1">
        {groups.map(([sector, members]) => {
          const shown = members.filter(matches);
          if (!shown.length) return null;
          return (
            <div key={sector} className="grid gap-x-6 gap-y-2 border-b border-rule py-3 sm:grid-cols-[200px_minmax(0,1fr)]">
              <p className="pt-1 text-xs text-muted">
                {sector} <span className="tabular-nums">· {members.filter((s) => chosen.has(s.ticker)).length}/{members.length}</span>
              </p>
              <div className="flex flex-wrap gap-1.5">
                {shown.map((stock) => {
                  const on = chosen.has(stock.ticker);
                  const title = stock.excluded ? `${stock.name ?? stock.ticker}: can't be used (${stock.excluded})`
                    : `${stock.name ?? stock.ticker}${stock.expected_return != null ? ` · ${percent(stock.expected_return)} expected return per year` : ""}`;
                  return (
                    <button key={stock.ticker} type="button" disabled={locked || Boolean(stock.excluded)} aria-pressed={on}
                            onClick={() => toggle(stock.ticker)} title={title}
                            className={`rounded-full border px-2.5 py-1 font-mono text-xs transition-colors disabled:cursor-default ${stock.excluded ? "line-through opacity-50 " : ""}${
                              on ? "border-ink bg-ink text-paper" : "border-rule-strong text-ink-2 enabled:hover:border-ink enabled:hover:text-ink"
                            }`}>
                      {shortName(stock.ticker)}
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
