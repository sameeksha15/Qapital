import type { Spread } from "../../api/research";
import { Plot, type Trace } from "../../components/charts/Plot";
import { useColors } from "../../lib/theme";

export interface SpreadSeries {
  name: string;
  color: string;
  values: (Spread | undefined)[];
  dash?: boolean;
}

interface SpreadBarsProps {
  categories: string[];
  series: SpreadSeries[];
  title: string;
  label: string;
  format?: (value: number) => string;
  suffix?: string;
  scale?: number;
  height?: number;
  /** A dotted reference line, e.g. 1× (no better than luck). */
  reference?: { value: number; label: string };
}

/**
 * Grouped bars of means over many problems, with whiskers from the lowest to the highest value, so a reader sees the
 * spread and not only the average.
 */
export function SpreadBars({ categories, series, title, label, format = (v) => v.toFixed(2), suffix = "", scale = 1, height = 340, reference }: SpreadBarsProps) {
  const colors = useColors();
  const data: Trace[] = series.map((s) => ({
    type: "bar", name: s.name, x: categories, marker: { color: s.color, pattern: s.dash ? { shape: "/", fgcolor: colors.paper, size: 6 } : undefined },
    y: s.values.map((v) => (v ? scale * v.mean : null)),
    error_y: {
      type: "data", symmetric: false, color: colors.ink2, thickness: 1.1, width: 4,
      array: s.values.map((v) => (v ? scale * (v.max - v.mean) : 0)),
      arrayminus: s.values.map((v) => (v ? scale * (v.mean - v.min) : 0)),
    },
    customdata: s.values.map((v) => (v ? [format(v.mean), format(v.min), format(v.max), v.n] : null)),
    hovertemplate: `${s.name}<br>%{x}: %{customdata[0]}${suffix} on average<br>from %{customdata[1]}${suffix} to %{customdata[2]}${suffix} over %{customdata[3]} runs<extra></extra>`,
  }));
  const top = Math.max(...series.flatMap((s) => s.values.map((v) => (v ? scale * v.max : 0))), reference ? reference.value * 1.1 : 0);
  return (
    <Plot colors={colors} height={height} data={data} label={label}
          layout={{
            showlegend: true, barmode: "group", bargap: 0.28, bargroupgap: 0.08,
            margin: { l: 64, r: 16, t: 8, b: 8 },
            yaxis: { title: { text: title }, range: [0, top * 1.08], automargin: false, ticksuffix: suffix },
            xaxis: { type: "category" },
            shapes: reference ? [{ type: "line", xref: "paper", x0: 0, x1: 1, y0: reference.value, y1: reference.value, line: { color: colors.muted, width: 1, dash: "dot" } }] : [],
            annotations: reference ? [{ xref: "paper", x: 1, y: reference.value, xanchor: "right", yanchor: "bottom", showarrow: false, text: reference.label, font: { size: 11, color: colors.ink2 } }] : [],
          }} />
  );
}

/** "12 of 31": a paired count, written out. */
export function Tally({ wins, total, of }: { wins: number; total: number; of: string }) {
  return (
    <span className="tabular-nums">
      <span className="font-serif text-2xl text-ink">{wins}</span>
      <span className="text-ink-2"> of {total} {of}</span>
    </span>
  );
}
