// The shapes the website and the API exchange, generated from the API itself (src/api/schema.d.ts), so the two can't
// drift apart. After changing the API: python -m scripts.export_openapi && npm run gen:api
import type { components } from "./schema";

type Schemas = components["schemas"];

export type Settings = Schemas["Settings"];
export type Market = Schemas["Market"];
export type MarketList = Schemas["MarketList"];
export type StockInfo = Schemas["StockInfo"];
export type StockList = Schemas["StockList"];
export type Correlations = Schemas["Correlations"];
export type DataStatus = Schemas["DataStatus"];
export type Holding = Schemas["Holding"];
export type OptimiseRequest = Schemas["OptimiseRequest"];
export type BacktestRequest = Schemas["BacktestRequest"];
export type JobCreated = Schemas["JobCreated"];
export type JobStatus = Schemas["JobStatus"];
export type Progress = Schemas["Progress"];
export type FullResult = Schemas["FullResult"];
export type QuantumResult = Schemas["QuantumResult"];
export type SampledPortfolio = Schemas["SampledPortfolio"];
export type NoiseComparison = Schemas["NoiseComparison"];
export type ReportRow = Schemas["ReportRow"];
export type Frontier = Schemas["Frontier"];
export type Dataset = Schemas["Dataset"];
export type Optimal = Schemas["Optimal"];
export type Allocation = Schemas["Allocation"];
export type Order = Schemas["Order"];
export type Estimation = Schemas["Estimation"];
export type CostInfo = Schemas["CostInfo"];
export type PruningRow = Schemas["PruningRow"];
export type BacktestResult = Schemas["BacktestResult"];
export type StrategyRun = Schemas["StrategyRun"];
export type Performance = Schemas["Performance"];
export type Estimator = OptimiseRequest["estimator"];
export type JobState = JobStatus["status"];
export type JobKind = JobStatus["kind"];

export const FINISHED: JobState[] = ["done", "error", "cancelled"];

/** Shots per run, fixed by the engine (qapital/quantum/solver.py SHOTS). */
export const SHOTS = 4096;

/** Most stocks the circuit can hold: 16 qubits on the perfect simulator, 12 with noise. */
export const MAX_QUBITS = 16;
export const MAX_NOISY_QUBITS = 12;

/** A saved run in public/saved/runs.json. */
export interface SavedRun {
  id: string;
  title: string;
  description: string;
  kind: "optimise" | "backtest";
  market: string;
  request: OptimiseRequest | BacktestRequest;
}

export interface SavedIndex {
  snapshot: string;
  runs: SavedRun[];
}
