import type { Holding, StockInfo } from "../../api/types";
import { PlusIcon, TrashIcon } from "../../components/icons";
import { inputClass } from "../../components/ui";
import { money, shortName } from "../../lib/format";

interface HoldingsEditorProps {
  holdings: Holding[];
  stocks: StockInfo[];
  currency: string;
  onChange: (holdings: Holding[]) => void;
}

/** Shares the investor already owns. Keeping them avoids selling costs, so the optimiser favours them a little. */
export function HoldingsEditor({ holdings, stocks, currency, onChange }: HoldingsEditorProps) {
  const prices = new Map(stocks.map((stock) => [stock.ticker, stock.price ?? null]));
  const held = new Set(holdings.map((h) => h.ticker));
  const sorted = [...stocks].sort((a, b) => a.ticker.localeCompare(b.ticker));
  const set = (i: number, holding: Holding) => onChange(holdings.map((h, j) => (j === i ? holding : h)));
  const add = () => {
    const free = sorted.find((stock) => !held.has(stock.ticker) && stock.price != null);
    if (free) onChange([...holdings, { ticker: free.ticker, shares: 10 }]);
  };
  const total = holdings.reduce((sum, h) => sum + h.shares * (prices.get(h.ticker) ?? 0), 0);

  return (
    <div>
      <div className="mb-2 text-xs font-medium text-ink-2">Shares you already own</div>
      {holdings.length === 0 && <p className="text-sm text-muted">None. Add any you hold: selling them costs money, so keeping a good one can pay.</p>}
      <ul className="space-y-2">
        {holdings.map((holding, i) => {
          const price = prices.get(holding.ticker);
          return (
            <li key={`${holding.ticker}-${i}`} className="grid grid-cols-[minmax(0,1fr)_90px_auto] items-center gap-2 sm:grid-cols-[minmax(0,1fr)_100px_120px_auto]">
              <select aria-label="Stock" className={inputClass} value={holding.ticker}
                      onChange={(event) => set(i, { ...holding, ticker: event.target.value })}>
                {sorted.map((stock) => (
                  <option key={stock.ticker} value={stock.ticker} disabled={stock.ticker !== holding.ticker && held.has(stock.ticker)}>
                    {shortName(stock.ticker)}{stock.name ? ` · ${stock.name}` : ""}
                  </option>
                ))}
              </select>
              <input aria-label={`Shares of ${shortName(holding.ticker)}`} type="number" min={0} step={1} className={inputClass}
                     value={holding.shares} onChange={(event) => set(i, { ...holding, shares: Math.max(0, Math.floor(Number(event.target.value) || 0)) })} />
              <span className="hidden text-right text-sm tabular-nums text-ink-2 sm:block">
                {price != null ? money(holding.shares * price, currency) : "no price"}
              </span>
              <button type="button" aria-label={`Remove ${shortName(holding.ticker)}`} onClick={() => onChange(holdings.filter((_, j) => j !== i))}
                      className="rounded-full p-2 text-muted transition hover:bg-paper-2 hover:text-bad">
                <TrashIcon />
              </button>
            </li>
          );
        })}
      </ul>
      <div className="mt-3 flex items-center justify-between gap-4">
        <button type="button" onClick={add} className="inline-flex items-center gap-1.5 text-sm text-accent hover:underline">
          <PlusIcon />Add a holding
        </button>
        {holdings.length > 0 && <span className="text-sm text-ink-2">worth <span className="tabular-nums text-ink">{money(total, currency)}</span> today</span>}
      </div>
    </div>
  );
}
