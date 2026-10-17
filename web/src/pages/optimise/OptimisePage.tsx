import { useMemo, useState } from "react";
import { useConnection } from "../../api/connection";
import { useMarkets, useStocks } from "../../api/queries";
import { MAX_NOISY_QUBITS, MAX_QUBITS, type Settings } from "../../api/types";
import { MarketMap, type MapGroup } from "../../components/charts/MarketMap";
import { NumberInput, NumberStepper, RiskSlider } from "../../components/inputs";
import { MarketSwitch } from "../../components/MarketSwitch";
import { CountUp } from "../../components/motion";
import { SavedRuns } from "../../components/SavedRuns";
import { StockPicker } from "../../components/StockPicker";
import {
  Button, ButtonLink, Container, Field, Hero, inputClass, Kicker, Loading, Note, Row, Section, Segmented, Stat,
  StatStrip, Stepper, Toggle,
} from "../../components/ui";
import { day, describeCircuit, ESTIMATOR_NAMES, money, percent, shortName, years } from "../../lib/format";
import { useDraft } from "../../state/draft";
import { OPTIMISE_STAGES, useStartRun } from "../../state/runs";
import { HoldingsEditor } from "./HoldingsEditor";

const SELECTION_GROUPS: Record<string, MapGroup> = {
  in: { name: "In your list", color: (c) => c.series1, size: 10 },
  out: { name: "Left out", color: (c) => c.neutral, size: 8 },
};

const MIXERS: { value: Settings["mixer"]; label: string }[] = [
  { value: "xy", label: "XY (keeps K)" },
  { value: "standard", label: "Penalty" },
  { value: "warm", label: "Warm start" },
];

const MIXER_NOTES: Record<Settings["mixer"], string> = {
  xy: "Keeps exactly the number of stocks you want inside the circuit, so no fines are needed and pruning saves gates.",
  standard: "The textbook circuit: it has to learn the stock count from fines, which costs a gate on every pair of stocks.",
  warm: "Starts from the classical relaxation's answer instead of all portfolios equally; shown next to that start alone.",
};

export function OptimisePage() {
  const { draft, update, setSettings, setMarket } = useDraft();
  const { state } = useConnection();
  const markets = useMarkets();
  const stocks = useStocks(draft.market, draft.estimator, draft.window_years);
  const { start, starting, error, canStart } = useStartRun();
  const settings = draft.settings;
  const market = markets.data?.markets.find((m) => m.id === draft.market);

  // An empty list in the request means the whole market, so an emptied selection is kept here instead.
  const [cleared, setCleared] = useState(false);
  const usable = useMemo(() => (stocks.data?.stocks ?? []).filter((s) => !s.excluded), [stocks.data]);
  const selected = cleared ? [] : draft.tickers.length ? draft.tickers : usable.map((s) => s.ticker);
  const inList = new Set(selected);
  const prices = new Map((stocks.data?.stocks ?? []).map((s) => [s.ticker, s.price ?? 0]));
  const holdingsValue = draft.holdings.reduce((sum, h) => sum + h.shares * (prices.get(h.ticker) ?? 0), 0);
  const total = draft.cash + holdingsValue;
  const limit = settings.noisy ? MAX_NOISY_QUBITS : MAX_QUBITS;
  const problem = selected.length < 2 ? "Pick at least 2 stocks."
    : settings.k >= selected.length ? `Buy fewer than the ${selected.length} stocks in your list.`
    : total <= 0 ? "Enter some money to invest, or shares you already own." : null;

  const choose = (tickers: string[]) => {
    setCleared(tickers.length === 0);
    update("tickers", tickers.length === usable.length && usable.every((s) => tickers.includes(s.ticker)) ? [] : tickers);
  };
  const toggle = (ticker: string) => choose(inList.has(ticker) ? selected.filter((t) => t !== ticker) : [...selected, ticker]);
  const run = () => start("optimise", draft, {
    title: `${market?.name ?? draft.market}: ${settings.k} of ${selected.length} stocks`,
    market: draft.market,
    detail: `${money(total, market?.currency)} · ${describeCircuit(settings)}`,
    stages: OPTIMISE_STAGES.filter((stage) => (stage !== "Running on noisy chip" || settings.noisy)
      && (stage !== "Pruning study" || settings.run_pruning_study)),
  });

  if (markets.error || stocks.error) {
    return <Container className="py-16"><Note tone="bad" title="Couldn't load the market data">{(markets.error ?? stocks.error)?.message}</Note></Container>;
  }
  if (!markets.data || !stocks.data || !market) return <Container><Loading>Loading market data…</Loading></Container>;

  const sectors = new Set(usable.map((s) => s.sector)).size;
  return (
    <>
      <Hero>
        <Kicker onDark>Quantum portfolio selection · {market.name}</Kicker>
        <h1 className="mt-5 max-w-3xl font-serif text-4xl leading-[1.12] sm:text-[54px]">
          Pick a few stocks out of many with a quantum circuit, <em className="text-signal">and check it honestly.</em>
        </h1>
        <p className="mt-6 max-w-2xl leading-relaxed text-navy-muted">
          Choose a market, your money and your rules. A quantum circuit (QAOA) searches for the best few stocks; every answer
          is then compared with classical methods and with blind guessing, and turned into real orders with real costs.
        </p>
        <StatStrip onDark className="mt-12 max-w-4xl">
          <Stat onDark label="stocks with usable prices" value={<CountUp value={usable.length} format={(v) => String(Math.round(v))} />} />
          <Stat onDark label="sectors" value={<CountUp value={sectors} format={(v) => String(Math.round(v))} />} />
          <Stat onDark label="prices up to" value={day(market.prices_as_of).replace(/ \d{4}$/, "")} detail={market.prices_as_of.slice(0, 4)} />
          <Stat onDark label="qubits at most" value={<CountUp value={MAX_QUBITS} format={(v) => String(Math.round(v))} />} />
        </StatStrip>
      </Hero>

      <Container className="pb-20 pt-10">
        <Stepper steps={["Settings", "Run", "Results"]} current={0} />
        <div className="mt-4 grid gap-x-14 lg:grid-cols-[minmax(0,1fr)_300px]">
          <div className="min-w-0">
            <Section number="01" title="The market" stacked
                     note="Click dots on the map, or names below, to choose which stocks the optimiser may pick from. Higher is more expected return; further right is bumpier.">
              <MarketSwitch markets={markets.data.markets} value={draft.market} onChange={(id) => {
                setCleared(false);
                setMarket(id);
              }} />
              <div className="mt-6">
                <MarketMap stocks={stocks.data.stocks} groups={SELECTION_GROUPS} groupOf={(t) => (inList.has(t) ? "in" : "out")}
                           onToggle={toggle} height={340} />
              </div>
              <div className="mt-6"><StockPicker stocks={stocks.data.stocks} selected={selected} onChange={choose} /></div>
              {stocks.data.stocks.some((s) => s.excluded) && (
                <p className="mt-3 text-xs text-muted">Crossed-out stocks don't have enough price history in the estimation window.</p>
              )}
            </Section>

            <Section number="02" title="Your money" stacked
                     note={`Amounts in ${market.currency}. The result turns the portfolio into whole shares, with every trading charge from ${market.cost_model}.`}>
              <div className="grid gap-8 sm:grid-cols-2">
                <NumberInput label="Cash to invest" value={draft.cash} min={0} step={market.currency === "INR" ? 10000 : 1000}
                             prefix={market.currency === "INR" ? "₹" : "$"} onChange={(v) => update("cash", v)}
                             hint={`${money(draft.cash, market.currency)}${holdingsValue ? ` + holdings ${money(holdingsValue, market.currency)}` : ""}`} />
                <Segmented label="How long you plan to hold" value={draft.horizon_years} onChange={(v) => update("horizon_years", v)}
                           options={[0.5, 1, 2, 3].map((h) => ({ value: h, label: h < 1 ? "6 months" : `${h} year${h > 1 ? "s" : ""}` }))} />
              </div>
              <div className="mt-8">
                <HoldingsEditor holdings={draft.holdings} stocks={stocks.data.stocks} currency={market.currency}
                                onChange={(holdings) => update("holdings", holdings)} />
              </div>
            </Section>

            <Section number="03" title="Your rules" stacked note="How many stocks to buy, how much risk you accept, and how concentrated a sector may be.">
              <div className="grid gap-8 sm:grid-cols-2">
                <NumberStepper label="Stocks to buy" value={settings.k} min={1} max={Math.max(1, Math.min(8, selected.length - 1))}
                               onChange={(k) => setSettings({ k })} />
                <Segmented label="At most per sector" value={settings.sector_cap ?? null} onChange={(cap) => setSettings({ sector_cap: cap })}
                           options={[{ value: null, label: "No limit" }, ...[1, 2, 3].map((cap) => ({ value: cap as number | null, label: String(cap) }))]} />
                <div className="sm:col-span-2"><RiskSlider value={settings.risk_aversion} onChange={(risk_aversion) => setSettings({ risk_aversion })} /></div>
              </div>
            </Section>

            <Section number="04" title="The estimates" stacked
                     note="Expected returns and risks come from past daily prices. Raw averages over-trust last year's winners; shrinkage pulls them towards the middle.">
              <div className="grid gap-8 sm:grid-cols-2">
                <div className="sm:col-span-2">
                  <Segmented label="Method" value={draft.estimator} onChange={(v) => update("estimator", v)}
                             options={(Object.keys(ESTIMATOR_NAMES) as (keyof typeof ESTIMATOR_NAMES)[]).map((m) => ({ value: m, label: ESTIMATOR_NAMES[m] }))} />
                </div>
                <Segmented label="Years of past prices" value={draft.window_years} onChange={(v) => update("window_years", v)}
                           options={[1, 2, 3, 5].map((y) => ({ value: y, label: `${y}` }))} />
                <Field label="Use prices up to (optional)" htmlFor="as-of"
                       hint={draft.as_of ? "Rewinds the market to this day: no later price is used." : `Default: the latest, ${day(market.prices_as_of)}.`}>
                  <input id="as-of" type="date" className={inputClass} value={draft.as_of ?? ""} max={market.prices_as_of} min="2016-01-01"
                         onChange={(event) => update("as_of", event.target.value || null)} />
                </Field>
              </div>
              {stocks.data.estimation_window && (
                <p className="mt-6 text-xs text-muted">The map shows estimates from {years(stocks.data.estimation_window)} ({stocks.data.estimation_window[0]} to {stocks.data.estimation_window[1]}).</p>
              )}
            </Section>

            <Section number="05" title="The circuit" stacked note={MIXER_NOTES[settings.mixer]}>
              <div className="grid gap-8 sm:grid-cols-2">
                <Segmented label="Circuit" value={settings.mixer} onChange={(mixer) => setSettings({ mixer })} options={MIXERS} />
                <Segmented label="Layers" value={settings.depth} onChange={(depth) => setSettings({ depth })}
                           options={[1, 2, 3, 4].map((d) => ({ value: d, label: String(d) }))} />
                <Segmented label="Tune for" value={settings.cvar_alpha} onChange={(cvar_alpha) => setSettings({ cvar_alpha })}
                           options={[{ value: 0.1, label: "Best 10%" }, { value: 0.25, label: "Best 25%" }, { value: 0.5, label: "Best 50%" }, { value: 1, label: "Average" }]} />
                <Segmented label="Stock links kept (pruning)" value={settings.pairs_kept} onChange={(pairs_kept) => setSettings({ pairs_kept })}
                           options={[1, 0.75, 0.5, 0.25].map((p) => ({ value: p, label: percent(p, 0) }))} />
                <Segmented label="Optimiser" value={settings.optimiser} onChange={(optimiser) => setSettings({ optimiser })}
                           options={(["COBYLA", "SPSA"] as const).map((o) => ({ value: o, label: o }))} />
                <NumberInput label="Seed" value={settings.seed} min={0} max={1_000_000} onChange={(seed) => setSettings({ seed })}
                             hint="Same settings and seed give the same result." />
              </div>
              <p className="mt-4 text-xs leading-relaxed text-muted">
                “Tune for the best 25%” (CVaR) judges the circuit by its best quarter of outcomes rather than the average,
                which suits a search where only the best answer matters.
              </p>
              <div className="mt-8 grid gap-5 border-t border-rule pt-6 sm:grid-cols-2">
                <Toggle label="Also run on a noisy IBM chip" checked={settings.noisy} onChange={(noisy) => setSettings({ noisy })}
                        note={`A copy of a real chip's errors. At most ${MAX_NOISY_QUBITS} stocks; counts toward the slower-run limit.`} />
                <Toggle label="Undo readout errors (mitigation)" checked={settings.mitigate_readout} disabled={!settings.noisy}
                        onChange={(mitigate_readout) => setSettings({ mitigate_readout })} note="Measures how often the chip misreads each qubit and corrects for it." />
                <Toggle label="Pruning study (100% → 25% links)" checked={settings.run_pruning_study}
                        onChange={(run_pruning_study) => setSettings({ run_pruning_study })} note="Takes a few minutes; counts toward the slower-run limit." />
              </div>
            </Section>
          </div>

          <aside className="border-t border-rule pt-12 lg:sticky lg:top-24 lg:self-start lg:border-l lg:border-t-0 lg:pl-8">
            <Kicker>Ready to run</Kicker>
            <p className="mt-2 font-serif text-xl leading-snug text-ink">{describeCircuit(settings)}</p>
            <dl className="mt-6 space-y-2.5 text-sm">
              <Row term="Market" value={market.name} />
              <Row term="Buy" value={`${settings.k} of ${selected.length} stocks`} />
              <Row term="Per sector" value={settings.sector_cap == null ? "no limit" : `at most ${settings.sector_cap}`} />
              <Row term="Money" value={money(total, market.currency)} />
              {draft.holdings.length > 0 && <Row term="Holdings" value={draft.holdings.map((h) => shortName(h.ticker)).join(", ")} />}
              <Row term="Prices up to" value={draft.as_of ? day(draft.as_of) : "latest"} />
            </dl>
            {selected.length > limit && (
              <p className="mt-5 text-xs leading-relaxed text-muted">
                More than {limit} stocks: the circuit gets a {limit}-stock shortlist (each sector's best first). Classical methods
                still search the whole list, and the result says what the shortlist cost.
              </p>
            )}
            <Button variant="primary" arrow className="mt-7 w-full" disabled={Boolean(problem) || !canStart || starting} onClick={run}>
              {starting ? "Starting…" : "Run optimisation"}
            </Button>
            <ButtonLink to="/backtest" variant="ghost" className="mt-2 w-full">Backtest these settings</ButtonLink>
            <div className="mt-6 space-y-4">
              {problem && <Note tone="bad">{problem}</Note>}
              {error && <Note tone="bad" title="The run didn't start">{error}</Note>}
              {state === "waking" && <Note tone="warn" title="The live engine is waking up">The free server sleeps when nobody uses it and takes a minute or two to start. Meanwhile, open a saved run below.</Note>}
              {state === "saved" && <Note title="Saved runs only">The live engine isn't reachable right now. These saved runs are real results on the same prices.</Note>}
            </div>
            <div className="mt-8">
              <Kicker>Saved runs</Kicker>
              <div className="mt-3"><SavedRuns kind="optimise" compact /></div>
            </div>
          </aside>
        </div>
      </Container>
    </>
  );
}
