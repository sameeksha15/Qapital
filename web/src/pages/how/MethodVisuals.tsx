import { AnimatePresence, motion } from "motion/react";
import { SHOTS, type FullResult, type SampledPortfolio } from "../../api/types";
import { EASE } from "../../components/motion";
import { percent, portfolioName, sameStocks, shortName, whole } from "../../lib/format";
import { Explainer } from "./Explainer";
import { OWN, strength } from "./illustration";

const tickersOf = (label: string) => label.split(", ");

/* ------------------------------------------------------------------ 1. Stocks become qubits */

export function QubitsExplainer({ result }: { result: FullResult }) {
  const { quantum } = result;
  const stocks = quantum.shortlist ?? [...new Set(quantum.top_samples.flatMap((sample) => sample.stocks))];
  const n = stocks.length;
  const top = quantum.top_samples[0];
  const steps = [
    { title: "One qubit per stock",
      text: `Each of the run's ${n} shortlisted stocks gets one qubit: a switch that reads 1 (buy) or 0 (don't buy) when it is measured.` },
    { title: "A portfolio is a pattern of switches",
      text: `Buying ${portfolioName(quantum.chosen)} means those ${quantum.chosen.length} qubits read 1 and the rest read 0. Every portfolio is one pattern: ${whole(2 ** n)} patterns in all.` },
    { title: "Before measuring: every pattern at once",
      text: "Inside the circuit the qubits are not yet 0 or 1. The circuit holds all the patterns at the same time, each with its own weight (an amplitude). Shaping those weights is the algorithm's whole job." },
    { title: "Measuring gives one pattern: a shot",
      text: `Reading the qubits gives one definite pattern, one portfolio. In our run, ${portfolioName(top.stocks)} came out most often: ${top.count} of ${whole(SHOTS)} shots.` },
  ];
  return (
    <Explainer label="Stocks become qubits" steps={steps}
               footnote={`A real run's shortlist and shots (${n} stocks fit on the simulator).`}>
      {(step) => <QubitBoard step={step} stocks={stocks} chosen={quantum.chosen} sample={top.stocks} />}
    </Explainer>
  );
}

function QubitBoard({ step, stocks, chosen, sample }: { step: number; stocks: string[]; chosen: string[]; sample: string[] }) {
  const lit = new Set<string>(step === 1 ? chosen : step === 3 ? sample : []);
  const unsure = step === 2;
  return (
    <div className="flex min-h-80 flex-col justify-center">
      <div className="grid grid-cols-4 gap-x-2 gap-y-5 sm:grid-cols-8">
        {stocks.map((ticker, i) => {
          const on = lit.has(ticker);
          return (
            <div key={ticker} className="flex min-w-0 flex-col items-center gap-1.5">
              <motion.div animate={unsure ? { opacity: [0.3, 1, 0.3], scale: 1 } : { opacity: 1, scale: on ? 1.1 : 1 }}
                          transition={unsure ? { duration: 1.8, repeat: Infinity, delay: (i % 8) * 0.14 } : { duration: 0.45, ease: EASE, delay: on ? i * 0.03 : 0 }}
                          className={`flex h-10 w-10 items-center justify-center rounded-full border font-mono text-sm transition-colors duration-500 ${
                            on ? "border-signal bg-signal text-paper" : unsure ? "border-accent bg-paper-2 text-accent" : "border-rule-strong text-muted"}`}>
                {unsure ? "?" : on ? 1 : 0}
              </motion.div>
              <span className="max-w-full truncate font-mono text-[10px] text-muted">{shortName(ticker)}</span>
            </div>
          );
        })}
      </div>
      <p className="mt-9 break-all font-mono text-lg tracking-[0.25em]" aria-label="The pattern as digits">
        {stocks.map((ticker) => (
          <span key={ticker} className={unsure ? "text-accent" : lit.has(ticker) ? "text-signal" : "text-muted"}>
            {unsure ? "?" : lit.has(ticker) ? "1" : "0"}
          </span>
        ))}
      </p>
      <p className="mt-2 text-sm text-ink-2">
        {step === 0 && `${stocks.length} qubits → 2^${stocks.length} = ${whole(2 ** stocks.length)} possible patterns`}
        {step === 1 && "one portfolio = one pattern"}
        {step === 2 && `all ${whole(2 ** stocks.length)} patterns held at once, each with its own weight`}
        {step === 3 && "one shot = one measured pattern"}
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ 2. The score becomes an energy */

const LETTERS = "ABCDEFGH".split("");
const PICKED = new Set([1, 3, 4, 6]);

export function ScoreExplainer() {
  const steps = [
    { title: "One number per stock",
      text: "On the diagonal: the stock's own risk (its variance σᵢ², times your risk setting q), minus its expected return μᵢ, plus the fee. It counts when the stock is bought (xᵢ = 1)." },
    { title: "One number per pair",
      text: "Above the diagonal: how strongly two stocks move together (their covariance σᵢⱼ). It counts only when both are bought. Stocks that fall together add risk." },
    { title: "A portfolio adds up its cells",
      text: "Buying B, D, E and G counts their 4 stock cells and the 6 pair cells between them; every other cell is ignored. That sum is the portfolio's score, the same score every method uses. Lower is better." },
    { title: "In the circuit's language",
      text: "A qubit reads +1 or −1, so each xᵢ becomes zᵢ = 1 − 2xᵢ. The same numbers turn into hᵢ (per qubit) and Jᵢⱼ (per pair): the cost Hamiltonian. Each pattern's energy is its portfolio's score, shifted and scaled, so the lowest energy is the best portfolio." },
  ];
  return (
    <Explainer label="The score becomes an energy" steps={steps}
               footnote="Letters and shading are an illustration; the real run uses 16 stocks and their measured returns and risks.">
      {(step) => <ScoreMatrix step={step} />}
    </Explainer>
  );
}

function ScoreMatrix({ step }: { step: number }) {
  const cell = 34;
  const offset = 26;
  const size = offset + 8 * cell;
  const shown = (i: number, j: number) => {
    if (step === 2) return PICKED.has(i) && PICKED.has(j);
    return i === j || step !== 0;
  };
  return (
    <div className="flex min-h-80 flex-col items-center justify-center gap-6 sm:flex-row sm:items-center sm:gap-10">
      <svg viewBox={`0 0 ${size} ${size}`} className="w-full max-w-64 shrink-0" role="img"
           aria-label="An 8 by 8 table: one number per stock on the diagonal, one per pair above it">
        {LETTERS.map((letter, i) => {
          const picked = step === 2 && PICKED.has(i);
          return (
            <g key={letter} className="font-mono" fontSize="11">
              <text x={offset + i * cell + cell / 2} y={16} textAnchor="middle" fill={picked ? "var(--signal)" : "var(--muted)"}>{letter}</text>
              <text x={10} y={offset + i * cell + cell / 2 + 4} textAnchor="middle" fill={picked ? "var(--signal)" : "var(--muted)"}>{letter}</text>
            </g>
          );
        })}
        {LETTERS.map((_, i) => LETTERS.map((__, j) => {
          if (j < i) return null;
          const diagonal = i === j;
          const on = shown(i, j);
          const level = diagonal ? OWN[i] : strength(i, j);
          return (
            <g key={`${i}-${j}`}>
              <rect x={offset + j * cell + 1} y={offset + i * cell + 1} width={cell - 2} height={cell - 2} rx="3"
                    fill={diagonal ? "var(--signal)" : "var(--accent)"} stroke="var(--rule)" strokeWidth="0.5"
                    style={{ transition: "fill-opacity 0.6s ease", fillOpacity: on ? 0.12 + 0.75 * level : 0.04 }} />
              {step === 3 && (
                <motion.text x={offset + j * cell + cell / 2} y={offset + i * cell + cell / 2 + 4} textAnchor="middle"
                             fontSize="11" fontStyle="italic" fill="var(--ink)" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                             transition={{ delay: 0.02 * (i + j) }} className="font-serif">
                  {diagonal ? "h" : "J"}
                </motion.text>
              )}
            </g>
          );
        }))}
      </svg>
      <Formula step={step} />
    </div>
  );
}

function Formula({ step }: { step: number }) {
  const lit = "rounded-sm bg-signal/15 px-1 text-ink";
  return (
    <div className="whitespace-nowrap font-serif text-base leading-relaxed text-ink-2">
      <AnimatePresence mode="wait">
        <motion.div key={step === 3 ? "ising" : "qubo"} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.35 }}>
          {step === 3 ? (
            <>
              <p className="text-ink"><i>E</i>(<i>z</i>) = Σ<sub>i</sub> <i>h<sub>i</sub> z<sub>i</sub></i> + Σ<sub>i&lt;j</sub> <i>J<sub>ij</sub> z<sub>i</sub> z<sub>j</sub></i></p>
              <p className="mt-3 text-sm">with <i>z<sub>i</sub></i> = ±1:<br />the energy the circuit works with</p>
            </>
          ) : (
            <>
              <p>score(<i>x</i>) =</p>
              <p className="mt-1"><span className={step === 0 ? lit : ""}>Σ<sub>i</sub> (<i>q</i>σ<sub>i</sub>² − μ<sub>i</sub> + fee) <i>x<sub>i</sub></i></span></p>
              <p className="mt-1">+ <span className={step === 1 ? lit : ""}>Σ<sub>i&lt;j</sub> 2<i>q</i>σ<sub>ij</sub> <i>x<sub>i</sub> x<sub>j</sub></i></span></p>
              {step === 2 && <p className="mt-3 text-sm">B + D + E + G:<br />4 stock cells + 6 pair cells</p>}
            </>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

/* ------------------------------------------------------------------ 3. One QAOA layer */

export function LayerExplainer({ result }: { result: FullResult }) {
  const { quantum } = result;
  const rows = quantum.layer_probs;
  const depth = rows.length - 1;
  const first = rows[0][0];
  const final = rows[depth][0];
  const steps = [
    { title: "Start: equal chances",
      text: `The circuit starts with every legal-sized portfolio equally likely. Each of these ${rows[0].length} best portfolios begins at ${percent(first, 2)} per shot.` },
    { title: "Score step (γ): turn the phases",
      text: "Each portfolio's phase (the dial) turns by γ times its energy. The chances don't change yet: the score is now written into the phases." },
    { title: "Mixing step (β): phases become chances",
      text: "The mixer lets portfolios pass weight to their neighbours. Where phases line up, weight piles up; where they clash, it cancels. Now the chances move." },
    { title: `Repeat for each layer (${depth} here)`,
      text: `Each layer repeats the two steps with its own γ and β. After ${depth} layers the best portfolio's chance went from ${percent(first, 2)} to ${percent(final, 2)}: about ${Math.round(final / first)} times its starting chance.` },
    { title: "Measure",
      text: `Each shot now gives a portfolio with these chances. The ${whole(SHOTS)} shots follow them.` },
  ];
  return (
    <Explainer label="One QAOA layer" steps={steps}
               footnote={`Bars: the real chances in our run for its ${rows[0].length} best portfolios, after each layer. Dials: an illustration of phase.`}>
      {(step) => <LayerPicture step={step} rows={rows} labels={quantum.layer_labels} />}
    </Explainer>
  );
}

function LayerPicture({ step, rows, labels }: { step: number; rows: number[][]; labels: string[] }) {
  const depth = rows.length - 1;
  const blocks = ["Start", ...Array.from({ length: depth }, (_, l) => [`Score γ${sub(l + 1)}`, `Mix β${sub(l + 1)}`]).flat(), "Measure"];
  const active = (b: number) => (step === 0 ? b === 0 : step === 1 ? b === 1 : step === 2 ? b === 2 : step === 3 ? b >= 3 && b <= 2 * depth : b === blocks.length - 1);
  const row = rows[[0, 0, 1, depth, depth][step]];
  const highest = Math.max(...rows.flat());
  const dial = (i: number) => [0, 30 + 41 * i, 18 + 23 * ((i * 5) % 8), 12 + 17 * ((i * 3) % 8), 12 + 17 * ((i * 3) % 8)][step];

  return (
    <div className="min-h-80">
      <div className="relative overflow-x-auto pb-1">
        <div className="relative flex min-w-max items-center gap-2">
          <span aria-hidden="true" className="absolute inset-x-2 top-1/2 h-px bg-rule-strong" />
          {blocks.map((block, b) => (
            <motion.span key={block} animate={{ scale: active(b) ? 1.06 : 1 }}
                         className={`relative rounded-full border px-3 py-1 font-mono text-xs transition-colors duration-500 ${
                           active(b) ? "border-ink bg-ink text-paper" : "border-rule-strong bg-paper text-ink-2"}`}>
              {block}
            </motion.span>
          ))}
        </div>
      </div>

      <ul className="mt-7 space-y-2.5">
        {labels.map((label, i) => (
          <li key={label} className="grid grid-cols-[minmax(0,10rem)_22px_minmax(0,1fr)] items-center gap-3 sm:grid-cols-[minmax(0,13rem)_22px_minmax(0,1fr)]">
            <span className={`truncate text-right font-mono text-[11px] ${i === 0 ? "text-signal" : "text-ink-2"}`}>{portfolioName(tickersOf(label))}</span>
            <svg viewBox="0 0 22 22" className="h-5.5 w-5.5" aria-hidden="true">
              <circle cx="11" cy="11" r="9.5" fill="none" stroke="var(--rule-strong)" />
              <motion.line x1="11" y1="11" x2="11" y2="3" stroke={i === 0 ? "var(--signal)" : "var(--ink-2)"} strokeWidth="1.6"
                           strokeLinecap="round" style={{ originX: 0.5, originY: 1 }}
                           animate={{ rotate: dial(i) }} transition={{ duration: 0.9, ease: EASE }} />
            </svg>
            <div className="flex items-center gap-2">
              <div className="h-3.5 flex-1">
                <motion.div className={`h-full rounded-r-sm ${i === 0 ? "bg-signal" : "bg-series-1"}`}
                            animate={{ width: `${Math.max(0.6, (100 * row[i]) / highest)}%` }} transition={{ duration: 0.9, ease: EASE }} />
              </div>
              <span className="w-12 text-right font-mono text-[11px] tabular-nums text-ink-2">{percent(row[i], 2)}</span>
            </div>
          </li>
        ))}
      </ul>
      <p className="mt-4 text-xs text-muted">chance of each portfolio in one shot · orange: the best portfolio</p>
    </div>
  );
}

const sub = (n: number) => String(n).split("").map((d) => "₀₁₂₃₄₅₆₇₈₉"[Number(d)]).join("");

/* ------------------------------------------------------------------ 4. Tune, then sample */

export function TuneExplainer({ result }: { result: FullResult }) {
  const { quantum, optimal } = result;
  const cvar = (result.request?.settings.cvar_alpha ?? 1) < 1;
  const target = cvar ? `the average energy of its best ${percent(result.request!.settings.cvar_alpha, 0)} of outcomes (CVaR)` : "the average energy the circuit would produce";
  const depth = quantum.layer_probs.length - 1;
  const best = quantum.top_samples.find((sample) => sameStocks(sample.stocks, quantum.chosen));
  const steps = [
    { title: "The knobs",
      text: `${depth} layers means ${2 * depth} knobs: one γ for each score step and one β for each mixing step. Every setting of the knobs gives a different set of chances.` },
    { title: "Try, measure, adjust",
      text: `A classical optimiser (COBYLA or SPSA) sets the knobs, the simulator reports ${target}, and the optimiser keeps the changes that lower it: ${quantum.convergence.length} tries in this run.` },
    { title: "Layer by layer",
      text: "Layer 1 is tuned first, starting from the best point of a coarse grid. Each new layer starts from the previous layer's knobs, stretched out to one more layer (a warm start). No answer is fed in." },
    { title: `${whole(SHOTS)} shots`,
      text: `The tuned circuit runs ${whole(SHOTS)} times. Each shot is one portfolio; these came out most often.` },
    { title: "Keep the best legal one",
      text: best
        ? `Every shot is scored with the shared score function on the full problem. The best legal one is the answer: ${portfolioName(best.stocks)}, seen ${best.count} times.`
        : "Every shot is scored with the shared score function on the full problem. The best legal one is the answer." },
  ];
  return (
    <Explainer label="Tune, then sample" steps={steps}
               footnote="Curve and shot counts: a real run. Dial positions are an illustration.">
      {(step) => (
        <div className="min-h-80">
          <AnimatePresence mode="wait">
            <motion.div key={step === 0 ? "knobs" : step < 3 ? "curve" : "shots"} initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }} transition={{ duration: 0.3 }}>
              {step === 0 && <Knobs depth={depth} />}
              {(step === 1 || step === 2) && <Convergence values={quantum.convergence} best={optimal?.shortlist_best?.score ?? optimal?.best.score} split={step === 2} />}
              {step >= 3 && <Shots samples={quantum.top_samples.slice(0, 10)} chosen={quantum.chosen} highlight={step === 4} />}
            </motion.div>
          </AnimatePresence>
        </div>
      )}
    </Explainer>
  );
}

function Knobs({ depth }: { depth: number }) {
  const knobs = Array.from({ length: depth }, (_, l) => [`γ${sub(l + 1)}`, `β${sub(l + 1)}`]).flat();
  return (
    <div className="flex min-h-80 flex-wrap items-center justify-center gap-8">
      {knobs.map((knob, i) => (
        <div key={knob} className="flex flex-col items-center gap-3">
          <svg viewBox="0 0 80 80" className="h-20 w-20" aria-hidden="true">
            <circle cx="40" cy="40" r="34" fill="var(--paper-2)" stroke="var(--rule-strong)" />
            {Array.from({ length: 12 }, (_, t) => (
              <line key={t} x1="40" y1="9" x2="40" y2="13" stroke="var(--rule-strong)" transform={`rotate(${t * 30} 40 40)`} />
            ))}
            <motion.line x1="40" y1="40" x2="40" y2="14" stroke={i % 2 ? "var(--accent)" : "var(--signal)"} strokeWidth="3" strokeLinecap="round"
                         style={{ originX: 0.5, originY: 1 }} initial={{ rotate: -120 }}
                         animate={{ rotate: [-120, 70 - 35 * i, 20 + 25 * i, 40 - 10 * i] }}
                         transition={{ duration: 3, ease: "easeInOut", delay: 0.15 * i }} />
            <circle cx="40" cy="40" r="4" fill="var(--ink)" />
          </svg>
          <span className="font-serif text-lg italic text-ink">{knob}</span>
        </div>
      ))}
    </div>
  );
}

function Convergence({ values, best, split }: { values: number[]; best?: number; split: boolean }) {
  const w = 560;
  const h = 250;
  const pad = 58;
  const all = best != null ? [...values, best] : values;
  const low = Math.min(...all);
  const high = Math.max(...all);
  const x = (i: number) => pad + ((w - pad - 8) * i) / (values.length - 1);
  const y = (v: number) => 10 + ((h - pad - 10) * (high - v)) / (high - low || 1);
  const path = values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" role="img" aria-label="The average energy falling as the optimiser tunes the knobs">
      <line x1={pad} y1={h - pad} x2={w - 8} y2={h - pad} stroke="var(--rule-strong)" />
      <line x1={pad} y1={10} x2={pad} y2={h - pad} stroke="var(--rule-strong)" />
      <text x={(w + pad) / 2} y={h - 8} textAnchor="middle" fontSize="12" fill="var(--muted)">tuning step (one circuit run each)</text>
      <text x={12} y={(h - pad) / 2} textAnchor="middle" fontSize="12" fill="var(--muted)" transform={`rotate(-90 12 ${(h - pad) / 2})`}>average energy</text>
      {[high, (high + low) / 2, low].map((v) => (
        <text key={v} x={pad - 4} y={y(v) + 4} textAnchor="end" fontSize="10" fill="var(--muted)" className="font-mono">{v.toFixed(2)}</text>
      ))}
      {best != null && (
        <>
          <line x1={pad} y1={y(best)} x2={w - 8} y2={y(best)} stroke="var(--good)" strokeDasharray="4 4" />
          <text x={w - 10} y={y(best) - 6} textAnchor="end" fontSize="11" fill="var(--good)">score of the best portfolio on the shortlist: the floor</text>
        </>
      )}
      <motion.path d={path} fill="none" stroke="var(--series-1)" strokeWidth="2" strokeLinejoin="round"
                   initial={{ pathLength: split ? 1 : 0 }} animate={{ pathLength: 1 }} transition={{ duration: 2.6, ease: "easeInOut" }} />
      {split && <motion.circle cx={x(values.length - 1)} cy={y(values[values.length - 1])} r="5" fill="var(--signal)"
                               initial={{ scale: 0 }} animate={{ scale: [0, 1.4, 1] }} transition={{ duration: 0.6 }} />}
    </svg>
  );
}

function Shots({ samples, chosen, highlight }: { samples: SampledPortfolio[]; chosen: string[]; highlight: boolean }) {
  const most = Math.max(...samples.map((sample) => sample.count));
  return (
    <ul className="space-y-2">
      {samples.map((sample, i) => {
        const isBest = sameStocks(sample.stocks, chosen);
        const dim = highlight && !isBest;
        return (
          <li key={sample.stocks.join()} className={`grid grid-cols-[minmax(0,11rem)_minmax(0,1fr)] items-center gap-3 transition-opacity duration-500 sm:grid-cols-[minmax(0,14rem)_minmax(0,1fr)] ${dim ? "opacity-30" : ""}`}>
            <span className={`truncate text-right font-mono text-[11px] ${isBest ? "text-signal" : sample.valid ? "text-ink-2" : "text-muted line-through"}`}>
              {portfolioName(sample.stocks)}
            </span>
            <div className="flex items-center gap-2">
              <div className="h-3.5 flex-1">
                <motion.div className={`h-full rounded-r-sm ${isBest ? "bg-signal" : sample.valid ? "bg-series-1" : "bg-neutral"}`}
                            initial={{ width: 0 }} animate={{ width: `${(100 * sample.count) / most}%` }}
                            transition={{ duration: 1.2, ease: EASE, delay: 0.06 * i }} />
              </div>
              <span className="w-9 text-right font-mono text-[11px] tabular-nums text-ink-2">{sample.count}</span>
            </div>
          </li>
        );
      })}
      <li className="pt-2 text-xs text-muted">shots out of {whole(SHOTS)} · orange: the best legal portfolio · struck through: breaks a rule</li>
    </ul>
  );
}
