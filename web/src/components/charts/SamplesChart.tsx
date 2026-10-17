import { useState } from "react";
import { portfolioLabel, sameStocks } from "../../lib/format";
import type { QuantumResult, SampledPortfolio } from "../../api/types";
import { useColors, useIsNarrow } from "../../lib/theme";
import { Segmented } from "../ui";
import { Plot, type Trace } from "./Plot";

/**
 * The most frequent portfolios among the shots, coloured best / other legal / rule-breaking, with a line at how
 * often a random legal guess lands on any one portfolio. A switch hides the rule-breakers.
 */
interface SamplesChartProps {
  quantum: QuantumResult;
  best: string[];
  numValid?: number | null;
  shots: number;
  limit?: number;
}

export function SamplesChart({ quantum, best, numValid, shots, limit = 20 }: SamplesChartProps) {
  const colors = useColors();
  const narrow = useIsNarrow();
  const [legalOnly, setLegalOnly] = useState(false);
  const label = (sample: SampledPortfolio) => portfolioLabel(sample.stocks, narrow);
  const samples = quantum.top_samples.filter((s) => !legalOnly || s.valid).slice(0, limit);
  const kinds = [
    { name: "Best portfolio", color: colors.series2, keep: (s: SampledPortfolio) => s.valid && sameStocks(s.stocks, best) },
    { name: "Other legal", color: colors.series1, keep: (s: SampledPortfolio) => s.valid && !sameStocks(s.stocks, best) },
    { name: "Breaks a rule", color: colors.neutral, keep: (s: SampledPortfolio) => !s.valid },
  ];
  const order = samples.map(label).reverse();
  const data: Trace[] = kinds.map((kind) => {
    const shown = samples.filter(kind.keep);
    return {
      type: "bar", orientation: "h", name: kind.name, marker: { color: kind.color },
      y: shown.map(label), x: shown.map((s) => (100 * s.count) / shots),
      customdata: shown.map((s) => [s.count, s.score]),
      hovertemplate: "%{y}<br>%{customdata[0]} shots (%{x:.2f}%)<br>score %{customdata[1]:.4f}<extra></extra>",
    };
  });
  const guess = numValid ? 100 / numValid : null;
  if (guess && order.length) {
    data.push({ type: "scatter", mode: "lines", name: `Random legal guess (${guess.toFixed(2)}% each)`,
                x: [guess, guess], y: [order[0], order[order.length - 1]], line: { color: colors.muted, width: 1.5 },
                hoverinfo: "skip" });
  }
  return (
    <div>
      <Segmented size="sm" value={legalOnly} onChange={setLegalOnly}
                 options={[{ value: false, label: "All portfolios" }, { value: true, label: "Legal only" }]} />
      <Plot colors={colors} height={90 + (narrow ? 34 : 22) * samples.length} data={data}
            label={`Bar chart of the ${samples.length} most frequent portfolios among ${shots} shots`}
            layout={{
              showlegend: true,
              barmode: "stack",
              bargap: 0.3,
              xaxis: { ticksuffix: "%", title: { text: `share of the ${shots.toLocaleString("en-US")} shots` } },
              yaxis: { type: "category", categoryorder: "array", categoryarray: order, showgrid: false },
            }} />
    </div>
  );
}
