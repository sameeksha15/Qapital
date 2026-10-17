import { useReducedMotion } from "motion/react";
import { useEffect, useRef } from "react";

const DEFAULT_PEAKS = [0.3, 0.5, 0.25, 0.45, 0.35, 0.6, 1, 0.4];   // tallest on the right, clear of the headline
const LINES = 24;

/**
 * Stacked lines that rise into slow-moving peaks, like probability gathering on a few outcomes.
 * `peaks` (0–1) sets the height of each peak, e.g. a run's final chances for its best portfolios;
 * peak number `highlight` (the tallest by default) is traced in orange. `speed` makes it move faster.
 * Pauses off-screen and draws a single still frame for people who prefer reduced motion.
 */
interface WaveFieldProps {
  peaks?: number[];
  highlight?: number;
  speed?: number;
  className?: string;
}

export function WaveField({ peaks = DEFAULT_PEAKS, highlight, speed = 1, className = "" }: WaveFieldProps) {
  const ref = useRef<HTMLCanvasElement>(null);
  const reduce = useReducedMotion();
  const lit = highlight ?? peaks.indexOf(Math.max(...peaks));
  const signature = `${peaks.join(",")}|${lit}`;   // restart only when the values change, not on every render

  useEffect(() => {
    const element = ref.current;
    const drawing = element?.getContext("2d");
    if (!element || !drawing) return undefined;
    const canvas: HTMLCanvasElement = element;
    const context: CanvasRenderingContext2D = drawing;
    const ratio = window.devicePixelRatio || 1;
    const [values, litIndex] = signature.split("|");
    const peaks = values.split(",").map(Number);
    const highest = Math.max(...peaks);
    const bumps = peaks.map((height, i) => ({
      x: (i + 0.5) / peaks.length, height: height / highest, width: 0.03 + 0.018 * (i % 3), top: i === Number(litIndex),
    }));
    let frame = 0;
    let time = 0;
    let visible = true;
    const observer = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; });
    observer.observe(canvas);

    function resize() {
      const { width, height } = canvas.getBoundingClientRect();
      canvas.width = Math.max(1, width * ratio);
      canvas.height = Math.max(1, height * ratio);
    }

    function lineY(x: number, line: number, depth: number) {
      let lift = 0.05 * Math.sin(x * 13 + time * 0.9 + line * 0.45);
      for (const bump of bumps) {
        const drift = 0.012 * Math.sin(time * 0.5 + bump.x * 11 + line * 0.3);
        const distance = (x - bump.x - drift) / bump.width;
        lift += bump.height * Math.exp(-distance * distance);
      }
      return canvas.height * (0.3 + 0.62 * depth) - lift * canvas.height * 0.24 * (0.3 + 0.7 * depth);
    }

    function draw() {
      const { width, height } = canvas;
      context.clearRect(0, 0, width, height);
      context.lineWidth = ratio;
      for (let line = 0; line < LINES; line++) {
        const depth = line / (LINES - 1);
        context.beginPath();
        for (let px = 0; px <= width; px += 3 * ratio) {
          const y = lineY(px / width, line, depth);
          if (px === 0) context.moveTo(px, y);
          else context.lineTo(px, y);
        }
        context.strokeStyle = `rgba(238, 241, 247, ${0.05 + 0.2 * depth})`;
        context.stroke();
      }
      const top = bumps.find((bump) => bump.top) ?? bumps[0];
      const start = Math.max(0, (top.x - 2.6 * top.width) * width);
      const end = Math.min(width, (top.x + 2.6 * top.width) * width);
      context.beginPath();
      for (let px = start; px <= end; px += 3 * ratio) {
        const y = lineY(px / width, LINES - 1, 1);
        if (px === start) context.moveTo(px, y);
        else context.lineTo(px, y);
      }
      context.strokeStyle = "rgba(240, 122, 69, 0.9)";
      context.lineWidth = 2 * ratio;
      context.stroke();
    }

    function tick() {
      if (visible) {
        time += 0.01 * speed;
        draw();
      }
      frame = requestAnimationFrame(tick);
    }

    resize();
    draw();
    if (!reduce) frame = requestAnimationFrame(tick);
    const resizer = new ResizeObserver(() => { resize(); draw(); });
    resizer.observe(canvas);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      resizer.disconnect();
    };
  }, [signature, speed, reduce]);

  return <canvas ref={ref} aria-hidden="true" className={`pointer-events-none block h-full w-full ${className}`} />;
}
