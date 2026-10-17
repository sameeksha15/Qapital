import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "./fetchJson";
import type { Settings } from "./types";

// Experiment results ship with the website in public/research/, written by research/experiments/*.py on the current
// price snapshot. They are fixed findings, read the same way whether or not the live engine is up.
const base = `${import.meta.env.BASE_URL}research/`;

/** Mean, lowest and highest over every problem (and seed) of an experiment. */
export interface Spread {
  mean: number;
  min: number;
  max: number;
  n: number;
}

export type MarketKey = "nifty50" | "sp100";
export type Scope = "all" | MarketKey;

export interface RunInfo {
  experiment: string;
  snapshot: string;
  estimates: string;
  costs: string;
  dates?: string;
  started: string;
  minutes: number;
  qiskit: string;
  [key: string]: unknown;
}

type Mixer = Settings["mixer"];

/** One circuit of the grid, on today's 16-stock problem. */
export interface GridRun {
  market: MarketKey;
  mixer: Mixer;
  depth: number;
  pairs_kept: number;
  optimiser: Settings["optimiser"];
  lift: number;
  p_best: number;
  legal: number;
  closeness: number;
  found_best: boolean;
  gates: number;
  circuit_depth: number;
  qubits: number;
  warm_alone_lift: number | null;
  seconds: number;
  chosen: string;
}

export interface GridMarket {
  name: string;
  as_of: string;
  stocks: number;
  shortlist: string[];
  shortlist_best: string[];
  true_best: string[] | null;
  best_kept: boolean | null;
  legal_on_shortlist: number;
}

export interface Circuits {
  run_info: RunInfo;
  markets: Record<MarketKey, GridMarket>;
  runs: GridRun[];
}

interface Summaries<T> {
  run_info: RunInfo;
  summary: Record<Scope, T>;
}

export interface CircuitKey {
  mixer: Mixer;
  pairs_kept: number;
  depth: number;
}

export interface EqualQualityRow extends CircuitKey {
  lift: Spread;
  legal: Spread;
  closeness: Spread;
  gates: Spread;
  found_best: number;
}

export type EqualQuality = Summaries<{
  rows: EqualQualityRow[];
  problems: number;
  best_penalty: CircuitKey;
  cheapest_match: CircuitKey | null;
}>;

export interface Record3 {
  wins: number;
  ties: number;
  losses: number;
}

export interface FamilyRow {
  mixer: Mixer;
  cvar_alpha: number;
  depth: number;
  lift: Spread;
  p_best: Spread;
  closeness: Spread;
  legal: Spread;
  found_best: number;
  gates: Spread;
  warm_alone_lift?: Spread;
}

export type Families = Summaries<{
  rows: FamilyRow[];
  problems: number;
  cvar_vs_average: Record<string, Record3>;
  warm_vs_warm_alone: Record<string, { wins: number; losses: number; problems: number }>;
  warm_vs_xy: Record<string, Record3>;
}>;

export type NoiseStage = "ideal" | "raw" | "mitigated" | "postselected" | "both";

export type NoiseRow = {
  stocks: number;
  chip: string;
  mixer: Mixer;
  pairs_kept: number;
  depth: number;
  gates: Spread;
  readout_error: Spread;
  postselected_share: Spread;
} & { [K in `${NoiseStage}_${"lift" | "legal"}`]: Spread };

export type Noise = Summaries<{ rows: NoiseRow[]; problems: number }> & { stages: NoiseStage[] };

export interface OptimiserRow {
  depth: number;
  optimiser: Settings["optimiser"];
  start: "warm" | "random";
  lift: Spread;
  p_best: Spread;
  closeness: Spread;
  circuit_runs: Spread;
  seconds: Spread;
  found_best: number;
}

export type Optimisers = Summaries<{ rows: OptimiserRow[]; problems: number; seeds: number }>;

export interface CovarianceRow {
  version: string;
  next_year_return: Spread;
  next_year_volatility: Spread;
  next_year_sharpe: Spread;
  covariance_error: Spread;
}

export type Covariance = Summaries<{
  rows: CovarianceRow[];
  problems: number;
  vs_sample: Record<string, { lower_error: number; lower_volatility: number; same_portfolio: number; problems: number }>;
}>;

const research = <T>(file: string) => () => fetchJson<T>(`${base}${file}`);
const options = { staleTime: Infinity } as const;

export const useCircuits = () => useQuery({ queryKey: ["research", "circuits"], queryFn: research<Circuits>("circuits.json"), ...options });
export const useEqualQuality = () => useQuery({ queryKey: ["research", "equal"], queryFn: research<EqualQuality>("equal_quality.json"), ...options });
export const useFamilies = () => useQuery({ queryKey: ["research", "families"], queryFn: research<Families>("families.json"), ...options });
export const useNoise = () => useQuery({ queryKey: ["research", "noise"], queryFn: research<Noise>("noise.json"), ...options });
export const useOptimisers = () => useQuery({ queryKey: ["research", "optimisers"], queryFn: research<Optimisers>("optimisers.json"), ...options });
export const useCovariance = () => useQuery({ queryKey: ["research", "covariance"], queryFn: research<Covariance>("covariance.json"), ...options });
