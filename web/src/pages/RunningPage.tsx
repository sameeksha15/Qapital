import { AnimatePresence, motion } from "motion/react";
import { useNavigate, useParams } from "react-router";
import { EASE } from "../components/motion";
import { Button, ButtonLink, Container, Kicker, Note } from "../components/ui";
import { WaveField } from "../components/WaveField";
import { jobInfo, OPTIMISE_STAGES, useJob } from "../state/runs";

const BACKTEST_STAGES = ["Rebalancing through history"];

/** A full navy screen: the wave moves faster while the job runs, the stage name changes in place. */
export function RunningPage() {
  const { jobId = "" } = useParams();
  const navigate = useNavigate();
  const info = jobInfo(jobId);
  const { status, cancel, waiting, connection } = useJob(jobId);
  const kind = status?.kind ?? info?.kind ?? "optimise";
  const progress = status?.progress ?? { stage: status?.status === "queued" ? "Waiting in the queue" : "Starting", step: 0, total: 1 };
  const stages = info?.stages ?? (kind === "backtest" ? BACKTEST_STAGES : OPTIMISE_STAGES);
  const current = stages.indexOf(progress.stage);
  const within = progress.total ? Math.min(1, progress.step / progress.total) : 0;
  const overall = current < 0 ? 0 : (current + within) / stages.length;
  const back = kind === "backtest" ? "/backtest" : "/";

  if (status?.status === "error" || status?.status === "cancelled") {
    return (
      <Container className="py-20">
        <Note tone={status.status === "error" ? "bad" : "neutral"} title={status.status === "error" ? "The run stopped" : "Run cancelled"}>
          {status.error ?? "Nothing was saved."}
        </Note>
        <ButtonLink to={back} variant="primary" className="mt-8">Back to the settings</ButtonLink>
      </Container>
    );
  }

  return (
    <section className="relative isolate flex min-h-[calc(100vh-57px)] items-center overflow-hidden bg-navy text-navy-ink">
      <div className="absolute inset-x-0 bottom-0 -z-10 h-[70%] opacity-90"><WaveField speed={4} /></div>
      <Container className="py-20">
        <Kicker onDark>{info?.title ?? (kind === "backtest" ? "Backtest" : "Optimisation")}{progress.elapsed_s != null && ` · ${Math.round(progress.elapsed_s)} s`}</Kicker>
        <div className="mt-5 min-h-18 overflow-hidden sm:min-h-21">
          <AnimatePresence mode="wait">
            <motion.h1 key={progress.stage} className="font-serif text-4xl sm:text-6xl" aria-live="polite"
                       initial={{ y: 40, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: -40, opacity: 0 }}
                       transition={{ duration: 0.45, ease: EASE }}>
              {waiting ? "Waiting for the live engine" : progress.stage}
            </motion.h1>
          </AnimatePresence>
        </div>
        {progress.total > 1 && <p className="mt-2 text-sm tabular-nums text-navy-muted">step {progress.step} of {progress.total}</p>}
        <div className="mt-8 h-px max-w-2xl bg-white/15" role="progressbar" aria-valuemin={0} aria-valuemax={100}
             aria-valuenow={Math.round(100 * overall)} aria-label="Progress">
          <motion.div className="h-px bg-signal" animate={{ width: `${100 * overall}%` }} transition={{ duration: 0.3, ease: "linear" }} />
        </div>
        {stages.length > 1 && (
          <ol className="mt-8 flex max-w-3xl flex-wrap gap-x-6 gap-y-3 text-sm">
            {stages.map((stage, i) => (
              <li key={stage} className={`flex items-center gap-2 transition-colors duration-500 ${
                i < current ? "text-navy-ink" : i === current ? "text-signal" : "text-navy-muted/60"}`}>
                <span className="font-mono text-xs">{String(i + 1).padStart(2, "0")}</span>{stage}
              </li>
            ))}
          </ol>
        )}
        {waiting && (
          <p className="mt-8 max-w-xl text-sm text-navy-muted">
            {connection === "waking" ? "The engine is waking up; this page follows the run as soon as it answers." : "The engine isn't reachable right now."}
          </p>
        )}
        <Button variant="onDark" className="mt-12" onClick={async () => {
          await cancel();
          navigate(back);
        }}>Cancel</Button>
      </Container>
    </section>
  );
}
