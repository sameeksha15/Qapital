// Calculations on a daily value series (one number per trading day), for the backtest charts.
// They match qapital/finance/risk.py: 252 trading days a year.

export const TRADING_DAYS = 252;

/** Fall from the highest value so far, on each day (0 at a new high, −0.25 when 25% below it). */
export function drawdowns(values: number[]): number[] {
  let peak = -Infinity;
  return values.map((value) => {
    peak = Math.max(peak, value);
    return value / peak - 1;
  });
}

/** Return over the trailing `window` days, on each day from day `window` on (earlier days are null). */
export function rollingReturn(values: number[], window = TRADING_DAYS): (number | null)[] {
  return values.map((value, i) => (i < window ? null : value / values[i - window] - 1));
}

/** Yearly volatility of daily returns over the trailing `window` days (earlier days are null). */
export function rollingVolatility(values: number[], window = TRADING_DAYS): (number | null)[] {
  const returns = values.map((value, i) => (i === 0 ? 0 : value / values[i - 1] - 1));
  let sum = 0;
  let squares = 0;
  return returns.map((r, i) => {
    if (i === 0) return null;
    sum += r;
    squares += r * r;
    if (i > window) {
      const old = returns[i - window];
      sum -= old;
      squares -= old * old;
    }
    if (i < window) return null;
    const mean = sum / window;
    const variance = Math.max(0, (squares - window * mean * mean) / (window - 1));
    return Math.sqrt(variance * TRADING_DAYS);
  });
}

/** Every `step`-th point plus the last one, to keep long daily series light in charts. */
export function thin<T>(points: T[], step: number): T[] {
  if (step <= 1) return points;
  return points.filter((_, i) => i % step === 0 || i === points.length - 1);
}
