import Plotly, { type PlotPoint } from "plotly.js-dist-min";
import { useEffect, useRef } from "react";
import { FONTS, type Colors } from "../../lib/theme";

const FONT = FONTS.sans;

/** A Plotly trace or layout: plain objects in Plotly's own format. */
export type Trace = Record<string, any>;
export type Layout = Record<string, any>;
export type { PlotPoint };

interface PlotProps {
  data: Trace[];
  layout?: Layout;
  colors: Colors;
  height: number;
  label: string;
  onPointClick?: (point: PlotPoint) => void;
  onPointHover?: (point: PlotPoint | null) => void;
}

/**
 * A Plotly chart in the page's colours (from useColors). Redraws whenever data, layout or colours change,
 * animating between states (`layout.transition`, 600 ms by default). `onPointClick` and `onPointHover`
 * receive Plotly's point; hovering off calls `onPointHover(null)`. `label` describes the chart for screen readers.
 */
export function Plot({ data, layout = {}, colors, height, label, onPointClick, onPointHover }: PlotProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const axis = { gridcolor: colors.rule, linecolor: colors.ruleStrong, zerolinecolor: colors.ruleStrong,
                   tickcolor: colors.ruleStrong, automargin: true, title: { font: { size: 12, color: colors.ink2 } } };
    Plotly.react(node, data, {
      height,
      autosize: true,
      margin: { l: 8, r: 16, t: 8, b: 8 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      font: { family: FONT, size: 12, color: colors.ink2 },
      hoverlabel: { bgcolor: colors.paper, bordercolor: colors.ruleStrong, font: { family: FONT, color: colors.ink } },
      legend: { orientation: "h", x: 0, y: 1.02, yanchor: "bottom", traceorder: "normal" },
      showlegend: false,
      transition: { duration: 600, easing: "cubic-in-out" },
      ...layout,
      xaxis: { ...axis, ...layout.xaxis },
      yaxis: { ...axis, ...layout.yaxis },
    }, { displayModeBar: false, responsive: true }).then((plot) => {
      plot.removeAllListeners?.("plotly_click");
      plot.removeAllListeners?.("plotly_hover");
      plot.removeAllListeners?.("plotly_unhover");
      if (onPointClick) plot.on("plotly_click", (event) => onPointClick(event.points[0]));
      if (onPointHover) {
        plot.on("plotly_hover", (event) => onPointHover(event.points[0]));
        plot.on("plotly_unhover", () => onPointHover(null));
      }
    });
  }, [data, layout, colors, height, onPointClick, onPointHover]);

  useEffect(() => {
    const node = ref.current;
    return () => {
      if (node) Plotly.purge(node);
    };
  }, []);

  return <div ref={ref} role="img" aria-label={label} className="w-full min-w-0" style={{ height }} />;
}
