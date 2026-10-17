import type { Frontier } from "../../api/types";
import { useColors } from "../../lib/theme";
import { Plot } from "./Plot";

/** "QAOA", or "QAOA + 3 classical" when classical methods picked the same portfolio. */
const quantumLabel = (solvers: string[]) => (solvers.length > 1 ? `QAOA + ${solvers.length - 1} classical  ` : "QAOA  ");

/**
 * The efficient frontier: best return for each level of risk, with every method's pick as a dot.
 * Methods that picked the same portfolio share one dot. `highlight` (a method name) rings that method's dot,
 * so hovering a row of the report card points at the chart.
 */
interface Dot {
  risk: number;
  ret: number;
  solvers: string[];
}

export function FrontierChart({ frontier, highlight = null, height = 400 }: { frontier: Frontier; highlight?: string | null; height?: number }) {
  const colors = useColors();
  const places = new Map<string, Dot>();
  for (const pick of frontier.picks) {
    const key = `${pick.risk.toFixed(6)}|${pick.ret.toFixed(6)}`;
    places.set(key, { risk: pick.risk, ret: pick.ret, solvers: [...(places.get(key)?.solvers ?? []), pick.solver] });
  }
  const dots = [...places.values()];
  const isQuantum = (dot: Dot) => dot.solvers.includes("QAOA");
  const isLit = (dot: Dot) => highlight != null && dot.solvers.includes(highlight);
  const line = (points: [number, number][], name: string, color: string) => ({
    type: "scatter", mode: "lines", name, line: { color, width: 2 },
    x: points.map(([risk]) => 100 * risk), y: points.map(([, ret]) => 100 * ret),
    hovertemplate: `${name}<br>volatility %{x:.1f}%<br>return %{y:.1f}%<extra></extra>`,
  });
  const data = [
    line(frontier.continuous, "Best with fractional weights", colors.series1),
    ...(frontier.discrete.length ? [line(frontier.discrete, "Best with whole stocks, equal money", colors.series3)] : []),
    {
      type: "scatter", mode: "markers+text", name: "Method picks",
      x: dots.map((dot) => 100 * dot.risk), y: dots.map((dot) => 100 * dot.ret),
      text: dots.map((dot) => (isQuantum(dot) ? quantumLabel(dot.solvers) : isLit(dot) ? `${highlight}  ` : "")),
      textposition: "middle left", textfont: { size: 11, color: colors.ink },
      customdata: dots.map((dot) => dot.solvers.join(", ")),
      marker: {
        size: dots.map((dot) => (isLit(dot) ? 18 : isQuantum(dot) ? 13 : 9)),
        color: dots.map((dot) => (isQuantum(dot) ? colors.series2 : colors.ink2)),
        line: { color: dots.map((dot) => (isLit(dot) ? colors.ink : colors.paper)), width: dots.map((dot) => (isLit(dot) ? 3 : 2)) },
      },
      hovertemplate: "%{customdata}<br>volatility %{x:.1f}%<br>return %{y:.1f}%<extra></extra>",
    },
  ];
  return (
    <Plot colors={colors} height={height} data={data}
          label="Efficient frontier: best yearly return for each level of volatility, with each method's pick"
          layout={{
            showlegend: true,
            transition: { duration: 350, easing: "cubic-in-out" },
            xaxis: { title: { text: "volatility (yearly ups and downs)" }, ticksuffix: "%" },
            yaxis: { title: { text: "expected return per year" }, ticksuffix: "%" },
          }} />
  );
}
