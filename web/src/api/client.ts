import { ApiError, fetchJson } from "./fetchJson";
import type {
  BacktestRequest, Correlations, DataStatus, Estimator, JobCreated, JobStatus, MarketList, OptimiseRequest,
  SavedIndex, StockList,
} from "./types";
import { FINISHED } from "./types";

/** What every page can read, from the live API or from the saved runs. */
export interface ReadApi {
  mode: "live" | "saved";
  markets(): Promise<MarketList>;
  stocks(market: string, estimator?: Estimator, windowYears?: number): Promise<StockList>;
  correlations(market: string): Promise<Correlations>;
  dataStatus(): Promise<DataStatus>;
  /** A finished run, by its result id. */
  result(id: string): Promise<JobStatus>;
}

/** What only the live API can do: start, follow and cancel runs. */
export interface LiveApi extends ReadApi {
  mode: "live";
  url: string;
  health(timeoutMs: number): Promise<{ status: string; snapshot: string | null }>;
  optimise(request: OptimiseRequest): Promise<JobCreated>;
  backtest(request: BacktestRequest): Promise<JobCreated>;
  job(id: string): Promise<JobStatus>;
  cancel(id: string): Promise<JobStatus>;
  /** Calls `onStatus` on every change until the job ends; returns a function that stops following it. */
  watch(id: string, onStatus: (status: JobStatus) => void): () => void;
}

const POLL_MS = 1500;
const PROGRESS_EVENTS = ["progress", ...FINISHED];

export function createLiveApi(url: string): LiveApi {
  const base = url.replace(/\/$/, "");
  const call = <T>(method: string, path: string, body?: unknown, timeoutMs?: number) => fetchJson<T>(base + path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    timeoutMs,
  });
  const id = encodeURIComponent;

  const api: LiveApi = {
    mode: "live",
    url: base,
    health: (timeoutMs) => call("GET", "/health", undefined, timeoutMs),
    markets: () => call("GET", "/markets"),
    stocks: (market, estimator = "shrunk-lw", windowYears = 3) =>
      call("GET", `/markets/${id(market)}/stocks?estimator=${estimator}&window_years=${windowYears}`),
    correlations: (market) => call("GET", `/markets/${id(market)}/correlations`),
    dataStatus: () => call("GET", "/data/status"),
    result: (resultId) => call("GET", `/results/${id(resultId)}`),
    optimise: (request) => call("POST", "/optimise", request),
    backtest: (request) => call("POST", "/backtest", request),
    job: (jobId) => call("GET", `/jobs/${id(jobId)}`),
    cancel: (jobId) => call("DELETE", `/jobs/${id(jobId)}`),

    watch(jobId, onStatus) {
      let stopped = false;
      let timer: ReturnType<typeof setTimeout> | undefined;
      let source: EventSource | undefined;

      const poll = async () => {
        if (stopped) return;
        let status: JobStatus;
        try {
          status = await api.job(jobId);
        } catch (error) {
          status = { status: "error", error: (error as Error).message } as JobStatus;
        }
        if (stopped) return;
        onStatus(status);
        if (!FINISHED.includes(status.status)) timer = setTimeout(poll, POLL_MS);
      };

      if (typeof EventSource === "undefined") {
        poll();
      } else {
        source = new EventSource(`${base}/jobs/${id(jobId)}/events`);
        let ended = false;
        for (const name of PROGRESS_EVENTS) {
          source.addEventListener(name, (event) => {
            const status = JSON.parse((event as MessageEvent).data) as JobStatus;
            onStatus(status);
            if (FINISHED.includes(status.status)) {
              ended = true;
              source?.close();
            }
          });
        }
        source.onerror = () => {  // the stream broke (proxy, network): ask every few seconds instead
          source?.close();
          if (!ended && !stopped) poll();
        };
      }
      return () => {
        stopped = true;
        source?.close();
        clearTimeout(timer);
      };
    },
  };
  return api;
}

/** The saved runs in public/saved/ (scripts/build_saved_site.py): the same shapes, read-only. */
export function createSavedApi(base = `${import.meta.env.BASE_URL}saved/`): ReadApi & { runs(): Promise<SavedIndex> } {
  const get = <T>(path: string) => fetchJson<T>(base + path);
  return {
    mode: "saved",
    markets: () => get("markets.json"),
    stocks: (market) => get(`stocks/${encodeURIComponent(market)}.json`),
    correlations: (market) => get(`correlations/${encodeURIComponent(market)}.json`),
    dataStatus: () => get("data-status.json"),
    runs: () => get("runs.json"),
    async result(resultId) {
      try {
        return await get<JobStatus>(`results/${encodeURIComponent(resultId)}.json`);
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) {
          throw new ApiError("This result is kept on the live server, which isn't reachable right now.", 404);
        }
        throw error;
      }
    },
  };
}
