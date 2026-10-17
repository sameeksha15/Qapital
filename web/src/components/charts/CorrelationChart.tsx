import type { Correlations } from "../../api/types";
import { shortName } from "../../lib/format";
import { FONTS, useColors } from "../../lib/theme";
import { Plot } from "./Plot";

/**
 * How each pair of stocks moved together, from −1 (opposite) through 0 (unrelated) to 1 (in step), with stocks
 * grouped by sector so the sector blocks show along the diagonal.
 */
export function CorrelationChart({ correlations, height = 640 }: { correlations: Correlations; height?: number }) {
  const colors = useColors();
  const names = correlations.tickers.map(shortName);
  const hover = correlations.tickers.map((_, i) => correlations.tickers.map((__, j) =>
    `${names[i]} (${correlations.sectors[i]})<br>${names[j]} (${correlations.sectors[j]})`));
  return (
    <Plot colors={colors} height={height}
          label={`Heatmap of how ${names.length} stocks moved together, grouped by sector`}
          data={[{
            type: "heatmap", x: names, y: names, z: correlations.matrix, customdata: hover,
            zmin: -1, zmax: 1, xgap: 0.5, ygap: 0.5,
            colorscale: [[0, colors.series1], [0.5, colors.paper], [1, colors.series2]],
            colorbar: { thickness: 10, outlinewidth: 0, tickvals: [-1, 0, 1], ticktext: ["opposite", "unrelated", "in step"] },
            hovertemplate: "%{customdata}<br>correlation %{z:.2f}<extra></extra>",
          }]}
          layout={{
            margin: { l: 8, r: 8, t: 8, b: 8 },
            xaxis: { showgrid: false, tickangle: -60, tickfont: { size: 9, family: FONTS.mono } },
            yaxis: { showgrid: false, autorange: "reversed", tickfont: { size: 9, family: FONTS.mono } },
          }} />
  );
}
