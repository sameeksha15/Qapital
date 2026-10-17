import { animate, motion, useInView, useReducedMotion, type HTMLMotionProps } from "motion/react";
import { useEffect, useRef, useState, type ReactNode } from "react";

/** One easing for the whole site: quick start, long gentle finish. */
export const EASE = [0.22, 1, 0.36, 1] as const;

type RevealProps = HTMLMotionProps<"div"> & { as?: "div" | "section" | "li"; delay?: number; children?: ReactNode };

/** Fades and lifts its content into place the first time it scrolls into view (shown at once for reduced motion). */
export function Reveal({ as = "div", delay = 0, children, ...props }: RevealProps) {
  const reduce = useReducedMotion();
  const Component = motion[as] as typeof motion.div;
  if (reduce) return <Component {...props}>{children}</Component>;
  return (
    <Component initial={{ opacity: 0, y: 18 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: 0.12 }}
               transition={{ duration: 0.7, ease: EASE, delay }} {...props}>
      {children}
    </Component>
  );
}

/**
 * Wipes a chart in from the left, like a line being drawn, the first time it scrolls into view.
 * The outer box is watched and the inner one clipped: browsers count a fully clipped element as never visible.
 */
export function DrawIn({ children, className = "" }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.2 });
  const reduce = useReducedMotion();
  if (reduce) return <div className={className}>{children}</div>;
  return (
    <div ref={ref} className={className}>
      <motion.div initial={{ clipPath: "inset(0% 100% 0% 0%)" }} animate={{ clipPath: inView ? "inset(0% 0% 0% 0%)" : "inset(0% 100% 0% 0%)" }}
                  transition={{ duration: 1.3, ease: EASE }}>
        {children}
      </motion.div>
    </div>
  );
}

/** Counts from 0 to `value` when it scrolls into view; `format` turns the number into text. */
export function CountUp({ value, format, duration = 1.4 }: { value: number; format: (v: number) => string; duration?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const reduce = useReducedMotion();
  const [shown, setShown] = useState(0);

  useEffect(() => {
    if (!inView || reduce) return undefined;
    const controls = animate(0, value, { duration, ease: EASE, onUpdate: setShown });
    return () => controls.stop();
  }, [inView, value, reduce, duration]);

  return <span ref={ref} className="tabular-nums">{format(reduce ? value : inView ? shown : 0)}</span>;
}
