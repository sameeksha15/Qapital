import { beforeEach, describe, expect, it } from "vitest";
import { DEFAULT_SETTINGS } from "../state/draft";
import { ago, describeCircuit, money, percent, portfolioName, sameStocks } from "./format";
import { addToHistory, clearHistory, removeFromHistory, type HistoryEntry } from "./history";
import { drawdowns, rollingReturn, rollingVolatility, thin } from "./series";

describe("format", () => {
  it("writes money in each market's own style", () => {
    expect(money(1_000_000, "INR")).toBe("₹10,00,000");
    expect(money(100_000, "USD")).toBe("$100,000");
    expect(money(12.345, "INR")).toBe("₹12.35");
  });

  it("never shows minus zero", () => {
    expect(percent(-0.00001)).toBe("0.0%");
  });

  it("names portfolios without exchange suffixes, in any order", () => {
    expect(portfolioName(["HDFCBANK.NS", "AAPL"])).toBe("HDFCBANK + AAPL");
    expect(sameStocks(["A", "B"], ["B", "A"])).toBe(true);
  });

  it("describes the circuit, including CVaR and pruning", () => {
    expect(describeCircuit(DEFAULT_SETTINGS)).toBe("XY (keeps K) · 2 layers · CVaR 25% · COBYLA");
    expect(describeCircuit({ ...DEFAULT_SETTINGS, mixer: "warm", pairs_kept: 0.5, cvar_alpha: 1, depth: 1 }))
      .toBe("Warm start · 1 layer · 50% links · mean · COBYLA");
  });

  it("says how long ago", () => {
    const now = Date.parse("2026-10-14T12:00:00Z");
    expect(ago("2026-10-14T11:59:40Z", now)).toBe("just now");
    expect(ago("2026-10-14T09:00:00Z", now)).toBe("3 hours ago");
  });
});

describe("series", () => {
  it("measures the fall from the previous high", () => {
    expect(drawdowns([100, 120, 90, 130])).toEqual([0, 0, -0.25, 0]);
  });

  it("gives trailing returns once the window is full", () => {
    const returns = rollingReturn([100, 110, 121], 1);
    expect(returns[0]).toBeNull();
    expect(returns[1]).toBeCloseTo(0.1, 10);
    expect(returns[2]).toBeCloseTo(0.1, 10);
  });

  it("gives zero volatility for steady growth and positive volatility otherwise", () => {
    const steady = Array.from({ length: 30 }, (_, i) => 100 * 1.01 ** i);
    expect(rollingVolatility(steady, 10)[29]).toBeCloseTo(0, 10);
    const bumpy = Array.from({ length: 30 }, (_, i) => 100 + (i % 2 ? 5 : -5));
    expect(rollingVolatility(bumpy, 10)[29]).toBeGreaterThan(0.5);
    expect(rollingVolatility(bumpy, 10)[5]).toBeNull();
  });

  it("thins long series but keeps the last point", () => {
    expect(thin([1, 2, 3, 4, 5], 2)).toEqual([1, 3, 5]);
    expect(thin([1, 2, 3, 4], 3)).toEqual([1, 4]);
  });
});

describe("history", () => {
  const entry = (id: string): HistoryEntry => ({ id, kind: "optimise", title: id, market: "nifty50", detail: "", createdAt: "2026-10-14T00:00:00Z" });
  const stored = () => JSON.parse(localStorage.getItem("qapital.history.v1") ?? "[]") as HistoryEntry[];

  beforeEach(() => clearHistory());

  it("keeps the newest first, once each", () => {
    addToHistory(entry("a"));
    addToHistory(entry("b"));
    addToHistory(entry("a"));
    expect(stored().map((e) => e.id)).toEqual(["a", "b"]);
    removeFromHistory("a");
    expect(stored().map((e) => e.id)).toEqual(["b"]);
  });

  it("keeps at most 40 runs", () => {
    for (let i = 0; i < 45; i++) addToHistory(entry(String(i)));
    expect(stored()).toHaveLength(40);
    expect(stored()[0].id).toBe("44");
  });
});
