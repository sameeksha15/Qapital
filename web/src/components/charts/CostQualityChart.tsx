import { useState } from "react";
import type { GridRun } from "../../api/research";
import { describeCircuit, percent } from "../../lib/format";
import { useColors } from "../../lib/theme";
import { DEFAULT_SETTINGS } from "../../state/draft";
import { Segmented } from "../ui";
import { Plot, type Trace } from "./Plot";

/**
 * Every precomputed circuit: two-qubit gates on the fake IBM chip against how much it beats random guessing.
 * Filters dim the circuits that don't match, so a family can be followed across the chart.
 */
export function CostQualityChart({ runs }: { runs: GridRun[] }) {
  const colors = useColors();
  const [depth, setDepth] = useState<number | "all">("all");
  const [kept, setKept] = useState<number | "all">("all");
  const matches = (run: GridRun) => (depth === "all" || run.depth === depth) && (kept === "all" || run.pairs_kept === kept);
  const groups = [
    { mixer: "standard", name: "Penalty circuit", color: colors.series1 },
    { mixer: "xy", name: "XY circuit (keeps K)", color: colors.series2 },
    { mixer: "warm", name: "Warm-started circuit", color: colors.series3 },
  ].filter((group) => runs.some((run) => run.mixer === group.mixer));
  const data: Trace[] = groups.map(({ mixer, name, color }) => {
    const shown = runs.filter((run) => run.mixer === mixer);
    return {
      type: "scatter", mode: "markers", name,
      marker: { color, size: shown.map((run) => (matches(run) ? 11 : 7)), opacity: shown.map((run) => (matches(run) ? 1 : 0.15)),
                line: { color: colors.paper, width: 1.5 } },
      x: shown.map((run) => run.gates), y: shown.map((run) => run.lift),
      text: shown.map((run) => describeCircuit({ ...DEFAULT_SETTINGS, mixer: run.mixer, depth: run.depth, pairs_kept: run.pairs_kept, optimiser: run.optimiser })),
      hovertemplate: "%{text}<br>%{x} two-qubit gates<br>%{y:.1f}× better than random<extra></extra>",
    };
  });
  const depths = [...new Set(runs.map((run) => run.depth))].sort((a, b) => a - b);
  const keeps = [...new Set(runs.map((run) => run.pairs_kept))].sort((a, b) => b - a);
  return (
    <div>
      <div className="flex flex-wrap gap-x-8 gap-y-3">
        <Segmented<number | "all"> size="sm" label="Layers" value={depth} onChange={setDepth}
                   options={[{ value: "all", label: "All" }, ...depths.map((d) => ({ value: d, label: String(d) }))]} />
        <Segmented<number | "all"> size="sm" label="Links kept" value={kept} onChange={setKept}
                   options={[{ value: "all", label: "All" }, ...keeps.map((k) => ({ value: k, label: percent(k, 0) }))]} />
      </div>
      <Plot colors={colors} height={400} data={data}
            label="Scatter chart of two-qubit gates against how much each circuit beats random guessing"
            layout={{
              showlegend: true,
              hovermode: "closest",
              xaxis: { title: { text: "two-qubit gates on the fake IBM chip (fewer is cheaper)" } },
              yaxis: { title: { text: "times better than random guessing" }, rangemode: "tozero" },
            }} />
    </div>
  );
}
