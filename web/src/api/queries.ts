import { useQuery } from "@tanstack/react-query";
import { useConnection } from "./connection";
import { ApiError } from "./fetchJson";
import type { Estimator, JobStatus } from "./types";

// Every read the pages make, cached by TanStack Query. Keys include the mode, so data refreshes when the live API
// wakes up. Nothing is fetched while the connection is still being checked, so the page doesn't flash saved data.

export function useMarkets() {
  const { api, state } = useConnection();
  return useQuery({ queryKey: ["markets", api.mode], queryFn: () => api.markets(), enabled: state !== "checking" });
}

export function useStocks(market: string | undefined, estimator: Estimator = "shrunk-lw", windowYears = 3) {
  const { api, state } = useConnection();
  return useQuery({
    queryKey: ["stocks", api.mode, market, estimator, windowYears],
    queryFn: () => api.stocks(market!, estimator, windowYears),
    enabled: state !== "checking" && Boolean(market),
    placeholderData: (previous) => (previous?.market === market ? previous : undefined),
  });
}

export function useCorrelations(market: string | undefined) {
  const { api, state } = useConnection();
  return useQuery({
    queryKey: ["correlations", api.mode, market],
    queryFn: () => api.correlations(market!),
    enabled: state !== "checking" && Boolean(market),
  });
}

export function useDataStatus() {
  const { api, state } = useConnection();
  return useQuery({ queryKey: ["data-status", api.mode], queryFn: () => api.dataStatus(), enabled: state !== "checking" });
}

export function useSavedRuns() {
  const { saved } = useConnection();
  return useQuery({ queryKey: ["saved-runs"], queryFn: () => saved.runs(), staleTime: Infinity });
}

/** A finished run: from the live API when it is up, falling back to the saved runs (which hold the examples). */
export function useResult(id: string | undefined) {
  const { live, saved, state } = useConnection();
  return useQuery<JobStatus>({
    queryKey: ["result", id, live ? "live" : "saved"],
    enabled: Boolean(id) && state !== "checking",
    staleTime: Infinity,  // a finished result never changes
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 2,
    queryFn: async () => {
      if (live) {
        try {
          return await live.result(id!);
        } catch (error) {
          if (!(error instanceof ApiError && error.status === 404)) throw error;
        }
      }
      return saved.result(id!);
    },
  });
}
