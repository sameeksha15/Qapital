import { AnimatePresence, motion } from "motion/react";
import type { Families, Noise } from "../../api/research";
import { EASE } from "../../components/motion";
import { percent, times } from "../../lib/format";
import { Explainer } from "./Explainer";
import { OWN } from "./illustration";

// The three upgrades over plain QAOA, as step-by-step pictures. Shapes are illustrations; every number in the step
// texts comes from the research runs (public/research/).

/* ------------------------------------------------------------------ CVaR: judge the circuit by its best shots */

/** A fixed, made-up spread of 40 shot scores, best (lowest) first. */
const SHOT_SCORES = Array.from({ length: 40 }, (_, i) => 0.15 + 0.85 * ((i / 39) ** 0.8) + 0.04 * Math.sin(i * 2.3));

export function CvarExplainer({ families }: { families: Families }) {
  const summary = families.summary.all;
  const at = (alpha: number) => summary.rows.find((r) => r.mixer === "xy" && r.depth === 2 && r.cvar_alpha === alpha);
  const average = at(1);
  const best25 = at(0.25);
  const best10 = at(0.1);
  const record = summary.cvar_vs_average["xy p=2 α=0.25"];
  const steps = [
    { title: "Each shot has a score",
      text: "Run the circuit and every shot is one portfolio with one score. Most shots land on ordinary portfolios; a few land on very good ones." },
    { title: "The usual target: the average",
      text: "Plain QAOA tunes the knobs to lower the average score of all shots. A setting that makes the bad shots a little less bad counts as much as one that finds the best portfolio more often." },
    { title: "CVaR: the average of the best quarter",
      text: "But we only keep the best shot. CVaR (Barkoutsos et al., 2020) tunes for the average of the best 25% of shots and ignores the rest, so the knobs chase the good tail." },
    { title: "What it did on real problems",
      text: average && best25 && record
        ? `XY circuit, 2 layers, ${summary.problems} problems: tuning for the average gave ${times(average.lift.mean)} better than guessing, the best 25% gave ${times(best25.lift.mean)}${best10 ? `, the best 10% ${times(best10.lift.mean)}` : ""}. The best 25% did better on ${record.wins} problems and worse on ${record.losses}.`
        : "See the Research page for the measured effect." },
  ];
  return (
    <Explainer label="CVaR: tune for the best shots" steps={steps} footnote="Bars: an illustration of 40 shots. Numbers: the research runs (CVaR vs average).">
      {(step) => <ShotTail step={step} />}
    </Explainer>
  );
}

function ShotTail({ step }: { step: number }) {
  const w = 440;
  const h = 230;
  const base = 212;
  const bar = w / SHOT_SCORES.length;
  const tail = Math.round(SHOT_SCORES.length / 4);
  const quality = SHOT_SCORES.map((score) => 1.12 - score); // taller = a better portfolio
  const mean = (values: number[]) => values.reduce((a, b) => a + b, 0) / values.length;
  const all = mean(quality);
  const best = mean(quality.slice(0, tail));
  const y = (q: number) => base - q * 170;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" role="img" aria-label="Forty shots sorted from best to worst, with the average of all and of the best quarter marked">
      {quality.map((q, i) => (
        <motion.rect key={i} x={i * bar + 1} width={bar - 2} rx="1.5"
                     initial={{ height: 0, y: base }} animate={{ height: base - y(q), y: y(q) }} transition={{ duration: 0.7, ease: EASE, delay: 0.015 * i }}
                     style={{ fill: step >= 2 && i < tail ? "var(--signal)" : "var(--series-1)", fillOpacity: step >= 2 && i >= tail ? 0.25 : 0.8, transition: "fill 0.5s, fill-opacity 0.5s" }} />
      ))}
      <line x1={0} x2={w} y1={base} y2={base} stroke="var(--rule-strong)" />
      <text x={4} y={h - 4} fontSize="11" fill="var(--muted)">40 shots, best on the left · taller = a better portfolio</text>
      <AnimatePresence>
        {step >= 1 && (
          <motion.g key="all" initial={{ opacity: 0 }} animate={{ opacity: step >= 2 ? 0.45 : 1 }} exit={{ opacity: 0 }}>
            <line x1={0} x2={w} y1={y(all)} y2={y(all)} stroke="var(--ink)" strokeDasharray="5 4" />
            <text x={w - 4} y={y(all) - 5} textAnchor="end" fontSize="11" fill="var(--ink)">average of all shots</text>
          </motion.g>
        )}
        {step >= 2 && (
          <motion.g key="best" initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <line x1={0} x2={tail * bar} y1={y(best)} y2={y(best)} stroke="var(--signal)" strokeWidth="2.5" />
            <text x={tail * bar + 6} y={y(best) + 4} fontSize="11" fill="var(--signal)">average of the best 25%: what CVaR improves</text>
          </motion.g>
        )}
      </AnimatePresence>
    </svg>
  );
}

/* ------------------------------------------------------------------ Warm start: begin near the classical answer */

/** Made-up relaxed amounts for 8 stocks (they add up to 4: buy 4). */
const RELAXED = [0.95, 0.1, 0.8, 0.05, 0.6, 0.2, 0.9, 0.4];
const EPSILON = 0.25;

export function WarmExplainer({ families }: { families: Families }) {
  const summary = families.summary.all;
  const warm = summary.rows.find((r) => r.mixer === "warm" && r.depth === 2 && r.cvar_alpha === 0.25);
  const xy = summary.rows.find((r) => r.mixer === "xy" && r.depth === 2 && r.cvar_alpha === 0.25);
  const added = summary.warm_vs_warm_alone["p=2 α=0.25"];
  const steps = [
    { title: "Solve an easier problem first",
      text: "Let each stock be bought in any amount between none and all, instead of all or nothing. That relaxed problem is quick to solve exactly, and its answer hints at which stocks matter." },
    { title: "Tilt each qubit towards that answer",
      text: `Instead of starting every qubit at 50/50, each starts leaning towards its relaxed amount (Egger et al., 2021). The lean is capped at ${percent(EPSILON, 0)} from certain, so every portfolio stays possible and the circuit can still disagree.` },
    { title: "Then the usual layers",
      text: "Score and mixing steps follow as before; the mixer is rotated to match the tilted start, so the circuit begins already close to a good region." },
    { title: "The fair comparison",
      text: warm?.warm_alone_lift && added
        ? `A head start isn't quantum. So the warm start alone is always measured too: ${times(warm.warm_alone_lift.mean)} better than guessing, against ${times(warm.lift.mean)} after 2 quantum layers (XY circuit: ${xy ? times(xy.lift.mean) : "?"}). The layers improved on their start in ${added.wins} of ${added.problems} problems.`
        : "A head start isn't quantum, so the warm start alone is always measured too." },
  ];
  return (
    <Explainer label="Warm start" steps={steps} footnote="Amounts and dials: an illustration on 8 stocks. Numbers: the research runs (warm start vs cold, 10 stocks, 2 layers, best 25%).">
      {(step) => <WarmPicture step={step} />}
    </Explainer>
  );
}

function WarmPicture({ step }: { step: number }) {
  const lean = (amount: number) => Math.min(1 - EPSILON, Math.max(EPSILON, amount));
  return (
    <div className="flex min-h-72 flex-col justify-center gap-6">
      <div className="grid grid-cols-8 items-end gap-2">
        {RELAXED.map((amount, i) => {
          const chance = step === 0 ? amount : step >= 1 ? lean(amount) : 0.5;
          return (
            <div key={i} className="flex flex-col items-center gap-2">
              <div className="relative flex h-36 w-full items-end overflow-hidden rounded-sm bg-rule/60">
                <motion.div className={`w-full ${step === 0 ? "bg-accent" : "bg-signal"}`} animate={{ height: `${100 * chance}%` }}
                            transition={{ duration: 0.8, ease: EASE, delay: 0.05 * i }} />
                {step >= 1 && <span className="absolute inset-x-0 top-1 text-center font-mono text-[10px] text-ink-2">{percent(chance, 0)}</span>}
              </div>
              <span className="font-mono text-xs text-muted">{"ABCDEFGH"[i]}</span>
            </div>
          );
        })}
      </div>
      <p className="text-sm text-ink-2">
        {step === 0 && "relaxed amounts: how much of each stock the easier problem buys"}
        {step === 1 && `each qubit's starting chance of reading 1, kept between ${percent(EPSILON, 0)} and ${percent(1 - EPSILON, 0)}`}
        {step === 2 && "the layers then move probability from this tilted start"}
        {step === 3 && "measured both ways: the start alone, and after the quantum layers"}
      </p>
      {step >= 2 && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-wrap items-center gap-2 font-mono text-xs">
          {["Tilted start", "Score γ₁", "Mix β₁", "Score γ₂", "Mix β₂", "Measure"].map((block) => (
            <span key={block} className="rounded-full border border-rule-strong bg-paper px-3 py-1 text-ink-2">{block}</span>
          ))}
        </motion.div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ Mitigation: undo readout errors, check the count */

const READ = [1, 0, 1, 1, 0, 0, 1, 0];
const MISREAD = new Set([1, 5]);

export function MitigationExplainer({ noise }: { noise: Noise }) {
  const row = noise.summary.all.rows.find((r) => r.chip === "FakeFez" && r.mixer === "xy" && r.pairs_kept === 1 && r.depth === 2 && r.stocks === 10);
  const steps = [
    { title: "Real chips misread qubits",
      text: row
        ? `When a qubit is read, the chip sometimes reports the wrong value. On the noise model of IBM Fez a qubit was misread ${percent(row.readout_error.mean, 1)} of the time on average, so a 4-stock portfolio can come out with the wrong number of stocks.`
        : "When a qubit is read, the chip sometimes reports the wrong value." },
    { title: "Measure the mistakes",
      text: "Two extra calibration circuits on the same qubits: one prepares all 0s, one all 1s. Counting what comes back gives each qubit's misreading table: how often a 0 reads as 1 and a 1 as 0." },
    { title: "Undo them",
      text: "Inverting each qubit's table turns the observed counts into an estimate of what the circuit really produced. It fixes reading errors only, not errors in the gates." },
    { title: "Check the count",
      text: row
        ? `Our circuit always holds exactly 4 stocks, so any shot with another count must be an error, and is dropped. On 10-stock problems with 2 layers: ${times(row.raw_lift.mean)} better than guessing raw, ${times(row.mitigated_lift.mean)} mitigated, ${times(row.both_lift.mean)} mitigated and checked (perfect simulator: ${times(row.ideal_lift.mean)}).`
        : "Our circuit always holds exactly 4 stocks, so any shot with another count must be an error." },
  ];
  return (
    <Explainer label="Error mitigation" steps={steps} footnote="Qubits: an illustration of one shot. Numbers: the research runs (on a noisy IBM chip, XY circuit, all links).">
      {(step) => <MisreadPicture step={step} />}
    </Explainer>
  );
}

function MisreadPicture({ step }: { step: number }) {
  const misread = step === 0 || step === 3;
  const shown = READ.map((bit, i) => (misread && MISREAD.has(i) ? 1 - bit : bit));
  const count = shown.reduce((a, b) => a + b, 0);
  const ok = count === 4;
  return (
    <div className="flex min-h-72 flex-col justify-center gap-7">
      <div className="flex flex-wrap gap-2.5">
        {shown.map((bit, i) => {
          const wrong = misread && MISREAD.has(i);
          return (
            <motion.div key={i} animate={{ scale: wrong ? [1, 1.15, 1] : 1 }} transition={{ duration: 0.6, repeat: wrong ? Infinity : 0, repeatDelay: 1 }}
                        className={`flex h-11 w-11 items-center justify-center rounded-full border font-mono text-sm transition-colors duration-500 ${
                          wrong ? "border-bad bg-bad/15 text-bad" : bit ? "border-signal bg-signal text-paper" : "border-rule-strong text-muted"}`}>
              {bit}
            </motion.div>
          );
        })}
      </div>
      {step === 1 && (
        <motion.table initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="w-full max-w-sm text-sm">
          <thead><tr className="text-xs text-muted"><th className="py-1 text-left font-normal">prepared</th><th className="text-right font-normal">read 0</th><th className="text-right font-normal">read 1</th></tr></thead>
          <tbody className="tabular-nums">
            <tr className="border-t border-rule"><td className="py-1.5 text-ink">0</td><td className="text-right">98%</td><td className="text-right text-bad">2%</td></tr>
            <tr className="border-t border-rule"><td className="py-1.5 text-ink">1</td><td className="text-right text-bad">4%</td><td className="text-right">96%</td></tr>
          </tbody>
          <caption className="caption-bottom pt-2 text-left text-xs text-muted">one qubit's misreading table (illustrative numbers)</caption>
        </motion.table>
      )}
      {step === 2 && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="grid max-w-md grid-cols-2 gap-6">
          {[["observed", OWN.slice(0, 5)], ["corrected", OWN.slice(0, 5).map((v, i) => (i === 0 ? v * 1.35 : v * 0.85))]].map(([name, values]) => (
            <div key={String(name)}>
              <p className="mb-2 text-xs text-muted">{String(name)} chances</p>
              <div className="flex h-24 items-end gap-1.5">
                {(values as number[]).map((v, i) => (
                  <motion.div key={i} className={i === 0 ? "w-5 bg-signal" : "w-5 bg-series-1"} initial={{ height: 0 }} animate={{ height: `${80 * v}%` }} transition={{ duration: 0.7, ease: EASE }} />
                ))}
              </div>
            </div>
          ))}
        </motion.div>
      )}
      <p className={`text-sm ${step === 2 ? "text-ink-2" : ok ? "text-good" : "text-bad"}`}>
        {step === 2 ? "probability moves back to the portfolios the circuit really produced" : `${count} stocks read: ${ok ? "kept" : step === 3 ? "dropped by the count check" : "an error"}`}
      </p>
    </div>
  );
}
