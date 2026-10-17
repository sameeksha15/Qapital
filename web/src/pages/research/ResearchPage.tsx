import { useState, type ReactNode } from "react";
import { useNavigate } from "react-router";
import {
  useCircuits, useCovariance, useEqualQuality, useFamilies, useNoise, useOptimisers, type Circuits, type CircuitKey,
  type Covariance, type EqualQuality, type Families, type GridRun, type MarketKey, type Noise, type NoiseStage,
  type Optimisers, type RunInfo, type Scope, type Spread,
} from "../../api/research";
import { CostQualityChart } from "../../components/charts/CostQualityChart";
import { CountUp, DrawIn } from "../../components/motion";
import { SectionIndex } from "../../components/SectionIndex";
import { Button, Container, Fact, Hero, Kicker, Loading, Note, Section, Segmented, Stat, StatStrip, Td, Th } from "../../components/ui";
import { day, decimal, mixerName, percent, portfolioName, seconds, times, whole } from "../../lib/format";
import { useColors } from "../../lib/theme";
import { useDraft } from "../../state/draft";
import { SpreadBars, Tally } from "./charts";

const SECTIONS = [
  { id: "grid", label: "Gates or quality?" },
  { id: "equal", label: "Quality per gate" },
  { id: "cvar", label: "CVaR vs average" },
  { id: "warm", label: "Warm start" },
  { id: "noise", label: "On a noisy chip" },
  { id: "optimisers", label: "Optimisers" },
  { id: "covariance", label: "Pruning vs shrinkage" },
  { id: "all", label: "All circuits" },
  { id: "methods", label: "How these were run" },
];
const SCOPES: { value: Scope; label: string }[] = [
  { value: "all", label: "Both markets" },
  { value: "nifty50", label: "NIFTY 50" },
  { value: "sp100", label: "S&P 100" },
];
const MARKETS: { value: MarketKey; label: string }[] = [{ value: "nifty50", label: "NIFTY 50" }, { value: "sp100", label: "S&P 100" }];

const same = (a: CircuitKey, b: CircuitKey | null) => b != null && a.mixer === b.mixer && a.pairs_kept === b.pairs_kept && a.depth === b.depth;
const range = (s: Spread, show: (v: number) => string) => `${show(s.min)}–${show(s.max)}`;

/** Experiments on the current price snapshot, each over many dated problems (public/research/). */
export function ResearchPage() {
  const circuits = useCircuits();
  const equal = useEqualQuality();
  const families = useFamilies();
  const noise = useNoise();
  const optimisers = useOptimisers();
  const covariance = useCovariance();
  const [scope, setScope] = useState<Scope>("all");
  const all = [circuits, equal, families, noise, optimisers, covariance];
  const failed = all.find((q) => q.error);

  if (failed?.error) return <Container className="py-16"><Note tone="bad" title="Couldn't load the research results">{failed.error.message}</Note></Container>;
  if (!circuits.data || !equal.data || !families.data || !noise.data || !optimisers.data || !covariance.data) {
    return <Container><Loading>Loading research results…</Loading></Container>;
  }
  const scopeSwitch = <Segmented size="sm" label="Problems from" value={scope} onChange={setScope} options={SCOPES} />;

  return (
    <>
      <Headline circuits={circuits.data} equal={equal.data} families={families.data} noise={noise.data} />
      <Container className="pb-20">
        <div className="grid gap-x-12 lg:grid-cols-[180px_minmax(0,1fr)]">
          <SectionIndex sections={SECTIONS} />
          <div className="min-w-0">
            <GridSection circuits={circuits.data} />
            <EqualSection study={equal.data} scope={scope} scopeSwitch={scopeSwitch} />
            <CvarSection study={families.data} scope={scope} scopeSwitch={scopeSwitch} />
            <WarmSection study={families.data} scope={scope} scopeSwitch={scopeSwitch} />
            <NoiseSection study={noise.data} scope={scope} scopeSwitch={scopeSwitch} />
            <OptimiserSection study={optimisers.data} scope={scope} scopeSwitch={scopeSwitch} />
            <CovarianceSection study={covariance.data} scope={scope} scopeSwitch={scopeSwitch} />
            <AllCircuits circuits={circuits.data} />
            <Methods infos={[circuits.data.run_info, equal.data.run_info, families.data.run_info, noise.data.run_info, optimisers.data.run_info, covariance.data.run_info]}
                     problems={{ equal: equal.data.summary.all.problems, families: families.data.summary.all.problems, noise: noise.data.summary.all.problems,
                                 optimisers: optimisers.data.summary.all.problems, covariance: covariance.data.summary.all.problems }} />
          </div>
        </div>
      </Container>
    </>
  );
}

function Headline({ circuits, equal, families, noise }: { circuits: Circuits; equal: EqualQuality; families: Families; noise: Noise }) {
  const rows = equal.summary.all.rows;
  const at = (mixer: string, kept: number, depth = 2) => rows.find((r) => r.mixer === mixer && r.pairs_kept === kept && r.depth === depth);
  const xy = at("xy", 1);
  const penalty = at("standard", 1);
  const pruned = at("xy", 0.25);
  const cvar = families.summary.all.cvar_vs_average["xy p=2 α=0.25"];
  const fez = noise.summary.all.rows.find((r) => r.chip === "FakeFez" && r.mixer === "xy" && r.pairs_kept === 1 && r.depth === 2 && r.stocks === 10);
  const problems = families.summary.all.problems;
  return (
    <Hero>
      <Kicker onDark>Research · {problems} real problems · prices to {day(circuits.markets.nifty50.as_of)}</Kicker>
      <h1 className="mt-5 max-w-3xl font-serif text-4xl leading-[1.12] sm:text-[52px]">
        How you enforce the rules decides <em className="text-signal">how big the circuit is.</em>
      </h1>
      <p className="mt-6 max-w-2xl leading-relaxed text-navy-muted">
        Every experiment below ran on the problem the app would have solved at the start of each quarter since 2019, in
        both markets: estimates from the three years before, real trading costs, buy 4 with at most 1 per sector. Bars are
        means; whiskers run from the worst problem to the best.
      </p>
      <StatStrip onDark className="mt-12 max-w-4xl">
        {xy && penalty && (
          <Stat onDark highlight label="XY vs penalty, 2 layers" value={<CountUp value={xy.lift.mean / penalty.lift.mean} format={times} />}
                detail={`${times(xy.lift.mean)} vs ${times(penalty.lift.mean)} better than guessing (8 stocks)`} />
        )}
        {xy && pruned && (
          <Stat onDark label="fewer gates with 25% of links" value={<CountUp value={1 - pruned.gates.mean / xy.gates.mean} format={(v) => percent(v, 0)} />}
                detail={`still ${times(pruned.lift.mean)} better than guessing`} />
        )}
        {cvar && (
          <Stat onDark label="problems where CVaR beat the average" value={`${cvar.wins}/${cvar.wins + cvar.ties + cvar.losses}`}
                detail="XY, 2 layers, tuned for the best 25%" />
        )}
        {fez && (
          <Stat onDark label="recovered on a noisy chip" value={<CountUp value={fez.both_lift.mean} format={times} />}
                detail={`from ${times(fez.raw_lift.mean)} raw, with mitigation + the count check (IBM Fez)`} />
        )}
      </StatStrip>
    </Hero>
  );
}

function GridSection({ circuits }: { circuits: Circuits }) {
  const [market, setMarket] = useState<MarketKey>("nifty50");
  const info = circuits.markets[market];
  const runs = circuits.runs.filter((r) => r.market === market);
  const find = (mixer: string) => runs.find((r) => r.mixer === mixer && r.depth === 2 && r.pairs_kept === 1 && r.optimiser === "COBYLA");
  return (
    <Section id="grid" number="01" title="Fewer error-prone gates, or better answers?" stacked
             note={`Every circuit setting on today's ${info.name} problem, with the circuit's 16-stock shortlist. Higher means it lands on the best portfolio more often than guessing; further left means fewer two-qubit gates on a real chip's wiring. Use the filters to follow one family.`}>
      <Segmented size="sm" label="Market" value={market} onChange={setMarket} options={MARKETS} />
      <div className="mt-6"><CostQualityChart runs={runs} /></div>
      <dl className="mt-8 grid gap-x-10 gap-y-6 sm:grid-cols-2 xl:grid-cols-4">
        <Fact term="Best portfolio on the shortlist" value={portfolioName(info.shortlist_best)} detail={`of ${whole(info.legal_on_shortlist)} legal ones`} />
        <Fact term="Did the shortlist keep the full list's best?"
              value={info.best_kept == null ? "Can't check" : info.best_kept ? "Yes" : "No"}
              detail={info.true_best ? `the best of all ${info.stocks}: ${portfolioName(info.true_best)}` : `${info.stocks} stocks: too many portfolios to check`} />
        {(["xy", "standard"] as const).map((mixer) => {
          const run = find(mixer);
          return run && <Fact key={mixer} term={`${mixerName(mixer)}, 2 layers`} value={`${times(run.lift)} · ${whole(run.gates)} gates`} detail={run.found_best ? "found the shortlist's best" : "missed the shortlist's best"} />;
        })}
      </dl>
    </Section>
  );
}

function EqualSection({ study, scope, scopeSwitch }: { study: EqualQuality; scope: Scope; scopeSwitch: ReactNode }) {
  const summary = study.summary[scope];
  const rows = [...summary.rows].sort((a, b) => a.mixer.localeCompare(b.mixer) || b.pairs_kept - a.pairs_kept || a.depth - b.depth);
  const penalty = rows.find((r) => same(r, summary.best_penalty));
  const match = rows.find((r) => same(r, summary.cheapest_match));
  const best = rows.reduce((top, r) => (r.lift.mean > top.lift.mean ? r : top), rows[0]);
  const verdict = penalty && match
    ? `To match the best penalty circuit (${penalty.depth} layers: ${times(penalty.lift.mean)} at ${whole(penalty.gates.mean)} gates), the cheapest XY circuit (${percent(match.pairs_kept, 0)} of links, ${match.depth} layers) needed ${whole(match.gates.mean)} gates: ${
        match.gates.mean < penalty.gates.mean * 0.95 ? "fewer" : match.gates.mean > penalty.gates.mean * 1.05 ? "more" : "about the same"}. Past that point only XY keeps improving, up to ${times(best.lift.mean)}, and every one of its shots is legal.`
    : "";
  return (
    <Section id="equal" number="02" title="Quality per gate" stacked
             note={`8-stock shortlists of ${summary.problems} problems. The highlighted rows are the best penalty circuit and the cheapest XY circuit that matches its average. ${verdict}`}>
      {scopeSwitch}
      <div className="relative mt-6 overflow-x-auto">
        <table className="w-full min-w-180 border-t border-ink text-sm">
          <thead className="border-b border-rule">
            <tr><Th>Circuit</Th><Th numeric>Links kept</Th><Th numeric>Layers</Th><Th numeric>× random</Th><Th numeric>Range</Th>
              <Th numeric>Legal shots</Th><Th numeric>Closeness</Th><Th numeric>2-qubit gates</Th></tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const lit = same(row, summary.best_penalty) || same(row, summary.cheapest_match);
              return (
                <tr key={`${row.mixer}-${row.pairs_kept}-${row.depth}`} className={`border-b border-rule transition-colors hover:bg-paper-2 ${lit ? "bg-paper-2 font-medium" : ""}`}>
                  <Td className="text-ink">{lit && <span aria-hidden="true" className="mr-2 inline-block h-2 w-2 rounded-full bg-signal" />}{mixerName(row.mixer)}</Td>
                  <Td numeric>{percent(row.pairs_kept, 0)}</Td>
                  <Td numeric>{row.depth}</Td>
                  <Td numeric className="text-ink">{times(row.lift.mean)}</Td>
                  <Td numeric className="text-ink-2">{range(row.lift, times)}</Td>
                  <Td numeric>{percent(row.legal.mean)}</Td>
                  <Td numeric>{decimal(row.closeness.mean)}</Td>
                  <Td numeric className="text-ink">{whole(row.gates.mean)}</Td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="mt-3 text-xs text-muted">
          × random: how many times more often than a blind legal guess the circuit lands on the best portfolio. Closeness: 1 for the best portfolio, 0 for the worst, averaged over shots.
        </p>
      </div>
    </Section>
  );
}

const ALPHA_NAMES: Record<string, string> = { "1": "Average", "0.25": "Best 25% (CVaR)", "0.1": "Best 10% (CVaR)" };

function CvarSection({ study, scope, scopeSwitch }: { study: Families; scope: Scope; scopeSwitch: ReactNode }) {
  const colors = useColors();
  const [depth, setDepth] = useState(2);
  const summary = study.summary[scope];
  const mixers = ["standard", "xy", "warm"] as const;
  const alphas = [1, 0.25, 0.1];
  const palette = [colors.neutral, colors.series2, colors.series1];
  const at = (mixer: string, alpha: number) => summary.rows.find((r) => r.mixer === mixer && r.cvar_alpha === alpha && r.depth === depth);
  return (
    <Section id="cvar" number="03" title="Tune for the best outcomes, not the average" stacked
             note={`Only the best portfolio matters, so judging the circuit by its average outcome wastes effort on the bad ones. CVaR judges it by its best 25% or 10% of outcomes instead. 10-stock shortlists of ${summary.problems} problems.`}>
      <div className="flex flex-wrap gap-x-8 gap-y-3">
        {scopeSwitch}
        <Segmented size="sm" label="Layers" value={depth} onChange={setDepth} options={[1, 2, 3].map((d) => ({ value: d, label: String(d) }))} />
      </div>
      <DrawIn>
        <SpreadBars categories={mixers.map(mixerName)} title="times better than random guessing" format={(v) => v.toFixed(1)} suffix="×"
                    label={`Bar chart: lift over random guessing for each circuit, tuned for the average or for the best 25% or 10%, at ${depth} layers`}
                    reference={{ value: 1, label: "1×: luck" }}
                    series={alphas.map((alpha, i) => ({ name: ALPHA_NAMES[String(alpha)], color: palette[i], values: mixers.map((m) => at(m, alpha)?.lift) }))} />
      </DrawIn>
      <dl className="mt-8 grid gap-x-10 gap-y-6 sm:grid-cols-3">
        {mixers.map((mixer) => {
          const record = summary.cvar_vs_average[`${mixer} p=${depth} α=0.25`];
          const total = record ? record.wins + record.ties + record.losses : 0;
          return record && (
            <Fact key={mixer} term={`${mixerName(mixer)}: best 25% vs average`} value={<Tally wins={record.wins} total={total} of="problems better" />}
                  detail={`${record.losses} worse, ${record.ties} the same`} />
          );
        })}
      </dl>
    </Section>
  );
}

function WarmSection({ study, scope, scopeSwitch }: { study: Families; scope: Scope; scopeSwitch: ReactNode }) {
  const colors = useColors();
  const [alpha, setAlpha] = useState(0.25);
  const summary = study.summary[scope];
  const depths = [1, 2, 3];
  const at = (mixer: string, depth: number) => summary.rows.find((r) => r.mixer === mixer && r.cvar_alpha === alpha && r.depth === depth);
  const added = depths.map((d) => summary.warm_vs_warm_alone[`p=${d} α=${alpha}`]);
  const vsXy = depths.map((d) => summary.warm_vs_xy[`p=${d} α=${alpha}`]);
  return (
    <Section id="warm" number="04" title="Warm start: a head start from the classical answer" stacked
             note={`The warm-started circuit begins near the portfolio a classical relaxation suggests, instead of from all portfolios equally. The fair test is against that starting point alone: what did the quantum layers add? 10-stock shortlists of ${summary.problems} problems.`}>
      <div className="flex flex-wrap gap-x-8 gap-y-3">
        {scopeSwitch}
        <Segmented size="sm" label="Tuned for" value={alpha} onChange={setAlpha} options={[1, 0.25, 0.1].map((a) => ({ value: a, label: ALPHA_NAMES[String(a)] }))} />
      </div>
      <DrawIn>
        <SpreadBars categories={depths.map((d) => `${d} layer${d > 1 ? "s" : ""}`)} title="times better than random guessing" format={(v) => v.toFixed(1)} suffix="×"
                    label="Bar chart: the warm start alone, the warm-started circuit, the XY circuit and the penalty circuit, at 1 to 3 layers"
                    reference={{ value: 1, label: "1×: luck" }}
                    series={[
                      { name: "Warm start alone (no quantum layers)", color: colors.neutral, values: depths.map((d) => at("warm", d)?.warm_alone_lift) },
                      { name: "Warm-started circuit", color: colors.series3, values: depths.map((d) => at("warm", d)?.lift) },
                      { name: "XY circuit", color: colors.series2, values: depths.map((d) => at("xy", d)?.lift) },
                      { name: "Penalty circuit", color: colors.series1, values: depths.map((d) => at("standard", d)?.lift) },
                    ]} />
      </DrawIn>
      <dl className="mt-8 grid gap-x-10 gap-y-6 sm:grid-cols-3">
        {depths.map((d, i) => added[i] && (
          <Fact key={d} term={`${d} layer${d > 1 ? "s" : ""}: quantum layers improved the start`} value={<Tally wins={added[i].wins} total={added[i].problems} of="problems" />}
                detail={vsXy[i] ? `and beat the XY circuit on ${vsXy[i].wins}, lost on ${vsXy[i].losses}` : undefined} />
        ))}
      </dl>
    </Section>
  );
}

const STAGE_NAMES: Record<NoiseStage, string> = {
  ideal: "Perfect simulator", raw: "Noisy chip", mitigated: "+ readout mitigation", postselected: "+ count check", both: "+ both",
};
const CHIPS: Record<string, string> = { FakeBrisbane: "IBM Brisbane (older)", FakeFez: "IBM Fez (newer)" };

function NoiseSection({ study, scope, scopeSwitch }: { study: Noise; scope: Scope; scopeSwitch: ReactNode }) {
  const colors = useColors();
  const [stocks, setStocks] = useState(10);
  const [chip, setChip] = useState("FakeFez");
  const [depth, setDepth] = useState(2);
  const summary = study.summary[scope];
  const row = (mixer: string, kept: number) => summary.rows.find((r) => r.stocks === stocks && r.chip === chip && r.depth === depth && r.mixer === mixer && r.pairs_kept === kept);
  const penalty = row("standard", 1);
  const xy = row("xy", 1);
  const levels = [1, 0.75, 0.5, 0.25];
  const pruning = levels.map((kept) => row("xy", kept));
  return (
    <Section id="noise" number="05" title="On a noisy IBM chip" stacked
             note={`Each circuit is tuned on the perfect simulator, then run on a noisy copy of a real IBM chip. Readout mitigation measures how often the chip misreads each qubit and undoes it; the count check keeps only shots with exactly 4 stocks, which on the XY circuit can only be lost to a hardware error. ${summary.problems} problems.`}>
      <div className="flex flex-wrap gap-x-8 gap-y-3">
        {scopeSwitch}
        <Segmented size="sm" label="Shortlist" value={stocks} onChange={setStocks} options={[8, 10].map((s) => ({ value: s, label: `${s} stocks` }))} />
        <Segmented size="sm" label="Chip" value={chip} onChange={setChip} options={Object.keys(CHIPS).map((c) => ({ value: c, label: CHIPS[c] }))} />
        <Segmented size="sm" label="Layers" value={depth} onChange={setDepth} options={[1, 2].map((d) => ({ value: d, label: String(d) }))} />
      </div>
      {penalty && xy ? (
        <>
          <DrawIn>
            <SpreadBars categories={study.stages.map((s) => STAGE_NAMES[s])} title="times better than random guessing" format={(v) => v.toFixed(1)} suffix="×"
                        label="Bar chart: lift over random guessing on the perfect simulator, the noisy chip, and after mitigation and the count check, for the penalty and XY circuits"
                        reference={{ value: 1, label: "1×: luck" }}
                        series={[
                          { name: "Penalty circuit", color: colors.series1, values: study.stages.map((s) => penalty[`${s}_lift`]) },
                          { name: "XY circuit (keeps K)", color: colors.series2, values: study.stages.map((s) => xy[`${s}_lift`]) },
                        ]} />
          </DrawIn>
          <dl className="mt-6 grid gap-x-10 gap-y-6 sm:grid-cols-3">
            <Fact term="Readout errors on this chip" value={percent(xy.readout_error.mean, 1)} detail="average chance a qubit is misread" />
            <Fact term="XY shots that passed the count check" value={percent(xy.postselected_share.mean, 0)} detail={`penalty circuit: ${percent(penalty.postselected_share.mean, 0)}`} />
            <Fact term="Two-qubit gates" value={`${whole(xy.gates.mean)} vs ${whole(penalty.gates.mean)}`} detail="XY vs penalty, compiled for this chip" />
          </dl>
          <h3 className="mt-12 font-serif text-xl text-ink">Pruning under noise (XY circuit)</h3>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-2">
            Fewer links mean fewer gates, so fewer errors, but a rougher picture of the market.
            {pruning[0] && pruning[3] && ` Keeping a quarter of the links: on the perfect simulator ${times(pruning[0].ideal_lift.mean)} → ${times(pruning[3].ideal_lift.mean)}; on this noisy chip after mitigation and the count check ${times(pruning[0].both_lift.mean)} → ${times(pruning[3].both_lift.mean)}.`}
          </p>
          <SpreadBars categories={pruning.map((r, i) => `${percent(levels[i], 0)} · ${r ? whole(r.gates.mean) : "?"} gates`)} title="times better than random guessing"
                      format={(v) => v.toFixed(1)} suffix="×" height={300}
                      label="Bar chart: lift at 100, 75, 50 and 25% of links kept, on the perfect simulator, raw on the noisy chip, and with mitigation and the count check"
                      reference={{ value: 1, label: "1×" }}
                      series={[
                        { name: "Perfect simulator", color: colors.neutral, values: pruning.map((r) => r?.ideal_lift) },
                        { name: "Noisy chip, raw", color: colors.series1, values: pruning.map((r) => r?.raw_lift) },
                        { name: "Noisy, mitigated + count check", color: colors.series2, values: pruning.map((r) => r?.both_lift) },
                      ]} />
        </>
      ) : <Note>No runs for this combination.</Note>}
    </Section>
  );
}

function OptimiserSection({ study, scope, scopeSwitch }: { study: Optimisers; scope: Scope; scopeSwitch: ReactNode }) {
  const summary = study.summary[scope];
  const rows = [...summary.rows].sort((a, b) => a.depth - b.depth || a.optimiser.localeCompare(b.optimiser) || a.start.localeCompare(b.start));
  return (
    <Section id="optimisers" number="06" title="Which classical optimiser, from which start?" stacked
             note={`Our start tunes one layer at a time, each from the last layer's answer; a random start tunes all layers at once from random angles with the same maximum number of circuit runs (the table shows how many each actually used). XY circuit, 10-stock shortlists of ${summary.problems} problems, ${summary.seeds} seeds each.`}>
      {scopeSwitch}
      <div className="relative mt-6 overflow-x-auto">
        <table className="w-full min-w-170 border-t border-ink text-sm">
          <thead className="border-b border-rule">
            <tr><Th numeric>Layers</Th><Th>Optimiser</Th><Th>Start</Th><Th numeric>× random</Th><Th numeric>Range</Th><Th numeric>Circuit runs</Th><Th numeric>Time</Th></tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.depth}-${row.optimiser}-${row.start}`} className="border-b border-rule hover:bg-paper-2">
                <Td numeric>{row.depth}</Td><Td className="text-ink">{row.optimiser}</Td>
                <Td>{row.start === "warm" ? "Layer by layer" : "Random"}</Td>
                <Td numeric className="text-ink">{times(row.lift.mean)}</Td><Td numeric className="text-ink-2">{range(row.lift, times)}</Td>
                <Td numeric>{whole(row.circuit_runs.mean)}</Td><Td numeric>{seconds(row.seconds.mean)}</Td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Section>
  );
}

function CovarianceSection({ study, scope, scopeSwitch }: { study: Covariance; scope: Scope; scopeSwitch: ReactNode }) {
  const summary = study.summary[scope];
  return (
    <Section id="covariance" number="07" title="Pruning the risk model vs shrinking it" stacked
             note={`Pruning drops weak stock pairs to save gates; Ledoit-Wolf shrinkage (the app's default) pulls the noisy sample estimate towards a simpler one. Each quarter with a full year after it (${summary.problems} problems), the best portfolio was chosen with each risk model and then judged on the following year, which no estimate saw.`}>
      {scopeSwitch}
      <div className="relative mt-6 overflow-x-auto">
        <table className="w-full min-w-180 border-t border-ink text-sm">
          <thead className="border-b border-rule">
            <tr><Th>Risk model</Th><Th numeric>Error vs next year</Th><Th numeric>Next-year volatility</Th><Th numeric>Next-year return</Th><Th numeric>Sharpe</Th><Th numeric>Same pick as sample</Th></tr>
          </thead>
          <tbody>
            {summary.rows.map((row) => {
              const vs = summary.vs_sample[row.version];
              return (
                <tr key={row.version} className="border-b border-rule hover:bg-paper-2">
                  <Td className="text-ink">{row.version === "ledoit-wolf" ? "Ledoit-Wolf (default)" : row.version[0].toUpperCase() + row.version.slice(1)}</Td>
                  <Td numeric className="text-ink">{percent(row.covariance_error.mean, 0)}{vs && <span className="ml-1 text-xs text-muted">(lower on {vs.lower_error}/{vs.problems})</span>}</Td>
                  <Td numeric>{percent(row.next_year_volatility.mean)}</Td>
                  <Td numeric>{percent(row.next_year_return.mean)}</Td>
                  <Td numeric>{decimal(row.next_year_sharpe.mean)}</Td>
                  <Td numeric>{vs ? `${vs.same_portfolio}/${vs.problems}` : "–"}</Td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="mt-3 text-xs text-muted">
          Error vs next year: how far each risk model was from the covariance the following year actually showed (relative
          Frobenius distance; lower is better). Returns, volatility and Sharpe: the chosen 4 stocks with equal money over the next year, means over all problems.
        </p>
      </div>
    </Section>
  );
}

type Column = { label: string; value: (r: GridRun) => number | string; show: (r: GridRun) => ReactNode; numeric?: boolean };
const COLUMNS: Column[] = [
  { label: "Circuit", value: (r) => r.mixer, show: (r) => mixerName(r.mixer) },
  { label: "Layers", value: (r) => r.depth, show: (r) => r.depth, numeric: true },
  { label: "Links kept", value: (r) => r.pairs_kept, show: (r) => percent(r.pairs_kept, 0), numeric: true },
  { label: "Optimiser", value: (r) => r.optimiser, show: (r) => r.optimiser },
  { label: "Found best?", value: (r) => Number(r.found_best), show: (r) => (r.found_best ? "yes" : "no") },
  { label: "× random", value: (r) => r.lift, show: (r) => times(r.lift), numeric: true },
  { label: "Best shots", value: (r) => r.p_best, show: (r) => percent(r.p_best, 2), numeric: true },
  { label: "Legal shots", value: (r) => r.legal, show: (r) => percent(r.legal), numeric: true },
  { label: "2-qubit gates", value: (r) => r.gates, show: (r) => whole(r.gates), numeric: true },
  { label: "Time", value: (r) => r.seconds, show: (r) => seconds(r.seconds), numeric: true },
];

function AllCircuits({ circuits }: { circuits: Circuits }) {
  const { setSettings } = useDraft();
  const navigate = useNavigate();
  const [market, setMarket] = useState<MarketKey>("nifty50");
  const [sort, setSort] = useState({ column: 5, descending: true });
  const column = COLUMNS[sort.column];
  const sorted = circuits.runs.filter((r) => r.market === market).sort((x, y) => {
    const [a, b] = [column.value(x), column.value(y)];
    const order = a < b ? -1 : a > b ? 1 : 0;
    return sort.descending ? -order : order;
  });
  return (
    <Section id="all" number="08" title={`Every circuit on today's ${circuits.markets[market].name} problem`} stacked
             note="Select a column to sort. “Open” loads that circuit into the optimiser.">
      <Segmented size="sm" label="Market" value={market} onChange={setMarket} options={MARKETS} />
      <div className="relative mt-6 max-h-[640px] overflow-auto">
        <table className="w-full min-w-220 border-t border-ink text-sm">
          <thead className="sticky top-0 border-b border-rule bg-paper">
            <tr>
              {COLUMNS.map((col, i) => (
                <Th key={col.label} numeric={col.numeric}>
                  <button type="button" aria-sort={i === sort.column ? (sort.descending ? "descending" : "ascending") : "none"}
                          className={`hover:text-ink ${i === sort.column ? "text-ink" : ""}`}
                          onClick={() => setSort({ column: i, descending: i === sort.column ? !sort.descending : Boolean(col.numeric) })}>
                    {col.label}{i === sort.column ? (sort.descending ? " ↓" : " ↑") : ""}
                  </button>
                </Th>
              ))}
              <Th><span className="sr-only">Actions</span></Th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((run) => (
              <tr key={`${run.mixer}-${run.depth}-${run.pairs_kept}-${run.optimiser}`} className="group border-b border-rule hover:bg-paper-2">
                {COLUMNS.map((col) => <Td key={col.label} numeric={col.numeric} className="whitespace-nowrap text-ink">{col.show(run)}</Td>)}
                <Td>
                  <Button variant="ghost" size="sm" arrow className="opacity-60 group-hover:opacity-100 focus-visible:opacity-100" onClick={() => {
                    setSettings({ mixer: run.mixer, depth: run.depth, pairs_kept: run.pairs_kept, optimiser: run.optimiser, cvar_alpha: 0.25 });
                    navigate("/");
                  }}>Open</Button>
                </Td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Section>
  );
}

function Methods({ infos, problems }: { infos: RunInfo[]; problems: Record<string, number> }) {
  return (
    <Section id="methods" number="09" title="How these were run" stacked
             note="Every number on this page comes from these runs; the raw tables and the exact settings are saved with the code in research/results/.">
      <ul className="border-t border-ink text-sm">
        {infos.map((info, i) => (
          <li key={info.experiment} className="grid gap-x-6 gap-y-1 border-b border-rule py-3 sm:grid-cols-[minmax(0,1fr)_auto]">
            <span className="text-ink">{info.experiment}</span>
            <span className="text-xs text-ink-2 sm:text-right">
              {i === 0 ? "today's problem, both markets" : `${Object.values(problems)[i - 1]} problems`} · {info.minutes} min · Qiskit {info.qiskit}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-4 text-xs leading-relaxed text-muted">
        Snapshot {infos[0].snapshot}. {infos[0].estimates}. {infos[0].costs}. Shots: 4,096 per run. Gate counts: compiled for a fake
        IBM Brisbane chip. Rerun everything with <span className="font-mono">python -m research.experiments.run_all</span>.
      </p>
    </Section>
  );
}
