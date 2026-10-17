import { useMemo, useState } from "react";
import { useCorrelations, useDataStatus, useMarkets, useStocks } from "../../api/queries";
import type { StockInfo } from "../../api/types";
import { CorrelationChart } from "../../components/charts/CorrelationChart";
import { MarketSwitch } from "../../components/MarketSwitch";
import { DrawIn } from "../../components/motion";
import { Container, Fact, Hero, Kicker, Loading, Note, Section, Td, Th, Ticker } from "../../components/ui";
import { day, money, percent, shortName, years } from "../../lib/format";
import { useDraft } from "../../state/draft";

type SortKey = "ticker" | "sector" | "expected_return" | "volatility";

/** Where the numbers come from: the price snapshot, its quality checks, and what the estimates look like. */
export function DataPage() {
  const { draft, setMarket } = useDraft();
  const status = useDataStatus();
  const markets = useMarkets();
  const stocks = useStocks(draft.market);
  const correlations = useCorrelations(draft.market);
  const market = markets.data?.markets.find((m) => m.id === draft.market);
  const marketStatus = status.data?.markets.find((m) => m.id === draft.market);

  if (status.error || markets.error) return <Container className="py-16"><Note tone="bad" title="Couldn't load the data status">{(status.error ?? markets.error)?.message}</Note></Container>;
  if (!status.data || !markets.data || !market) return <Container><Loading>Loading the data status…</Loading></Container>;
  const snapshot = status.data.snapshot;

  return (
    <>
      <Hero speed={0.4}>
        <Kicker onDark>Data · snapshot {snapshot.id}</Kicker>
        <h1 className="mt-5 max-w-3xl font-serif text-4xl leading-[1.12] sm:text-[54px]">Real prices, checked every night.</h1>
        <p className="mt-6 max-w-2xl leading-relaxed text-navy-muted">
          A scheduled job downloads daily prices for every stock on both lists, checks them, and saves a dated, fingerprinted
          snapshot. The engine never calls a data provider itself: every run says which snapshot it used.
        </p>
      </Hero>

      <Container className="pb-20">
        <Section number="01" title="The snapshot in use" stacked>
          <dl className="grid gap-x-10 gap-y-6 sm:grid-cols-2 xl:grid-cols-4">
            <Fact term="Prices" value={`${day(snapshot.start)} – ${day(snapshot.end)}`} detail={snapshot.price_field} />
            <Fact term="Made" value={day(snapshot.created_at)} detail={`${status.data.available.length} snapshot${status.data.available.length > 1 ? "s" : ""} on the server`} />
            {status.data.markets.map((m) => (
              <Fact key={m.id} term={markets.data.markets.find((x) => x.id === m.id)?.name ?? m.id} value={`${m.usable} of ${m.stocks} stocks usable`} detail={`prices up to ${day(m.prices_as_of)}`} />
            ))}
          </dl>
        </Section>

        <Section number="02" title="One market at a time" stacked>
          <MarketSwitch markets={markets.data.markets} value={draft.market} onChange={setMarket} />
          <dl className="mt-8 grid gap-x-10 gap-y-6 sm:grid-cols-2 xl:grid-cols-3">
            <Fact term="Stock list" value={`${market.num_stocks} stocks, as of ${day(market.list_as_of)}`}
                  detail={<a href={market.list_source} target="_blank" rel="noreferrer" className="underline underline-offset-2 hover:text-ink">official list</a>} />
            <Fact term="Benchmark" value={market.benchmark} detail="what every backtest is compared with" />
            <Fact term="Risk-free rate" value={market.risk_free != null ? percent(market.risk_free, 2) : "–"} detail={market.risk_free_source?.replace(/https?:\/\/\S+/, "").replace(/[:,]\s*$/, "")} />
            <Fact term="Trading costs" value={market.cost_model} detail="charged on every order" />
          </dl>
          {marketStatus && Object.keys(marketStatus.problems).length > 0 && (
            <div className="mt-8">
              <h3 className="text-xs font-medium text-muted">What the quality checks noticed</h3>
              <ul className="mt-2 grid gap-x-8 gap-y-1.5 text-sm sm:grid-cols-2">
                {Object.entries(marketStatus.problems).map(([ticker, notes]) => (
                  <li key={ticker} className="flex gap-3 border-b border-rule py-1.5"><Ticker className="w-28 shrink-0 text-ink">{shortName(ticker)}</Ticker><span className="text-ink-2">{notes.join("; ")}</span></li>
                ))}
              </ul>
            </div>
          )}
        </Section>

        <Section number="03" title="How the stocks move together" stacked
                 note="Correlation of daily returns over the estimation window, grouped by sector. Stocks in the same sector usually move together, which is why the optimiser limits how many it takes from one sector.">
          {correlations.data ? <DrawIn><CorrelationChart correlations={correlations.data} height={Math.min(760, 220 + 11 * correlations.data.tickers.length)} /></DrawIn>
            : correlations.error ? <Note tone="bad">{correlations.error.message}</Note> : <Loading />}
        </Section>

        <Section number="04" title="Every stock" stacked
                 note={stocks.data?.estimation_window ? `Estimates from ${years(stocks.data.estimation_window)}, shrunk towards the middle (the optimiser's default). Select a column to sort.` : undefined}>
          {stocks.data ? <StockTable stocks={stocks.data.stocks} currency={market.currency} /> : <Loading />}
        </Section>
      </Container>
    </>
  );
}

function StockTable({ stocks, currency }: { stocks: StockInfo[]; currency: string }) {
  const [sort, setSort] = useState<{ key: SortKey; descending: boolean }>({ key: "expected_return", descending: true });
  const sorted = useMemo(() => [...stocks].sort((a, b) => {
    const x = a[sort.key] ?? -Infinity;
    const y = b[sort.key] ?? -Infinity;
    const order = typeof x === "string" ? String(x).localeCompare(String(y)) : (x as number) - (y as number);
    return sort.descending ? -order : order;
  }), [stocks, sort]);
  const header = (key: SortKey, label: string, numeric = false) => (
    <Th numeric={numeric}>
      <button type="button" className="hover:text-ink" aria-sort={sort.key === key ? (sort.descending ? "descending" : "ascending") : undefined}
              onClick={() => setSort({ key, descending: sort.key === key ? !sort.descending : numeric })}>
        {label}{sort.key === key ? (sort.descending ? " ↓" : " ↑") : ""}
      </button>
    </Th>
  );
  return (
    <div className="max-h-[640px] overflow-auto">
      <table className="w-full min-w-180 border-t border-ink text-sm">
        <thead className="sticky top-0 border-b border-rule bg-paper">
          <tr>{header("ticker", "Stock")}<Th>Name</Th>{header("sector", "Sector")}<Th numeric>Last price</Th>{header("expected_return", "Expected return", true)}{header("volatility", "Volatility", true)}</tr>
        </thead>
        <tbody>
          {sorted.map((stock) => (
            <tr key={stock.ticker} className={`border-b border-rule ${stock.excluded ? "text-muted" : ""}`}>
              <Td><Ticker className="text-ink">{shortName(stock.ticker)}</Ticker></Td>
              <Td className="max-w-56 truncate text-ink-2">{stock.name}</Td>
              <Td className="text-ink-2">{stock.sector}</Td>
              <Td numeric>{stock.price != null ? money(stock.price, currency, 2) : "–"}</Td>
              <Td numeric className="text-ink">{stock.expected_return != null ? percent(stock.expected_return) : <span title={stock.excluded ?? undefined}>not enough history</span>}</Td>
              <Td numeric>{stock.volatility != null ? percent(stock.volatility) : "–"}</Td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
