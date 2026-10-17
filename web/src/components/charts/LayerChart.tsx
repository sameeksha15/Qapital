import { useInView, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { portfolioLabel } from "../../lib/format";
import type { QuantumResult } from "../../api/types";
import { useColors, useIsNarrow } from "../../lib/theme";
import { PauseIcon, PlayIcon } from "../icons";
import { Plot } from "./Plot";

/**
 * "Watch the circuit think": chance of each of the best portfolios after 0, 1, …, p layers.
 * Plays once by itself when it scrolls into view; the bars glide from one layer to the next.
 */
export function LayerChart({ quantum }: { quantum: QuantumResult }) {
  const colors = useColors();
  const narrow = useIsNarrow();
  const reduce = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.5 });
  const lastLayer = quantum.layer_probs.length - 1;
  const [layer, setLayer] = useState(reduce ? lastLayer : 0);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (inView && !reduce) setPlaying(true);
  }, [inView, reduce]);

  useEffect(() => {
    if (!playing) return undefined;
    const timer = setTimeout(() => {
      if (layer < lastLayer) setLayer(layer + 1);
      else setPlaying(false);
    }, 1100);
    return () => clearTimeout(timer);
  }, [playing, layer, lastLayer]);

  const labels = quantum.layer_labels.map((label) => portfolioLabel(label.split(", "), narrow));
  const highest = Math.max(...quantum.layer_probs.flat());
  return (
    <div ref={ref}>
      <Plot colors={colors} height={70 + (narrow ? 34 : 26) * labels.length}
            label={`Bar chart of the chance of the ${labels.length} best portfolios after ${layer} layers`}
            data={[{
              type: "bar", orientation: "h", y: labels, x: quantum.layer_probs[layer].map((p) => 100 * p),
              marker: { color: labels.map((_, i) => (i === 0 ? colors.series2 : colors.series1)) },
              hovertemplate: "%{y}<br>%{x:.2f}% chance per shot<extra></extra>",
            }]}
            layout={{
              bargap: 0.3,
              transition: { duration: 800, easing: "cubic-in-out" },
              xaxis: { ticksuffix: "%", range: [0, 105 * highest], title: { text: "chance in one shot" } },
              yaxis: { autorange: "reversed", showgrid: false },
            }} />
      <div className="mt-4 flex flex-wrap items-center gap-4">
        <button type="button" onClick={() => { if (layer === lastLayer) setLayer(0); setPlaying(!playing); }}
                className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-rule-strong text-ink transition hover:border-ink"
                aria-label={playing ? "Pause" : "Play"}>
          {playing ? <PauseIcon /> : <PlayIcon />}
        </button>
        <div className="flex items-center gap-1.5" role="group" aria-label="Layers applied">
          {quantum.layer_probs.map((_, i) => (
            <button key={i} type="button" onClick={() => { setPlaying(false); setLayer(i); }} aria-pressed={i === layer}
                    className={`h-1.5 rounded-full transition-all duration-500 ${i === layer ? "w-8 bg-signal" : i < layer ? "w-4 bg-ink-2" : "w-4 bg-rule-strong"}`}>
              <span className="sr-only">after {i} layers</span>
            </button>
          ))}
        </div>
        <span className="text-sm text-ink-2">after <span className="tabular-nums text-ink">{layer}</span> of {lastLayer} layer{lastLayer > 1 ? "s" : ""}</span>
      </div>
    </div>
  );
}
