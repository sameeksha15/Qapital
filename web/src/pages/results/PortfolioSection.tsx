import { motion, useReducedMotion } from "motion/react";
import type { FullResult } from "../../api/types";
import { MarketMap, type MapGroup } from "../../components/charts/MarketMap";
import { EASE } from "../../components/motion";
import { Note, Section, Ticker } from "../../components/ui";
import { percent, portfolioName, sameStocks, shortName } from "../../lib/format";

const MAP_GROUPS: Record<string, MapGroup> = {
  rest: { name: "Other stocks", color: (c) => c.neutral, size: 7 },
  shortlist: { name: "On the circuit's shortlist", color: (c) => c.series1, size: 10 },
  qaoa: { name: "The circuit's pick", color: (c) => c.series3, size: 13, labelled: true },
  chosen: { name: "The portfolio", color: (c) => c.series2, size: 15, labelled: true },
};

/** The portfolio to hold: the best known one, which is the circuit's pick whenever the circuit found the best. */
export function PortfolioSection({ result }: { result: FullResult }) {
  const { quantum, optimal } = result;
  const reduce = useReducedMotion();
  const stocks = result.stocks ?? [];
  const info = new Map(stocks.map((s) => [s.ticker, s]));
  const portfolio = optimal?.best.stocks ?? quantum.chosen;
  const weights = result.allocations?.[0]?.weights ?? Object.fromEntries(portfolio.map((t) => [t, 1 / portfolio.length]));
  const chosen = new Set(portfolio);
  const circuitPick = new Set(quantum.chosen);
  const shortlist = new Set(quantum.shortlist ?? stocks.map((s) => s.ticker));
  const differs = !sameStocks(portfolio, quantum.chosen);

  return (
    <Section id="portfolio" number="01" title="The portfolio" stacked
             note={`${portfolio.length} stocks with equal money in each (a lowest-risk split is in the next section), shown among all the stocks: further right is bumpier, higher is more expected return.`}>
      {differs && (
        <div className="mb-8">
          <Note tone="warn" title="This is the best portfolio found, not the circuit's pick">
            The circuit picked {portfolioName(quantum.chosen)}, which scores lower. We'd buy the best portfolio any method
            found; the comparison below shows each method's pick.
          </Note>
        </div>
      )}
      <ol className="grid border-t border-ink sm:grid-cols-2 lg:grid-cols-4">
        {portfolio.map((ticker, i) => {
          const stock = info.get(ticker);
          const share = weights[ticker] ?? 1 / portfolio.length;
          return (
            <li key={ticker} className="border-b border-rule py-5 sm:pr-6 lg:border-b-0">
              <div className="flex items-baseline justify-between gap-3">
                <Ticker className="text-xl text-ink">{shortName(ticker)}</Ticker>
                <span className="font-serif text-lg tabular-nums text-ink-2">{percent(share, 0)}</span>
              </div>
              <p className="mt-0.5 truncate text-xs text-muted" title={stock?.name ?? undefined}>{stock?.name ?? ""}{stock?.name ? " · " : ""}{stock?.sector}</p>
              <div className="mt-3 h-0.5 bg-rule">
                <motion.div className="h-full bg-signal" initial={{ width: reduce ? `${100 * share}%` : 0 }} whileInView={{ width: `${100 * share}%` }}
                            viewport={{ once: true }} transition={{ duration: 1, ease: EASE, delay: 0.15 * i }} />
              </div>
              {stock?.expected_return != null && stock.volatility != null && (
                <p className="mt-3 text-sm tabular-nums text-ink-2">
                  <span className="text-ink">{percent(stock.expected_return)}</span> return · {percent(stock.volatility)} volatility
                </p>
              )}
            </li>
          );
        })}
      </ol>
      {stocks.length > 0 && (
        <div className="mt-10">
          <MarketMap stocks={stocks} groups={MAP_GROUPS} height={420}
                     groupOf={(t) => (chosen.has(t) ? "chosen" : circuitPick.has(t) ? "qaoa" : shortlist.has(t) ? "shortlist" : "rest")} />
        </div>
      )}
    </Section>
  );
}
