import { percent, shortName } from "../../lib/format";
import type { StockInfo } from "../../api/types";
import { FONTS, useColors, type Colors } from "../../lib/theme";
import { Plot } from "./Plot";

export interface MapGroup {
  name: string;
  color: (colors: Colors) => string;
  size: number;
  labelled?: boolean;
}

interface MarketMapProps {
  stocks: StockInfo[];
  groups: Record<string, MapGroup>;
  groupOf: (ticker: string) => string;
  onToggle?: (ticker: string) => void;
  height?: number;
}

/**
 * Every stock as a dot: further right is bumpier, higher is more expected return.
 * `groupOf(ticker)` returns one of the keys of `groups` ({name, color, size, labelled}), so the same chart can show
 * "selected / not selected" on the settings page and "chosen / shortlisted / the rest" on the results page.
 * Clicking a dot calls `onToggle(ticker)` when it is given.
 */
export function MarketMap({ stocks, groups, groupOf, onToggle, height = 380 }: MarketMapProps) {
  const colors = useColors();
  const usable = stocks.filter((stock) => stock.expected_return != null && stock.volatility != null);
  const labelSide = labelSides(usable.filter((stock) => groups[groupOf(stock.ticker)]?.labelled));
  const data = Object.entries(groups).map(([key, group]) => {
    const shown = usable.filter((stock) => groupOf(stock.ticker) === key);
    return {
      type: "scatter", mode: group.labelled ? "markers+text" : "markers", name: group.name,
      x: shown.map((s) => 100 * s.volatility!), y: shown.map((s) => 100 * s.expected_return!),
      text: group.labelled ? shown.map((s) => shortName(s.ticker)) : undefined,
      textposition: shown.map((s) => labelSide.get(s.ticker) ?? "top center"), textfont: { size: 11, color: colors.ink, family: FONTS.mono },
      customdata: shown.map((s) => [s.ticker, s.name ?? shortName(s.ticker), s.sector, percent(s.expected_return!), percent(s.volatility!)]),
      marker: { color: group.color(colors), size: group.size, line: { color: colors.paper, width: 1.5 } },
      hovertemplate: "<b>%{customdata[1]}</b> · %{customdata[2]}<br>return %{customdata[3]} · volatility %{customdata[4]}<extra></extra>",
    };
  });
  return (
    <Plot colors={colors} height={height} data={data} onPointClick={onToggle ? (point) => onToggle((point.customdata as string[])[0]) : undefined}
          label="Market map: each stock's expected yearly return against its volatility"
          layout={{
            showlegend: true,
            hovermode: "closest",
            xaxis: { title: { text: "volatility (yearly ups and downs)" }, ticksuffix: "%" },
            yaxis: { title: { text: "expected return per year" }, ticksuffix: "%" },
          }} />
  );
}

/**
 * Labels go above each dot; when labelled dots sit close together, the next one's label goes to its right (then
 * below), so the names don't print over each other. Positions are in percentage points of return and volatility.
 */
function labelSides(stocks: StockInfo[]): Map<string, string> {
  const sides = new Map<string, string>();
  const placed: { x: number; y: number; side: string }[] = [];
  for (const stock of [...stocks].sort((a, b) => a.volatility! - b.volatility!)) {
    const x = 100 * stock.volatility!;
    const y = 100 * stock.expected_return!;
    const crowded = placed.filter((p) => Math.abs(p.x - x) < 3.5 && Math.abs(p.y - y) < 4);
    const side = crowded.length === 0 ? "top center" : crowded.some((p) => p.side === "middle right") ? "bottom center" : "middle right";
    placed.push({ x, y, side });
    sides.set(stock.ticker, side);
  }
  return sides;
}
