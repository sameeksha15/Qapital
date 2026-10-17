import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";
import { useResult } from "../../api/queries";
import { useCircuits, useFamilies, useNoise } from "../../api/research";
import { SectionIndex } from "../../components/SectionIndex";
import { EASE, Reveal } from "../../components/motion";
import { Container, Hero, Kicker, Loading, Note, Section } from "../../components/ui";
import { DickeExplainer, FineExplainer, MixerExplainer, PruneExplainer } from "./DesignVisuals";
import { LayerExplainer, QubitsExplainer, ScoreExplainer, TuneExplainer } from "./MethodVisuals";
import { CvarExplainer, MitigationExplainer, WarmExplainer } from "./UpgradeVisuals";

const STEPS = [
  { title: "Prices become returns and risk", text: "Three years of daily prices from the nightly snapshot give each stock's expected yearly return and how pairs of stocks move together, shrunk towards the middle so last year's winners aren't over-trusted." },
  { title: "One score for every portfolio", text: "Risk minus return plus real trading costs: the same formula for every method. The rules (how many stocks, how many per sector) are part of the problem." },
  { title: "The score becomes a circuit", text: "Each stock becomes a qubit and the score becomes the circuit's energy: good portfolios have low energy." },
  { title: "Tune, then sample", text: "A classical optimiser turns the circuit's knobs until good portfolios come out often. The circuit then runs 4,096 times and we keep the best legal portfolio it produced." },
  { title: "Check honestly", text: "Every answer is compared with the best portfolio (proven by trying every one when the list allows, otherwise the best any method found), with classical methods, and with blind guessing using the same number of tries. Then it becomes whole-share orders, and a walk-forward backtest shows how the strategy would have done." },
];

const SECTIONS = [
  { id: "overview", label: "Five steps" },
  { id: "qubits", label: "Stocks become qubits" },
  { id: "energy", label: "Score becomes energy" },
  { id: "layer", label: "One QAOA layer" },
  { id: "tuning", label: "Tune, then sample" },
  { id: "fine", label: "The rule as a fine" },
  { id: "start", label: "A legal start" },
  { id: "mixer", label: "The XY ring mixer" },
  { id: "pruning", label: "Pruning" },
  { id: "central", label: "The central idea" },
  { id: "cvar", label: "CVaR" },
  { id: "warm", label: "Warm start" },
  { id: "mitigation", label: "Error mitigation" },
  { id: "numbers", label: "Reading the numbers" },
];

export function HowItWorksPage() {
  const reduce = useReducedMotion();
  const saved = useResult("nifty50-default");
  const demo = { data: saved.data?.result ?? undefined, error: saved.error };
  const grid = useCircuits();
  const families = useFamilies();
  const noise = useNoise();

  return (
    <>
      <Hero>
        <Kicker onDark>How it works</Kicker>
        <h1 className="mt-5 max-w-3xl font-serif text-4xl leading-[1.12] sm:text-[52px]">
          About 10 billion possible portfolios. <em className="text-signal">One quantum circuit.</em>
        </h1>
        <p className="mt-6 max-w-2xl leading-relaxed text-navy-muted">
          An investor wants a few stocks out of many: high return, low risk, at most a set number per sector, low fees.
          With 50 stocks and 10 picks there are about 10 billion choices. We search them with a quantum algorithm (QAOA)
          and compare it, honestly, with classical methods.
        </p>
        <p className="mt-8 font-mono text-xs text-navy-muted">
          Each idea below plays once as it comes into view. Step through it with Back and Next, or the ← → keys.
        </p>
      </Hero>

      <Container className="pb-20">
        <div className="grid gap-x-12 lg:grid-cols-[180px_minmax(0,1fr)]">
          <SectionIndex sections={SECTIONS} />
          <div className="min-w-0">
            <Section id="overview" number="01" title="From prices to a portfolio" note="Five steps, the same for every run.">
              <ol className="relative">
                <motion.span aria-hidden="true" className="absolute left-2.75 top-2 h-[calc(100%-1rem)] w-px origin-top bg-rule-strong"
                             initial={{ scaleY: reduce ? 1 : 0 }} whileInView={{ scaleY: 1 }} viewport={{ once: true, amount: 0.3 }}
                             transition={{ duration: 1.6, ease: EASE }} />
                {STEPS.map((step, i) => (
                  <Reveal as="li" key={step.title} delay={0.15 * i} className="relative grid grid-cols-[24px_minmax(0,1fr)] gap-x-5 pb-9 last:pb-0">
                    <span className="relative z-10 mt-1 flex h-6 w-6 items-center justify-center rounded-full border border-ink bg-paper font-mono text-[11px] text-ink">
                      {i + 1}
                    </span>
                    <div>
                      <h3 className="font-serif text-xl text-ink">{step.title}</h3>
                      <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-ink-2">{step.text}</p>
                    </div>
                  </Reveal>
                ))}
              </ol>
            </Section>

            <Part number="Part 1" title="The method" />
            <Section id="qubits" number="02" title="Stocks become qubits" stacked
                     note="A qubit is a switch that ends up 0 or 1 when you look at it. Until then, the circuit holds every pattern of switches at once.">
              <WithData state={demo} what="the saved run">{(result) => <QubitsExplainer result={result} />}</WithData>
            </Section>
            <Section id="energy" number="03" title="The score becomes an energy" stacked
                     note="The circuit only understands one number per qubit and one per pair. This is how the investor's score is written in those terms (a QUBO, then a cost Hamiltonian).">
              <ScoreExplainer />
            </Section>
            <Section id="layer" number="04" title="One QAOA layer: a score step, then a mixing step" stacked
                     note="The score step marks good portfolios by turning their phases; the mixing step turns those marks into higher chances.">
              <WithData state={demo} what="the saved run">{(result) => <LayerExplainer result={result} />}</WithData>
            </Section>
            <Section id="tuning" number="05" title="Tune the knobs, then take 4,096 shots" stacked
                     note="The quantum circuit makes the portfolios; a normal computer only tunes its knobs and checks the answers.">
              <WithData state={demo} what="the saved run">{(result) => <TuneExplainer result={result} />}</WithData>
            </Section>

            <Part number="Part 2" title="Our design choices" />
            <Section id="fine" number="06" title="The standard way: the rule as a fine" stacked
                     note="Standard QAOA lets the circuit break the “buy exactly 4” rule and charges a fine for it. The fine has a hidden cost.">
              <WithData state={grid} what="the research results">{(value) => <FineExplainer grid={value} />}</WithData>
            </Section>
            <Section id="start" number="07" title="Our way, part 1: start with legal portfolios only" stacked
                     note="If the circuit can never hold a wrong number of stocks, it never needs the fine.">
              <WithData state={grid} what="the research results">{(value) => <DickeExplainer grid={value} />}</WithData>
            </Section>
            <Section id="mixer" number="08" title="Our way, part 2: mix without breaking the rule" stacked
                     note="The mixing step is where weight moves between portfolios, so it is where the rule has to hold.">
              <MixerExplainer />
            </Section>
            <Section id="pruning" number="09" title="Our way, part 3: prune the weak links" stacked
                     note="With the fine gone, every remaining pair link comes from the data, and links between stocks that barely move together can go.">
              <WithData state={grid} what="the research results">{(value) => <PruneExplainer grid={value} />}</WithData>
            </Section>

            <Section id="central" number="10" title="How you enforce the rules decides how big the circuit is" stacked
                     note={<>Two-qubit gates cause most errors on real chips. Honestly counted: each XY swap costs more gates than one fine link, so
                       at the same number of layers with every link kept, our circuit is <em>larger</em>. What the design buys is quality per gate: every
                       shot is legal, no effort goes into learning the rule, and the remaining links can be pruned. Whether that is worth the extra gates
                       is measured, problem by problem, on the Research page.</>}>
              <div className="grid gap-12 md:grid-cols-2">
                <Wiring title="Standard circuit: rules as fines" links="all"
                        text="“Pick exactly 4” is added as a fine. That fine links every pair of stocks, so the score step needs a gate for all 28 pairs, whatever the data says, and the circuit spends its effort learning not to break the rule." />
                <Wiring title="Our circuit: rules built in, weak links pruned" links="pruned"
                        text="The circuit only ever swaps a chosen stock for an unchosen one, so it always holds exactly 4. The fine disappears from the score step, and links between stocks that barely move together can be dropped. (The swaps themselves cost gates too: a ring of them per layer.)" />
              </div>
            </Section>

            <Part number="Part 3" title="Getting more out of the circuit" />
            <Section id="cvar" number="11" title="Tune for the best shots (CVaR)" stacked
                     note="We keep only the best portfolio the circuit produces, so the knobs should chase the best shots, not the average one.">
              <WithData state={families} what="the research results">{(value) => <CvarExplainer families={value} />}</WithData>
            </Section>
            <Section id="warm" number="12" title="Start near the classical answer (warm start)" stacked
                     note="A quick classical solution of an easier problem gives the circuit a head start; the honest question is what the quantum layers add to it.">
              <WithData state={families} what="the research results">{(value) => <WarmExplainer families={value} />}</WithData>
            </Section>
            <Section id="mitigation" number="13" title="Clean up the chip's mistakes (error mitigation)" stacked
                     note="Two cheap corrections for real hardware: undo reading errors, and drop shots that break the stock count.">
              <WithData state={noise} what="the research results">{(value) => <MitigationExplainer noise={value} />}</WithData>
            </Section>

            <Section id="numbers" number="14" title="Reading the numbers">
              <div className="grid gap-10 md:grid-cols-3">
                <Term title="Better than random">How often the circuit lands on the best portfolio, compared with picking a legal portfolio blindly the same number of times. 1× is luck.</Term>
                <Term title="Two-qubit gates">The steps that link two qubits. On real chips they cause most errors, so fewer of them means answers survive the noise better.</Term>
                <Term title="What we don't claim">A normal computer solves these sizes in a fraction of a second. We show what the quantum method needs to compete, not a speed advantage.</Term>
              </div>
            </Section>
          </div>
        </div>
      </Container>
    </>
  );
}

function Part({ number, title }: { number: string; title: string }) {
  return (
    <Reveal className="pb-2 pt-14">
      <p className="font-mono text-xs uppercase tracking-[0.14em] text-signal">{number}</p>
      <p className="mt-1 font-serif text-3xl text-ink">{title}</p>
    </Reveal>
  );
}

/** Shows `children(value)` once the data has loaded, a loading line until then, and a friendly note if it failed. */
function WithData<T>({ state, what, children }: { state: { data?: T; error: Error | null }; what: string; children: (value: T) => ReactNode }) {
  if (state.error) return <Note tone="bad" title={`Couldn't load ${what}`}>{state.error.message}</Note>;
  if (!state.data) return <Loading>Loading {what}…</Loading>;
  return <>{children(state.data)}</>;
}

function Term({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Reveal className="border-t border-ink pt-4">
      <h3 className="font-serif text-lg text-ink">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-ink-2">{children}</p>
    </Reveal>
  );
}

/** Eight qubits on a circle: either every pair linked, or a ring plus a few strong links. Links draw in one by one. */
function Wiring({ title, text, links }: { title: string; text: string; links: "all" | "pruned" }) {
  const reduce = useReducedMotion();
  const n = 8;
  const points: [number, number][] = Array.from({ length: n }, (_, i) => {
    const angle = (2 * Math.PI * i) / n - Math.PI / 2;
    return [80 + 60 * Math.cos(angle), 80 + 60 * Math.sin(angle)];
  });
  const pairs: [number, number][] = [];
  for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) pairs.push([i, j]);
  const lines: [number, number][] = links === "all" ? pairs : [...points.map((_, i): [number, number] => [i, (i + 1) % n]), [0, 3], [2, 6], [1, 5]];
  const color = links === "all" ? "var(--muted)" : "var(--signal)";
  return (
    <figure>
      <svg viewBox="0 0 160 160" className="h-52 w-52" role="img"
           aria-label={links === "all" ? "Eight qubits with all 28 pairs linked" : "Eight qubits linked in a ring plus three strong pairs"}>
        {lines.map(([i, j], k) => (
          <motion.line key={`${i}-${j}`} x1={points[i][0]} y1={points[i][1]} x2={points[j][0]} y2={points[j][1]}
                       stroke={color} strokeWidth="1.2" strokeOpacity={links === "all" ? 0.6 : 0.95}
                       initial={{ pathLength: reduce ? 1 : 0 }} whileInView={{ pathLength: 1 }} viewport={{ once: true, amount: 0.4 }}
                       transition={{ duration: 0.5, delay: 0.04 * k, ease: EASE }} />
        ))}
        {points.map(([x, y], i) => <circle key={i} cx={x} cy={y} r="7" fill="var(--paper)" stroke="var(--ink)" strokeWidth="1.5" />)}
      </svg>
      <figcaption className="mt-4">
        <p className="font-serif text-lg text-ink">{title}</p>
        <p className="mt-1.5 text-sm leading-relaxed text-ink-2">{text}</p>
        <p className="mt-2 font-mono text-xs text-muted">{lines.length} links</p>
      </figcaption>
    </figure>
  );
}
