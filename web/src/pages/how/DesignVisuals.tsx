import { AnimatePresence, motion } from "motion/react";
import { CheckIcon, CrossIcon } from "../../components/icons";
import { EASE } from "../../components/motion";
import type { Circuits, GridRun } from "../../api/research";
import { SHOTS } from "../../api/types";
import { percent, times, whole } from "../../lib/format";
import { Explainer, useTicker } from "./Explainer";
import { allPairs, choose, circlePoints, ones, strength } from "./illustration";

const COMPARE = { depth: 2, optimiser: "COBYLA", market: "nifty50" } as const;

/** The research run on today's NIFTY 50 problem with these settings (2 layers, COBYLA unless given). */
function findRun(grid: Circuits, mixer: string, pairsKept: number, depth: number = COMPARE.depth): GridRun {
  const run = grid.runs.find((r) => r.market === COMPARE.market && r.mixer === mixer && r.depth === depth
    && r.pairs_kept === pairsKept && r.optimiser === COMPARE.optimiser);
  if (!run) throw new Error(`The research results have no ${mixer} run with ${pairsKept} of links kept.`);
  return run;
}

function range(grid: Circuits, mixer: string, pick: (run: GridRun) => number): [number, number] {
  const values = grid.runs.filter((run) => run.market === COMPARE.market && run.mixer === mixer).map(pick);
  return [Math.min(...values), Math.max(...values)];
}

/* ------------------------------------------------------------------ 5. The rule as a fine */

export function FineExplainer({ grid }: { grid: Circuits }) {
  const penalty = findRun(grid, "standard", 1);
  const xy = findRun(grid, "xy", 1);
  const [low, high] = range(grid, "standard", (run) => run.legal);
  const n = grid.markets.nifty50.shortlist.length;
  const steps = [
    { title: "“Buy exactly 4” becomes a fine",
      text: "The standard circuit can output any number of stocks. The rule is added to the score as a fine, λ(x₁ + … + xₙ − 4)²: zero at exactly 4 stocks, growing fast either side." },
    { title: "Expand the square",
      text: "A switch is 0 or 1, so xᵢ² = xᵢ. The square splits into a part for each stock and a term 2λ·xᵢxⱼ for every pair of stocks." },
    { title: "A gate for every pair",
      text: `Each pair term needs a two-qubit gate: 28 on 8 qubits, ${choose(n, 2)} on our run's ${n}, whatever the data says. Pruning can't remove them; the fine needs them all.` },
    { title: "And the circuit has to learn the rule",
      text: `Its effort goes into legality. Same problem, 2 layers, all links: ${percent(penalty.legal)} of the penalty circuit's shots were legal, against ${percent(xy.legal)} for ours. Across all ${grid.runs.filter((r) => r.market === COMPARE.market && r.mixer === "standard").length} penalty runs: ${percent(low, 0)} to ${percent(high, 0)}.` },
  ];
  return (
    <Explainer label="The rule as a fine" steps={steps}
               footnote="The sector rule (at most 1 per sector) is a fine in both circuits, but it only links stocks in the same sector. Legal-shot shares: real runs on today's NIFTY 50 problem.">
      {(step) => (
        <div className="min-h-80">
          <AnimatePresence mode="wait">
            <motion.div key={step < 2 ? "fine" : step === 2 ? "wires" : "legal"} initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }} transition={{ duration: 0.3 }}>
              {step < 2 && <FineCurve expanded={step === 1} />}
              {step === 2 && <AllPairs />}
              {step === 3 && <LegalShare penalty={penalty.legal} xy={xy.legal} />}
            </motion.div>
          </AnimatePresence>
        </div>
      )}
    </Explainer>
  );
}

function FineCurve({ expanded }: { expanded: boolean }) {
  const counts = Array.from({ length: 9 }, (_, i) => i);
  const w = 420;
  const base = 170;
  return (
    <div>
      <svg viewBox={`0 0 ${w} 214`} className="w-full max-w-120" role="img" aria-label="The fine is zero at 4 stocks and grows on both sides">
        {counts.map((count) => {
          const fine = (count - 4) ** 2;
          const x = 30 + count * 44;
          const height = (fine / 16) * 140;
          return (
            <g key={count}>
              <motion.rect x={x} width="28" rx="2" fill={count === 4 ? "var(--good)" : "var(--signal)"}
                           fillOpacity={expanded ? 0.3 : 0.85}
                           initial={{ height: 0, y: base }} animate={{ height: Math.max(height, 2), y: base - Math.max(height, 2) }}
                           transition={{ duration: 0.8, ease: EASE, delay: 0.05 * Math.abs(count - 4) }} />
              <text x={x + 14} y={base + 16} textAnchor="middle" fontSize="12" fill="var(--ink-2)" className="font-mono">{count}</text>
              {fine > 0 && <text x={x + 14} y={base - height - 5} textAnchor="middle" fontSize="10" fill="var(--muted)">{fine}λ</text>}
            </g>
          );
        })}
        <text x={30 + 4 * 44 + 14} y={base - 10} textAnchor="middle" fontSize="11" fill="var(--good)">0</text>
        <text x={w / 2} y={210} textAnchor="middle" fontSize="11" fill="var(--muted)">stocks picked</text>
      </svg>
      <div className="mt-4 font-serif text-lg text-ink-2">
        <AnimatePresence mode="wait">
          <motion.p key={String(expanded)} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            {expanded ? (
              <>λ[ −7 Σ<sub>i</sub> <i>x<sub>i</sub></i> + <span className="rounded-sm bg-signal/15 px-1 text-ink">2 Σ<sub>i&lt;j</sub> <i>x<sub>i</sub> x<sub>j</sub></i></span> + 16 ]</>
            ) : (
              <>fine = λ(<i>x</i><sub>1</sub> + <i>x</i><sub>2</sub> + … + <i>x</i><sub>8</sub> − 4)²</>
            )}
          </motion.p>
        </AnimatePresence>
        {expanded && <p className="mt-1 text-sm">the highlighted term touches every pair of stocks</p>}
      </div>
    </div>
  );
}

function AllPairs() {
  const points = circlePoints(8, 88, 110);
  const pairs = allPairs(8);
  return (
    <div className="flex flex-col items-center gap-8 sm:flex-row">
      <svg viewBox="0 0 220 220" className="h-60 w-60 shrink-0" role="img" aria-label="Eight qubits with all 28 pairs linked">
        {pairs.map(([i, j], k) => (
          <motion.line key={`${i}-${j}`} x1={points[i][0]} y1={points[i][1]} x2={points[j][0]} y2={points[j][1]}
                       stroke="var(--signal)" strokeWidth="1.2" strokeOpacity="0.7" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
                       transition={{ duration: 0.35, delay: 0.06 * k, ease: EASE }} />
        ))}
        {points.map(([x, y], i) => <circle key={i} cx={x} cy={y} r="9" fill="var(--paper)" stroke="var(--ink)" strokeWidth="1.5" />)}
      </svg>
      <div>
        <p className="font-serif text-5xl text-ink">28</p>
        <p className="mt-1 text-sm text-ink-2">two-qubit links per layer,<br />from the fine alone</p>
      </div>
    </div>
  );
}

function LegalShare({ penalty, xy }: { penalty: number; xy: number }) {
  const rows = [
    { label: "Penalty (rule as a fine)", value: penalty, color: "bg-series-1" },
    { label: "XY (rule built in)", value: xy, color: "bg-signal" },
  ];
  return (
    <div className="flex min-h-80 flex-col justify-center gap-7">
      {rows.map((row, i) => (
        <div key={row.label}>
          <div className="flex items-baseline justify-between">
            <span className="text-sm text-ink">{row.label}</span>
            <span className="font-serif text-3xl tabular-nums text-ink">{percent(row.value)}</span>
          </div>
          <div className="mt-2 h-3 bg-rule">
            <motion.div className={`h-full ${row.color}`} initial={{ width: 0 }} animate={{ width: `${100 * row.value}%` }}
                        transition={{ duration: 1.1, ease: EASE, delay: 0.25 * i }} />
          </div>
        </div>
      ))}
      <p className="text-xs text-muted">share of {whole(SHOTS)} shots that followed every rule · today's NIFTY 50 problem, 2 layers, all links, COBYLA</p>
    </div>
  );
}

/* ------------------------------------------------------------------ 6. Start with legal portfolios only */

export function DickeExplainer({ grid }: { grid: Circuits }) {
  const n = grid.markets.nifty50.shortlist.length;
  const steps = [
    { title: "Standard start: every pattern",
      text: "A coin flip on each of 8 qubits gives all 2⁸ = 256 patterns, equally likely. Each square is one pattern." },
    { title: "Most of them break the rule",
      text: "Only 70 patterns buy exactly 4 stocks: 27%. The standard circuit starts with 73% of its weight on illegal portfolios." },
    { title: "Our start: legal patterns only",
      text: "A short circuit prepares every way of picking 4 stocks, all equally likely, and nothing else (a Dicke state). The circuit never sees a wrong count." },
    { title: "Why not start from one portfolio?",
      text: "One legal pattern is cheaper to prepare, but in our dry run the optimiser learned “don't mix” and returned its starting portfolio 100% of the time. Starting from all of them avoids that." },
  ];
  return (
    <Explainer label="Start with legal portfolios only" steps={steps}
               footnote={`8 qubits for clarity. Our run: ${n} qubits, ${whole(2 ** n)} patterns, ${whole(choose(n, 4))} with exactly 4 stocks (${whole(grid.markets.nifty50.legal_on_shortlist)} of them also keep to 1 per sector).`}>
      {(step) => <PatternGrid step={step} />}
    </Explainer>
  );
}

const PATTERNS = Array.from({ length: 256 }, (_, i) => i);

function PatternGrid({ step }: { step: number }) {
  const tile = 17;
  const opacity = (pattern: number) => {
    const legal = ones(pattern) === 4;
    if (step === 0) return 0.55;
    if (step === 1) return legal ? 0.9 : 0.18;
    if (step === 2) return legal ? 0.9 : 0.04;
    return pattern === 15 ? 1 : legal ? 0.12 : 0.03;
  };
  const fill = (pattern: number) => (step === 0 || ones(pattern) !== 4 ? "var(--ink-2)" : "var(--signal)");
  const stats: [string, string, boolean][] = [
    ["256", "patterns on 8 qubits", step === 0],
    ["70", "with exactly 4 stocks (27%)", step === 1 || step === 2],
    ["1", "single starting portfolio", step === 3],
  ];
  return (
    <div className="flex min-h-80 flex-wrap items-center gap-8">
      <svg viewBox={`0 0 ${16 * tile} ${16 * tile}`} className="w-full max-w-68" role="img"
           aria-label="All 256 patterns of 8 qubits; the 70 with exactly 4 stocks are marked">
        {PATTERNS.map((pattern) => (
          <rect key={pattern} x={(pattern % 16) * tile + 1} y={Math.floor(pattern / 16) * tile + 1} width={tile - 2} height={tile - 2} rx="2.5"
                style={{ fill: fill(pattern), fillOpacity: opacity(pattern), transition: `fill 0.5s ease, fill-opacity 0.6s ease ${(pattern % 16) * 0.012}s` }} />
        ))}
      </svg>
      <dl className="space-y-4">
        {stats.map(([value, label, on]) => (
          <div key={label} className={`border-l-2 pl-3 transition-colors duration-500 ${on ? "border-signal" : "border-rule"}`}>
            <dt className={`font-serif text-3xl tabular-nums transition-colors duration-500 ${on ? "text-ink" : "text-muted"}`}>{value}</dt>
            <dd className="text-xs text-ink-2">{label}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/* ------------------------------------------------------------------ 7. Mix without breaking the rule */

const START = [0, 1, 3, 6];
const FLIPS = [2, 6, 5, 0, 7, 3];

export function MixerExplainer() {
  const steps = [
    { title: "Standard mixer: flip any switch",
      text: "The standard mixer turns each qubit on its own, so weight leaks to patterns with a stock more or a stock fewer. Those portfolios break the rule, which is why that circuit needs the fine." },
    { title: "XY mixer: swap neighbours",
      text: "Our mixer only moves weight between neighbouring qubits around a ring: a bought stock is swapped for one that isn't. The count stays at exactly 4, always, so the fine for the count disappears." },
    { title: "Only a ring of links",
      text: "The ring adds one link per qubit per layer: 8 here, 16 in our run. The score still links stocks that move together, but those links now come only from the data, so the weak ones can be dropped." },
  ];
  return (
    <Explainer label="Mix without breaking the rule" steps={steps} footnote="8 qubits for clarity; the flips and swaps shown are one example sequence.">
      {(step) => <Ring step={step} />}
    </Explainer>
  );
}

function xyPattern(tick: number): { lit: Set<number>; last: number[] | null } {
  const lit = new Set(START);
  let last: number[] | null = null;
  for (let t = 0; t < tick; t++) {
    const options = Array.from({ length: 8 }, (_, i) => [i, (i + 1) % 8]).filter(([a, b]) => lit.has(a) !== lit.has(b));
    last = options[(t * 3) % options.length];
    const [a, b] = last;
    if (lit.has(a)) { lit.delete(a); lit.add(b); } else { lit.delete(b); lit.add(a); }
  }
  return { lit, last };
}

function Ring({ step }: { step: number }) {
  const tick = useTicker(step < 2, 1500);
  const points = circlePoints(8, 82, 110);
  const ring = Array.from({ length: 8 }, (_, i) => [i, (i + 1) % 8]);
  let lit = new Set(START);
  let flipped: number | null = null;
  let swapped: number[] | null = null;
  if (step === 0 && tick % 2 === 1) {
    flipped = FLIPS[Math.floor(tick / 2) % FLIPS.length];
    lit = new Set(START);
    if (lit.has(flipped)) lit.delete(flipped); else lit.add(flipped);
  }
  if (step === 1) ({ lit, last: swapped } = xyPattern(tick));
  const count = lit.size;
  const ok = count === 4;

  return (
    <div className="flex min-h-80 flex-col items-center gap-8 sm:flex-row">
      <svg viewBox="0 0 220 220" className="h-60 w-60 shrink-0" role="img"
           aria-label={step === 0 ? "Qubits flipping one at a time" : "Neighbouring qubits swapping around a ring"}>
        {step > 0 && ring.map(([a, b]) => {
          const active = swapped && swapped[0] === a && swapped[1] === b;
          return (
            <line key={`${a}-${b}`} x1={points[a][0]} y1={points[a][1]} x2={points[b][0]} y2={points[b][1]}
                  stroke="var(--signal)" strokeOpacity={active ? 1 : 0.45} strokeWidth={active ? 3.5 : 1.5}
                  style={{ transition: "stroke-width 0.3s, stroke-opacity 0.3s" }} />
          );
        })}
        {points.map(([x, y], i) => (
          <g key={i}>
            {flipped === i && (
              <motion.circle cx={x} cy={y} r="13" fill="none" stroke="var(--bad)" strokeWidth="2"
                             initial={{ scale: 0.6, opacity: 1 }} animate={{ scale: 1.8, opacity: 0 }} transition={{ duration: 0.9 }}
                             style={{ originX: 0.5, originY: 0.5 }} />
            )}
            <circle cx={x} cy={y} r="13" stroke="var(--ink)" strokeWidth="1.5"
                    style={{ fill: lit.has(i) ? "var(--signal)" : "var(--paper)", transition: "fill 0.45s ease" }} />
            <text x={x} y={y + 4} textAnchor="middle" fontSize="11" className="font-mono"
                  style={{ fill: lit.has(i) ? "var(--paper)" : "var(--muted)", transition: "fill 0.45s ease" }}>{lit.has(i) ? 1 : 0}</text>
          </g>
        ))}
      </svg>
      <div className="min-w-0 space-y-4">
        <div>
          <p className="font-serif text-5xl tabular-nums text-ink">{count}</p>
          <p className={`mt-1 flex items-center gap-1.5 text-sm ${ok ? "text-good" : "text-bad"}`}>
            {ok ? <CheckIcon /> : <CrossIcon />}stocks picked: {ok ? "follows the rule" : "breaks the rule"}
          </p>
        </div>
        {step === 2 && (
          <motion.p initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="max-w-52 text-sm text-ink-2">
            <span className="font-serif text-3xl text-ink">8</span> ring links per layer, against 28 for the fine
          </motion.p>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ 8. Prune the weak links */

const KEPT = [1, 0.75, 0.5, 0.25, 0.25];

export function PruneExplainer({ grid }: { grid: Circuits }) {
  const xy = KEPT.slice(0, 4).map((kept) => findRun(grid, "xy", kept));
  const penalty = KEPT.slice(0, 4).map((kept) => findRun(grid, "standard", kept));
  const saved = 1 - xy[3].gates / xy[0].gates;
  const steps = [
    { title: "Every link costs gates",
      text: `In the score step each pair of stocks that moves together gets a two-qubit gate. On today's NIFTY 50 shortlist with 2 layers: ${whole(xy[0].gates)} gates for XY, ${whole(penalty[0].gates)} for the penalty circuit (whose fine needs every pair).` },
    { title: "Drop the weakest quarter",
      text: `Pairs that barely move together change the score very little. Keeping the strongest 75%: ${whole(xy[1].gates)} gates for XY.` },
    { title: "Keep half",
      text: `${whole(xy[2].gates)} gates for XY. The penalty circuit is still at ${whole(penalty[2].gates)}: its fine needs every pair anyway.` },
    { title: "Keep a quarter",
      text: `${whole(xy[3].gates)} gates for XY (${percent(saved, 0)} fewer), ${times(xy[3].lift)} better than random guessing (from ${times(xy[0].lift)})${xy[3].found_best ? ", and it still found the best portfolio" : ""}. Pruning saves gates only on the XY circuit.` },
    { title: "Graded on the full problem",
      text: "Pruning changes the circuit, never the answer key. Every shot is scored on the full, unpruned score, so pruning can't make a portfolio look better than it is." },
  ];
  return (
    <Explainer label="Prune the weak links" steps={steps}
               footnote="Graph: an illustration on 8 qubits. Gate counts: real runs on today's NIFTY 50 problem (16-stock shortlist), 2 layers, COBYLA, compiled for a fake IBM Brisbane chip.">
      {(step) => <Pruning step={step} xy={xy} penalty={penalty} />}
    </Explainer>
  );
}

function Pruning({ step, xy, penalty }: { step: number; xy: GridRun[]; penalty: GridRun[] }) {
  const kept = KEPT[step];
  const points = circlePoints(8, 82, 110);
  const ranked = allPairs(8).sort((p, q) => strength(q[0], q[1]) - strength(p[0], p[1]));
  const keep = new Set(ranked.slice(0, Math.round(kept * ranked.length)).map((pair) => pair.join()));
  const index = Math.min(step, 3);
  const most = Math.max(...xy.map((run) => run.gates), ...penalty.map((run) => run.gates));
  const bars = [
    { label: "XY", run: xy[index], color: "bg-signal" },
    { label: "Penalty", run: penalty[index], color: "bg-series-1" },
  ];
  return (
    <div className="grid min-h-80 items-center gap-8 sm:grid-cols-[14rem_minmax(0,1fr)]">
      <svg viewBox="0 0 220 220" className="h-56 w-56" role="img" aria-label={`Eight stocks with the strongest ${percent(kept, 0)} of links kept`}>
        {ranked.map(([i, j]) => {
          const on = keep.has(`${i},${j}`);
          return (
            <line key={`${i}-${j}`} x1={points[i][0]} y1={points[i][1]} x2={points[j][0]} y2={points[j][1]}
                  stroke="var(--accent)" strokeWidth={0.6 + 2.6 * strength(i, j)} strokeLinecap="round"
                  style={{ strokeOpacity: on ? 0.25 + 0.6 * strength(i, j) : 0, transition: "stroke-opacity 0.7s ease" }} />
          );
        })}
        {points.map(([x, y], i) => <circle key={i} cx={x} cy={y} r="9" fill="var(--paper)" stroke="var(--ink)" strokeWidth="1.5" />)}
      </svg>
      <div className="min-w-0">
        <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted">links kept</p>
        <p className="font-serif text-5xl tabular-nums text-ink">{percent(kept, 0)}</p>
        <div className="mt-6 space-y-5">
          {bars.map((bar) => (
            <div key={bar.label}>
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span className="text-ink">{bar.label}</span>
                <span className="font-mono tabular-nums text-ink-2">{whole(bar.run.gates)} gates</span>
              </div>
              <div className="mt-1.5 h-2.5 bg-rule">
                <motion.div className={`h-full ${bar.color}`} animate={{ width: `${(100 * bar.run.gates) / most}%` }}
                            transition={{ duration: 0.8, ease: EASE }} />
              </div>
              <p className="mt-1 text-xs text-muted">{times(bar.run.lift)} better than random guessing</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
