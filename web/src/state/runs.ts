import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { useConnection } from "../api/connection";
import type { BacktestRequest, JobStatus, OptimiseRequest } from "../api/types";
import { FINISHED } from "../api/types";
import { addToHistory } from "../lib/history";

/** What the running screen needs to know about a job it didn't start itself (e.g. after a reload). */
export interface JobInfo {
  kind: "optimise" | "backtest";
  title: string;
  market: string;
  detail: string;
  /** Stages this run will go through, when known (optional ones like the noisy chip only if switched on). */
  stages?: string[];
}

/** Every stage an optimisation reports, in order (qapital/api/service.py and the engine). */
export const OPTIMISE_STAGES = [
  "Estimating returns and risk", "Building the score", "Tuning circuit", "Sampling portfolios", "Running on noisy chip",
  "Classical baselines", "Pruning study", "Turning the portfolio into orders",
];

const jobKey = (id: string) => `qapital.job.${id}`;

function remember(id: string, info: JobInfo) {
  try {
    sessionStorage.setItem(jobKey(id), JSON.stringify(info));
  } catch {
    // the running screen then shows a generic title
  }
}

export function jobInfo(id: string): JobInfo | null {
  try {
    const text = sessionStorage.getItem(jobKey(id));
    return text ? (JSON.parse(text) as JobInfo) : null;
  } catch {
    return null;
  }
}

/** Start an optimisation or a backtest on the live API, then go to its running screen. */
export function useStartRun() {
  const { live } = useConnection();
  const navigate = useNavigate();
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const start = useCallback(async (kind: JobInfo["kind"], request: OptimiseRequest | BacktestRequest, info: Omit<JobInfo, "kind">) => {
    if (!live) return;
    setStarting(true);
    setError(null);
    try {
      const { job_id: id } = kind === "optimise"
        ? await live.optimise(request as OptimiseRequest)
        : await live.backtest(request as BacktestRequest);
      remember(id, { kind, ...info });
      navigate(`/runs/${id}`);
    } catch (problem) {
      setError((problem as Error).message);
    } finally {
      setStarting(false);
    }
  }, [live, navigate]);

  return { start, starting, error, canStart: Boolean(live) };
}

/**
 * Follow a running job: live progress over the event stream (or polling), then on success remember it in the
 * history and move to its result page.
 */
export function useJob(id: string) {
  const { live, state } = useConnection();
  const navigate = useNavigate();
  const [status, setStatus] = useState<JobStatus | null>(null);

  useEffect(() => {
    if (!live) return undefined;
    return live.watch(id, (next) => {
      setStatus(next);
      if (next.status !== "done") return;
      const resultId = next.result?.result_id ?? next.backtest?.result_id;
      if (!resultId) return;
      const info = jobInfo(id);
      const kind = next.kind === "backtest" ? "backtest" : "optimise";
      addToHistory({
        id: resultId, kind, title: info?.title ?? (kind === "backtest" ? "Backtest" : "Optimisation"),
        market: info?.market ?? "", detail: info?.detail ?? "", createdAt: new Date().toISOString(),
      });
      navigate(kind === "backtest" ? `/backtest/${resultId}` : `/results/${resultId}`, { replace: true });
    });
  }, [live, id, navigate]);

  const cancel = useCallback(async () => {
    if (live) await live.cancel(id).catch(() => undefined);
  }, [live, id]);

  const finished = status != null && FINISHED.includes(status.status);
  return { status, cancel, finished, waiting: !live, connection: state };
}
