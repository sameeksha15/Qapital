import { useMemo, useState } from "react";
import type { BacktestResult } from "../../api/types";
import { money } from "../../lib/format";
import { drawdowns, rollingReturn, rollingVolatility, thin } from "../../lib/series";
import { useColors, type Colors } from "../../lib/theme";
import { Segmented } from "../ui";
import { Plot, type Trace } from "./Plot";

/** One colour per line: the index in neutral ink, strategies in the series colours, QAOA in signal orange. */
export function lineColors(run: BacktestResult, colors: Colors): Map<string, string> {
  const palette = [colors.series1, colors.series3, colors.accent, colors.muted];
  const map = new Map<string, string>();
  let next = 0;
  for (const strategy of run.strategies) {
    map.set(strategy.name, strategy.name.startsWith("QAOA") ? colors.series2 : palette[next++ % palette.length]);
  }
  map.set(run.benchmark.name, colors.ink2);
  return map;
}

function lines(run: BacktestResult) {
  return [...run.strategies, run.benchmark];
}

/** Daily series are thinned to about 600 points per line; the shape is the same and the page stays quick. */
function useThinned(run: BacktestResult) {
  return useMemo(() => {
    const step = Math.ceil(run.dates.length / 600);
    return { step, dates: thin(run.dates, step) };
  }, [run]);
}

/** The value of the money in each strategy and in the index, from the same starting amount. */
export function EquityChart({ run, height = 420 }: { run: BacktestResult; height?: number }) {
  const colors = useColors();
  const [scale, setScale] = useState<"linear" | "log">("linear");
  const { step, dates } = useThinned(run);
  const palette = lineColors(run, colors);
  const data: Trace[] = lines(run).map((line) => ({
    type: "scatter", mode: "lines", name: line.name, x: dates, y: thin(line.values, step),
    line: { color: palette.get(line.name), width: line === run.benchmark ? 1.5 : 2, dash: line === run.benchmark ? "dot" : "solid" },
    hovertemplate: `${line.name}<br>%{x}: %{customdata}<extra></extra>`,
    customdata: thin(line.values, step).map((v) => money(v, run.currency)),
  }));
  return (
    <div>
      <Segmented size="sm" value={scale} onChange={setScale}
                 options={[{ value: "linear" as const, label: "Money" }, { value: "log" as const, label: "Growth (log scale)" }]} />
      <Plot colors={colors} height={height} data={data}
            label={`Line chart of the value of ${money(run.capital, run.currency)} in each strategy and the index, ${run.start} to ${run.end}`}
            layout={{
              showlegend: true,
              hovermode: "x unified",
              xaxis: { type: "date" },
              yaxis: { type: scale, title: { text: `value (${run.currency})` }, tickformat: scale === "log" ? "~s" : "~s" },
            }} />
    </div>
  );
}

/** How far below its previous high each strategy was, every day. */
export function DrawdownChart({ run, height = 300 }: { run: BacktestResult; height?: number }) {
  const colors = useColors();
  const { step, dates } = useThinned(run);
  const palette = lineColors(run, colors);
  const data: Trace[] = lines(run).map((line) => ({
    type: "scatter", mode: "lines", name: line.name, x: dates, y: thin(drawdowns(line.values), step).map((d) => 100 * d),
    line: { color: palette.get(line.name), width: 1.5, dash: line === run.benchmark ? "dot" : "solid" },
    hovertemplate: `${line.name}<br>%{x}: %{y:.1f}%<extra></extra>`,
  }));
  return (
    <Plot colors={colors} height={height} data={data} label="Line chart of each strategy's fall from its previous high"
          layout={{
            showlegend: true,
            hovermode: "x unified",
            xaxis: { type: "date" },
            yaxis: { ticksuffix: "%", title: { text: "below the previous high" } },
          }} />
  );
}

/** Trailing one-year return or volatility, so good and bad stretches show up. */
export function RollingChart({ run, height = 300 }: { run: BacktestResult; height?: number }) {
  const colors = useColors();
  const [measure, setMeasure] = useState<"return" | "volatility">("return");
  const { step, dates } = useThinned(run);
  const palette = lineColors(run, colors);
  const data: Trace[] = lines(run).map((line) => {
    const values = measure === "return" ? rollingReturn(line.values) : rollingVolatility(line.values);
    return {
      type: "scatter", mode: "lines", name: line.name, x: dates,
      y: thin(values, step).map((v) => (v == null ? null : 100 * v)),
      line: { color: palette.get(line.name), width: 1.5, dash: line === run.benchmark ? "dot" : "solid" },
      hovertemplate: `${line.name}<br>%{x}: %{y:.1f}%<extra></extra>`,
    };
  });
  return (
    <div>
      <Segmented size="sm" value={measure} onChange={setMeasure}
                 options={[{ value: "return" as const, label: "1-year return" }, { value: "volatility" as const, label: "1-year volatility" }]} />
      <Plot colors={colors} height={height} data={data}
            label={`Line chart of each strategy's trailing one-year ${measure}`}
            layout={{
              showlegend: true,
              hovermode: "x unified",
              xaxis: { type: "date" },
              yaxis: { ticksuffix: "%", title: { text: measure === "return" ? "return over the past year" : "volatility over the past year" } },
            }} />
    </div>
  );
}
