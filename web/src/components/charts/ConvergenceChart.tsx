import { useColors } from "../../lib/theme";
import { Plot } from "./Plot";

/** Average score after every tuning step (all layers in a row), with the best possible score as a line. */
export function ConvergenceChart({ values, best, bestLabel }: { values: number[]; best: number; bestLabel: string }) {
  const colors = useColors();
  return (
    <Plot colors={colors} height={300} label="Line chart of the average score after every tuning step"
          data={[{
            type: "scatter", mode: "lines", line: { color: colors.series1, width: 2 },
            x: values.map((_, step) => step + 1), y: values,
            hovertemplate: "step %{x}<br>average score %{y:.4f}<extra></extra>",
          }]}
          layout={{
            xaxis: { title: { text: "tuning step (one circuit run each)" } },
            yaxis: { title: { text: "average score, fines included" } },
            shapes: [{ type: "line", xref: "paper", x0: 0, x1: 1, y0: best, y1: best, line: { color: colors.muted, width: 1 } }],
            annotations: [{ xref: "paper", x: 1, y: best, xanchor: "right", yanchor: "bottom", showarrow: false,
                            text: bestLabel, font: { size: 11, color: colors.ink2 } }],
          }} />
  );
}
