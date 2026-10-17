import type { Market } from "../api/types";

/** The markets as two large choices. */
export function MarketSwitch({ markets, value, onChange }: { markets: Market[]; value: string; onChange: (id: string) => void }) {
  return (
    <div role="radiogroup" aria-label="Market" className="grid gap-3 sm:grid-cols-2">
      {markets.map((market) => {
        const selected = market.id === value;
        return (
          <button key={market.id} type="button" role="radio" aria-checked={selected} onClick={() => onChange(market.id)}
                  className={`rounded-xl border p-4 text-left transition ${selected ? "border-ink bg-paper-2" : "border-rule hover:border-rule-strong"}`}>
            <span className="flex items-baseline justify-between gap-3">
              <span className="font-serif text-xl text-ink">{market.name}</span>
              <span className="font-mono text-xs text-muted">{market.currency}</span>
            </span>
            <span className="mt-1 block text-xs text-ink-2">{market.country} · {market.num_stocks} stocks · vs the {market.benchmark}</span>
          </button>
        );
      })}
    </div>
  );
}
