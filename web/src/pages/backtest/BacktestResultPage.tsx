import { useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router";
import { useMarkets, useResult } from "../../api/queries";
import type { BacktestResult, StrategyRun } from "../../api/types";
import { DrawdownChart, EquityChart, lineColors, RollingChart } from "../../components/charts/BacktestCharts";
import { LinkIcon } from "../../components/icons";
import { CountUp, DrawIn } from "../../components/motion";
import { Button, ButtonLink, Container, Hero, Kicker, Loading, Note, Section, Stat, StatStrip, Td, Th } from "../../components/ui";
import { day, decimal, ESTIMATOR_NAMES, money, percent, portfolioName, signedPercent } from "../../lib/format";
import { useColors } from "../../lib/theme";
import { useDraft } from "../../state/draft";

export function BacktestResultPage() {
  const { resultId = "" } = useParams();
  const result = useResult(resultId);
  if (result.error) {
    return (
      <Container className="py-20">
        <Note tone="warn" title="Couldn't open this backtest">{result.error.message}</Note>
        <ButtonLink to="/backtest" variant="primary" className="mt-8">Go to the backtest page</ButtonLink>
      </Container>
    );
  }
  if (!result.data) return <Container><Loading>Opening the backtest…</Loading></Container>;
  if (result.data.kind !== "backtest") return <Navigate to={`/results/${resultId}`} replace />;
  if (!result.data.backtest) return <Container className="py-20"><Note tone="bad" title="This backtest has no result">{result.data.error}</Note></Container>;
  return <Report run={result.data.backtest} />;
}

function Report({ run }: { run: BacktestResult }) {
  const markets = useMarkets();
  const navigate = useNavigate();
  const { setMarket } = useDraft();
  const [copied, setCopied] = useState(false);
  const marketName = markets.data?.markets.find((m) => m.id === run.market)?.name ?? run.market;
  const lead = run.strategies[0];
  const beat = lead.performance.cagr - run.benchmark.performance.cagr;
  const all = [...run.strategies, run.benchmark];

  return (
    <>
      <Hero speed={0.6}>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <Kicker onDark>{marketName} · {run.frequency} rebalancing · {ESTIMATOR_NAMES[run.method]}</Kicker>
          <div className="flex flex-wrap gap-2">
            <Button variant="onDark" onClick={() => {
              setMarket(run.market);
              navigate("/backtest");
            }}>New backtest</Button>
            <Button variant="onDark" onClick={async () => {
              await navigator.clipboard.writeText(location.href).catch(() => undefined);
              setCopied(true);
              setTimeout(() => setCopied(false), 2000);
            }}><LinkIcon />{copied ? "Link copied" : "Copy link"}</Button>
          </div>
        </div>
        <h1 className="mt-8 max-w-4xl font-serif text-4xl leading-[1.12] sm:text-[52px]">
          {money(run.capital, run.currency)} from {day(run.start)} would be {money(lead.values[lead.values.length - 1], run.currency)} today.
        </h1>
        <p className="mt-5 max-w-3xl leading-relaxed text-navy-muted">
          Following “{lead.name}”, after every trading cost. That is {percent(lead.performance.cagr)} a year, {beat >= 0 ? `${percent(beat)} a year more than` : `${percent(-beat)} a year less than`} the {run.benchmark.name}.
          Holding every stock in equal amounts did {percent(run.strategies.find((s) => s.name.startsWith("All"))?.performance.cagr ?? 0)} a year.
        </p>
        <StatStrip onDark className="mt-12 max-w-4xl">
          <Stat onDark highlight label="growth per year" value={<CountUp value={lead.performance.cagr} format={(v) => percent(v)} />} detail={lead.name} />
          <Stat onDark label="Sharpe ratio" value={<CountUp value={lead.performance.sharpe} format={(v) => decimal(v)} />} detail={`index: ${decimal(run.benchmark.performance.sharpe)}`} />
          <Stat onDark label="worst fall" value={<CountUp value={lead.performance.max_drawdown} format={(v) => percent(v)} />}
                detail={`${day(lead.performance.drawdown_start)} to ${day(lead.performance.drawdown_bottom)}`} />
          <Stat onDark label="trading costs" value={money(lead.costs, run.currency)} detail={`over ${lead.rebalances.length} rebalances`} />
        </StatStrip>
      </Hero>

      <Container className="pb-20">
        <Section number="01" title="The money over time" stacked
                 note={`${money(run.capital, run.currency)} at the start in each strategy and in the index (dotted). Switch to the log scale to compare growth rates fairly.`}>
          <DrawIn><EquityChart run={run} /></DrawIn>
        </Section>

        <Section number="02" title="Side by side" stacked note="Yearly figures over the whole period. Sharpe and Sortino use the market's risk-free rate; beta is against the index.">
          <MetricsTable run={run} />
        </Section>

        <Section number="03" title="The bad stretches" stacked note="How far each strategy was below its previous high, and its return or volatility over the past year at each point.">
          <DrawdownChart run={run} />
          <div className="mt-10"><RollingChart run={run} /></div>
        </Section>

        <Section number="04" title="Every rebalance" stacked note={`What the lead strategy held after each rebalance, how much of it changed, and what trading cost.`}>
          <Rebalances run={run} strategy={lead} />
        </Section>

        <Section number="05" title="Read this before trusting it" stacked>
          <ul className="space-y-3">
            {run.caveats.map((caveat) => <li key={caveat}><Note tone="warn">{caveat}</Note></li>)}
            <li><Note>Snapshot {run.snapshot}; {all.length - 1} strategies from {day(run.start)} to {day(run.end)}, estimating from the past {run.window_years} years at each step.</Note></li>
          </ul>
        </Section>
      </Container>
    </>
  );
}

function MetricsTable({ run }: { run: BacktestResult }) {
  const colors = useColors();
  const palette = lineColors(run, colors);
  const rows = [...run.strategies, run.benchmark];
  const best = Math.max(...rows.map((r) => r.performance.sharpe));
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-200 border-t border-ink text-sm">
        <thead className="border-b border-rule">
          <tr><Th>Strategy</Th><Th numeric>Growth / year</Th><Th numeric>Volatility</Th><Th numeric>Sharpe</Th><Th numeric>Sortino</Th>
            <Th numeric>Worst fall</Th><Th numeric>Worst 5% day</Th><Th numeric>Beta</Th><Th numeric>Costs</Th></tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.name} className="border-b border-rule">
              <Td className="text-ink">
                <span aria-hidden="true" className="mr-2 inline-block h-2 w-2 rounded-full" style={{ background: palette.get(row.name) }} />{row.name}
              </Td>
              <Td numeric className="text-ink">{percent(row.performance.cagr)}</Td>
              <Td numeric>{percent(row.performance.volatility)}</Td>
              <Td numeric className={row.performance.sharpe === best ? "font-medium text-good" : ""}>{decimal(row.performance.sharpe)}</Td>
              <Td numeric>{decimal(row.performance.sortino)}</Td>
              <Td numeric>{percent(row.performance.max_drawdown)}</Td>
              <Td numeric>{percent(-row.performance.var_95, 2)}</Td>
              <Td numeric>{row.performance.beta != null ? decimal(row.performance.beta) : "–"}</Td>
              <Td numeric>{row === run.benchmark ? "–" : money(row.costs, run.currency)}</Td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-3 text-xs text-muted">Worst 5% day: the daily loss exceeded on one day in twenty (value at risk). The index has no trading costs.</p>
    </div>
  );
}

function Rebalances({ run, strategy }: { run: BacktestResult; strategy: StrategyRun }) {
  const [all, setAll] = useState(false);
  const shown = all ? strategy.rebalances : strategy.rebalances.slice(-8);
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-170 border-t border-ink text-sm">
        <thead className="border-b border-rule"><tr><Th>Date</Th><Th>Held</Th><Th numeric>Traded</Th><Th numeric>Costs</Th></tr></thead>
        <tbody>
          {shown.map((r, i) => {
            const previous = strategy.rebalances[strategy.rebalances.indexOf(r) - 1];
            const kept = previous ? r.chosen.filter((t) => previous.chosen.includes(t)).length : 0;
            return (
              <tr key={`${r.date}-${i}`} className="border-b border-rule">
                <Td className="whitespace-nowrap text-ink">{day(r.date)}</Td>
                <Td className="font-mono text-xs text-ink-2">{portfolioName(r.chosen)}{previous && kept < r.chosen.length && <span className="ml-2 font-sans text-muted">({r.chosen.length - kept} new)</span>}</Td>
                <Td numeric>{signedPercent(r.turnover, 0).replace("+", "")}</Td>
                <Td numeric>{money(r.costs, run.currency, r.costs < 1000 ? 2 : 0)}</Td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {strategy.rebalances.length > 8 && (
        <button type="button" onClick={() => setAll(!all)} className="mt-3 text-sm text-accent hover:underline">
          {all ? "Show the latest 8" : `Show all ${strategy.rebalances.length} rebalances`}
        </button>
      )}
      <p className="mt-3 text-xs text-muted">Traded: the value bought plus the value sold, as a share of the portfolio, so swapping everything counts as 200%. The first rebalance buys everything.</p>
    </div>
  );
}
