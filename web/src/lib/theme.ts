import { useEffect, useState } from "react";

/** The page's fonts (index.css), for charts that set their own text. */
export const FONTS = {
  sans: '"Libre Franklin", system-ui, -apple-system, "Segoe UI", sans-serif',
  mono: '"JetBrains Mono", ui-monospace, "Cascadia Mono", monospace',
};

/** True while a CSS media query matches; re-renders the caller when that changes. */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => matchMedia(query).matches);
  useEffect(() => {
    const list = matchMedia(query);
    const update = () => setMatches(list.matches);
    list.addEventListener("change", update);
    return () => list.removeEventListener("change", update);
  }, [query]);
  return matches;
}

/** Phone-sized screens, where long chart labels go on two lines. */
export const useIsNarrow = () => useMediaQuery("(max-width: 640px)");

const NAMES = ["paper", "paper-2", "ink", "ink-2", "muted", "rule", "rule-strong", "accent", "signal", "neutral",
  "series-1", "series-2", "series-3", "good", "bad"] as const;

type CamelCase<S extends string> = S extends `${infer A}-${infer B}` ? `${A}${Capitalize<CamelCase<B>>}` : S;
export type Colors = { dark: boolean } & Record<CamelCase<(typeof NAMES)[number]>, string>;

/**
 * Chart colours read from the CSS variables in index.css, so charts and page always match, in light and dark mode.
 * Keys are camel-cased: "ink-2" → ink2, "series-1" → series1.
 */
export function useColors(): Colors {
  const dark = useMediaQuery("(prefers-color-scheme: dark)");
  const css = getComputedStyle(document.documentElement);
  const colors: Record<string, string | boolean> = { dark };
  for (const name of NAMES) colors[name.replace(/-(\w)/g, (_, c: string) => c.toUpperCase())] = css.getPropertyValue(`--${name}`).trim();
  return colors as Colors;
}
