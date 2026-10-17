import { useState } from "react";
import { Link } from "react-router";
import { useConnection } from "../../api/connection";
import { useMarkets } from "../../api/queries";
import { NumberInput, NumberStepper } from "../../components/inputs";
import { MarketSwitch } from "../../components/MarketSwitch";
import { SavedRuns } from "../../components/SavedRuns";
import { Button, Container, Field, Hero, inputClass, Kicker, Loading, Note, Row, Section, Segmented, Toggle } from "../../components/ui";
import { day, ESTIMATOR_NAMES, money } from "../../lib/format";
import { backtestOf, DEFAULT_CASH, useDraft, type BacktestDraft } from "../../state/draft";
import { useStartRun } from "../../state/runs";

const FREQUENCIES = [
  { value: "monthly" as const, label: "Monthly" },
  { value: "quarterly" as const, label: "Quarterly" },
  { value: "yearly" as const, label: "Yearly" },
];

/** Replay the strategy through history: at every rebalance only the prices known that day are used. */
export function BacktestPage() {
  const { draft, setMarket } = useDraft();
  const { state } = useConnection();
  const markets = useMarkets();
  const { start, starting, error, canStart } = useStartRun();
  const [request, setRequest] = useState<BacktestDraft>(() => backtestOf(draft));
  const set = <K extends keyof BacktestDraft>(key: K, value: BacktestDraft[K]) => setRequest((r) => ({ ...r, [key]: value }));
  const setSettings = (settings: Partial<BacktestDraft["settings"]>) => setRequest((r) => ({ ...r, settings: { ...r.settings, ...settings } }));
  const market = markets.data?.markets.find((m) => m.id === request.market);
  const switchMarket = (id: string) => {
    setMarket(id);
    setRequest((r) => ({ ...r, market: id, tickers: [], capital: DEFAULT_CASH[id] ?? r.capital }));
  };
  const problem = request.end && request.end <= request.start ? "The end date must come after the start." : null;

  if (markets.error) return <Container className="py-16"><Note tone="bad" title="Couldn't load the markets">{markets.error.message}</Note></Container>;
  if (!markets.data || !market) return <Container><Loading>Loading markets…</Loading></Container>;

  const run = () => start("backtest", request, {
    title: `${market.name} backtest, ${request.start.slice(0, 4)} to ${request.end?.slice(0, 4) ?? "now"}`,
    market: request.market,
    detail: `${request.settings.k} stocks · ${request.frequency} · ${money(request.capital, market.currency)}`,
  });

  return (
    <>
      <Hero speed={0.6}>
        <Kicker onDark>Walk-forward backtest · {market.name}</Kicker>
        <h1 className="mt-5 max-w-3xl font-serif text-4xl leading-[1.12] sm:text-[54px]">
          What if you had followed it since 2018? <em className="text-signal">Without peeking.</em>
        </h1>
        <p className="mt-6 max-w-2xl leading-relaxed text-navy-muted">
          At every rebalance the strategy sees only the prices known that day, picks its stocks, and trades whole shares
          with real costs. The result is set against the index and an equal split of every stock.
        </p>
      </Hero>

      <Container className="pb-20 pt-10">
        <div className="grid gap-x-14 lg:grid-cols-[minmax(0,1fr)_300px]">
          <div className="min-w-0">
            <Section number="01" title="The market" stacked
                     note={request.tickers.length ? `${request.tickers.length} stocks from your optimiser list.` : "Every stock in the market that has enough history at each rebalance."}>
              <MarketSwitch markets={markets.data.markets} value={request.market} onChange={switchMarket} />
              {request.tickers.length > 0 && (
                <button type="button" className="mt-4 text-sm text-accent hover:underline" onClick={() => set("tickers", [])}>Use the whole market instead</button>
              )}
            </Section>

            <Section number="02" title="The strategy" stacked note="The same rules as the optimiser: how many stocks, how much risk, how many per sector.">
              <div className="grid gap-8 sm:grid-cols-2">
                <NumberStepper label="Stocks to hold" value={request.settings.k} min={1} max={8} onChange={(k) => setSettings({ k })} />
                <Segmented label="At most per sector" value={request.settings.sector_cap ?? null} onChange={(sector_cap) => setSettings({ sector_cap })}
                           options={[{ value: null, label: "No limit" }, ...[1, 2, 3].map((cap) => ({ value: cap as number | null, label: String(cap) }))]} />
                <Segmented label="Rebalance" value={request.frequency} onChange={(v) => set("frequency", v)} options={FREQUENCIES} />
                <Segmented label="Years of past prices at each step" value={request.window_years} onChange={(v) => set("window_years", v)}
                           options={[1, 2, 3, 5].map((y) => ({ value: y, label: String(y) }))} />
                <div className="sm:col-span-2">
                  <Segmented label="Estimates" value={request.estimator} onChange={(v) => set("estimator", v)}
                             options={(Object.keys(ESTIMATOR_NAMES) as (keyof typeof ESTIMATOR_NAMES)[]).map((m) => ({ value: m, label: ESTIMATOR_NAMES[m] }))} />
                </div>
              </div>
              <div className="mt-8 border-t border-rule pt-6">
                <Toggle label="Also run QAOA at every rebalance" checked={request.include_quantum} onChange={(v) => set("include_quantum", v)}
                        note="Adds a quantum strategy next to the classical best. Slow: several minutes; counts toward the slower-run limit." />
              </div>
            </Section>

            <Section number="03" title="Period and money" stacked>
              <div className="grid gap-8 sm:grid-cols-3">
                <Field label="Start" htmlFor="bt-start" hint="Needs the estimation window before it.">
                  <input id="bt-start" type="date" className={inputClass} value={request.start} min="2016-01-01" max={market.prices_as_of}
                         onChange={(event) => event.target.value && set("start", event.target.value)} />
                </Field>
                <Field label="End" htmlFor="bt-end" hint={`Default: ${day(market.prices_as_of)}`}>
                  <input id="bt-end" type="date" className={inputClass} value={request.end ?? ""} min={request.start} max={market.prices_as_of}
                         onChange={(event) => set("end", event.target.value || null)} />
                </Field>
                <NumberInput label="Starting money" value={request.capital} min={1000} step={market.currency === "INR" ? 100000 : 10000}
                             prefix={market.currency === "INR" ? "₹" : "$"} onChange={(v) => set("capital", v)} hint={money(request.capital, market.currency)} />
              </div>
            </Section>
          </div>

          <aside className="border-t border-rule pt-12 lg:sticky lg:top-24 lg:self-start lg:border-l lg:border-t-0 lg:pl-8">
            <Kicker>Ready to backtest</Kicker>
            <dl className="mt-4 space-y-2.5 text-sm">
              <Row term="Market" value={market.name} />
              <Row term="Hold" value={`${request.settings.k} stocks`} />
              <Row term="Rebalance" value={request.frequency} />
              <Row term="From" value={day(request.start)} />
              <Row term="To" value={request.end ? day(request.end) : "latest"} />
              <Row term="Strategies" value={request.include_quantum ? "4 + index" : "3 + index"} />
            </dl>
            <Button variant="primary" arrow className="mt-7 w-full" disabled={Boolean(problem) || !canStart || starting} onClick={run}>
              {starting ? "Starting…" : "Run backtest"}
            </Button>
            <div className="mt-6 space-y-4">
              {problem && <Note tone="bad">{problem}</Note>}
              {error && <Note tone="bad" title="The backtest didn't start">{error}</Note>}
              {state !== "live" && <Note tone="warn" title="Saved backtests only, for now">{state === "waking" ? "The live engine is waking up." : "The live engine isn't reachable."} These saved backtests are real runs:</Note>}
            </div>
            <div className="mt-6">
              <SavedRuns kind="backtest" compact />
            </div>
            <p className="mt-6 text-xs leading-relaxed text-muted">
              Want the quantum circuit's pick for today instead? <Link to="/" className="underline underline-offset-2 hover:text-ink">Run the optimiser</Link>.
            </p>
          </aside>
        </div>
      </Container>
    </>
  );
}
