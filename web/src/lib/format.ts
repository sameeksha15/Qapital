import type { Settings } from "../api/types";

export const APP_NAME = "Qapital";

/** Fixed decimals without a "-0.0" for tiny negative numbers. */
function rounded(x: number, digits: number): string {
  const value = Number(x.toFixed(digits));
  return (value === 0 ? 0 : value).toFixed(digits);
}

export const percent = (x: number, digits = 1) => `${rounded(100 * x, digits)}%`;
export const signedPercent = (x: number, digits = 1) => `${x > 0 ? "+" : ""}${percent(x, digits)}`;
export const decimal = (x: number, digits = 2) => rounded(x, digits);
export const times = (x: number) => `${x.toFixed(1)}×`; // one decimal, like the engine's verdict
export const whole = (x: number) => Math.round(x).toLocaleString("en-US");
export const seconds = (s: number) => (s < 1 ? `${Math.round(s * 1000)} ms` : `${s.toFixed(s < 10 ? 1 : 0)} s`);

const LOCALES: Record<string, string> = { INR: "en-IN", USD: "en-US" };

/** Money in the market's currency: ₹10,00,000 or $100,000. `digits` defaults to none above 1,000. */
export function money(amount: number, currency = "INR", digits?: number): string {
  const places = digits ?? (Math.abs(amount) >= 1000 ? 0 : 2);
  return new Intl.NumberFormat(LOCALES[currency] ?? "en-US", {
    style: "currency", currency, minimumFractionDigits: places, maximumFractionDigits: places,
  }).format(amount);
}

/** "HDFCBANK.NS" → "HDFCBANK" */
export const shortName = (ticker: string) => ticker.replace(/\.(NS|BO)$/, "");
export const portfolioName = (tickers: string[]) => tickers.map(shortName).join(" + ") || "(nothing)";

/** Chart label; on narrow screens the second half of the names goes on a new line. */
export function portfolioLabel(tickers: string[], twoLines: boolean): string {
  if (!twoLines || tickers.length < 2) return portfolioName(tickers);
  const half = Math.ceil(tickers.length / 2);
  return `${portfolioName(tickers.slice(0, half))} +<br>${portfolioName(tickers.slice(half))}`;
}

export const sameStocks = (a: string[], b: string[]) => [...a].sort().join() === [...b].sort().join();

export const MIXER_NAMES: Record<Settings["mixer"], string> = {
  xy: "XY (keeps K)",
  standard: "Penalty",
  warm: "Warm start",
};
export const mixerName = (mixer: Settings["mixer"]) => MIXER_NAMES[mixer];
export const layers = (depth: number) => `${depth} layer${depth > 1 ? "s" : ""}`;

export function describeCircuit(settings: Settings): string {
  const parts = [mixerName(settings.mixer), layers(settings.depth)];
  if (settings.pairs_kept < 1) parts.push(`${percent(settings.pairs_kept, 0)} links`);
  parts.push(settings.cvar_alpha < 1 ? `CVaR ${percent(settings.cvar_alpha, 0)}` : "mean");
  parts.push(settings.optimiser);
  return parts.join(" · ");
}

export const year = (date: string) => date.slice(0, 4);
export const years = ([start, end]: readonly [string, string] | string[]) =>
  (year(start) === year(end) ? year(start) : `${year(start)}–${year(end)}`);

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-10-12" → "12 Oct 2026" */
export function day(date: string): string {
  const [y, m, d] = date.slice(0, 10).split("-").map(Number);
  return `${d} ${MONTHS[m - 1]} ${y}`;
}

/** "3 minutes ago", for the run history. */
export function ago(iso: string, now = Date.now()): string {
  const minutes = Math.round((now - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} minute${minutes > 1 ? "s" : ""} ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours > 1 ? "s" : ""} ago`;
  const days = Math.round(hours / 24);
  return days < 30 ? `${days} day${days > 1 ? "s" : ""} ago` : day(iso);
}

export const ESTIMATOR_NAMES = {
  "shrunk-lw": "Shrunk returns + Ledoit-Wolf risk",
  shrunk: "Shrunk returns + sample risk",
  historical: "Plain historical averages",
} as const;
