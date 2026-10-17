// Shared geometry and made-up strengths for the "How it works" drawings. These are illustrations, not results.

/** `n` points evenly spaced on a circle, the first at the top. */
export function circlePoints(n: number, radius: number, centre: number): [number, number][] {
  return Array.from({ length: n }, (_, i) => {
    const angle = (2 * Math.PI * i) / n - Math.PI / 2;
    return [centre + radius * Math.cos(angle), centre + radius * Math.sin(angle)] as [number, number];
  });
}

/** Every pair (i, j) with i < j. */
export function allPairs(n: number): [number, number][] {
  const pairs: [number, number][] = [];
  for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) pairs.push([i, j]);
  return pairs;
}

/** A fixed, made-up strength between 0.1 and 1 for how much stocks i and j move together. */
export function strength(i: number, j: number): number {
  const [a, b] = i < j ? [i, j] : [j, i];
  const x = Math.sin(a * 12.9898 + b * 78.233) * 43758.5453;
  return 0.1 + 0.9 * (x - Math.floor(x));
}

/** A fixed, made-up size for each stock's own term. */
export const OWN = [0.55, 0.85, 0.35, 0.7, 0.6, 0.4, 0.8, 0.5];

/** Number of ways to choose k things from n. */
export function choose(n: number, k: number): number {
  let result = 1;
  for (let i = 1; i <= k; i++) result = (result * (n - k + i)) / i;
  return Math.round(result);
}

/** Number of 1s in the binary form of `x`. */
export const ones = (x: number) => x.toString(2).split("").filter((bit) => bit === "1").length;
