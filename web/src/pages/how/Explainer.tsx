import { AnimatePresence, motion, useInView, useReducedMotion } from "motion/react";
import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { ArrowLeftIcon, ArrowRightIcon, PauseIcon, PlayIcon } from "../../components/icons";
import { EASE } from "../../components/motion";

const STEP_MS = 5500;

/**
 * One idea told in numbered steps: `children(step)` draws the picture for the current step, the story sits beside it.
 * It plays through once when it first scrolls into view. Back, Next, Play, the arrow keys or a click on a step take over.
 */
export interface Step {
  title: string;
  text: string;
}

interface ExplainerProps {
  label: string;
  steps: Step[];
  footnote?: ReactNode;
  children: (step: number) => ReactNode;
}

export function Explainer({ label, steps, footnote, children }: ExplainerProps) {
  const id = useId();
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.45 });
  const reduce = useReducedMotion();
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const last = steps.length - 1;

  useEffect(() => {
    if (inView && !reduce) setPlaying(true);
  }, [inView, reduce]);

  useEffect(() => {
    if (!playing) return undefined;
    const timer = setTimeout(() => {
      if (step < last) setStep(step + 1);
      if (step + 1 >= last) setPlaying(false);
    }, STEP_MS);
    return () => clearTimeout(timer);
  }, [playing, step, last]);

  const go = (next: number) => {
    setPlaying(false);
    setStep(Math.max(0, Math.min(last, next)));
  };
  const toggle = () => {
    if (playing) return setPlaying(false);
    if (step === last) setStep(0);
    return setPlaying(true);
  };
  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key === "ArrowRight") go(step + 1);
    else if (event.key === "ArrowLeft") go(step - 1);
    else return;
    event.preventDefault();
  };

  return (
    <div ref={ref} role="group" aria-label={label} tabIndex={0} onKeyDown={onKeyDown}
         className="grid gap-x-10 gap-y-8 rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-accent/40 lg:grid-cols-[minmax(0,1.45fr)_minmax(0,1fr)]">
      <figure className="min-w-0">
        {children(step)}
        {footnote && <figcaption className="mt-3 text-xs leading-relaxed text-muted">{footnote}</figcaption>}
      </figure>

      <div className="min-w-0">
        <ol className="border-l border-rule">
          {steps.map((item, i) => (
            <li key={item.title} className="relative">
              {i === step && (
                <motion.span layoutId={`${id}-marker`} className="absolute -left-px inset-y-0 w-0.5 bg-signal"
                             transition={{ type: "spring", stiffness: 380, damping: 34 }} />
              )}
              <button type="button" onClick={() => go(i)} aria-current={i === step ? "step" : undefined}
                      className={`flex w-full gap-2.5 py-2 pl-5 text-left text-sm transition-colors ${
                        i === step ? "font-medium text-ink" : "text-muted hover:text-ink-2"}`}>
                <span className="mt-px font-mono text-xs text-signal/80">{String(i + 1).padStart(2, "0")}</span>
                {item.title}
              </button>
              <AnimatePresence initial={false}>
                {i === step && (
                  <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}
                              transition={{ duration: 0.4, ease: EASE }} className="overflow-hidden">
                    <p className="pb-3 pl-12 pr-2 text-sm leading-relaxed text-ink-2">{item.text}</p>
                  </motion.div>
                )}
              </AnimatePresence>
            </li>
          ))}
        </ol>

        <div className="mt-5 flex items-center gap-2 pl-5">
          <RoundButton label="Previous step" onClick={() => go(step - 1)} disabled={step === 0}><ArrowLeftIcon /></RoundButton>
          <RoundButton label={playing ? "Pause" : step === last ? "Play again" : "Play"} onClick={toggle} strong>
            {playing ? <PauseIcon /> : <PlayIcon />}
          </RoundButton>
          <RoundButton label="Next step" onClick={() => go(step + 1)} disabled={step === last}><ArrowRightIcon /></RoundButton>
          <div className="ml-3 flex-1">
            <p className="font-mono text-xs text-muted">step {step + 1} of {steps.length}</p>
            <div className="mt-1.5 h-px bg-rule">
              {playing && (
                <motion.div key={step} className="h-full bg-signal" initial={{ width: "0%" }} animate={{ width: "100%" }}
                            transition={{ duration: STEP_MS / 1000, ease: "linear" }} />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function RoundButton({ label, onClick, disabled = false, strong = false, children }: {
  label: string; onClick: () => void; disabled?: boolean; strong?: boolean; children: ReactNode;
}) {
  return (
    <button type="button" aria-label={label} title={label} onClick={onClick} disabled={disabled}
            className={`flex h-9 w-9 items-center justify-center rounded-full border transition disabled:opacity-30 ${
              strong ? "border-ink bg-ink text-paper hover:bg-ink/85" : "border-rule-strong text-ink hover:border-ink"}`}>
      {children}
    </button>
  );
}

/** Steps through a fixed list of states on a timer while `running` (for small looping animations inside a step). */
export function useTicker(running: boolean, every = 1400): number {
  const reduce = useReducedMotion();
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!running || reduce) return undefined;
    const timer = setInterval(() => setTick((t) => t + 1), every);
    return () => clearInterval(timer);
  }, [running, every, reduce]);
  return tick;
}
