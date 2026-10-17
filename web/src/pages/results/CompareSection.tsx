import { useState } from "react";
import type { FullResult } from "../../api/types";
import { FrontierChart } from "../../components/charts/FrontierChart";
import { CheckIcon, CrossIcon } from "../../components/icons";
import { DrawIn } from "../../components/motion";
import { Fact, Section, Td, Th } from "../../components/ui";
import { decimal, percent, portfolioName, seconds, whole } from "../../lib/format";

export function CompareSection({ result }: { result: FullResult }) {
  const { report_card: rows, frontier, optimal } = result;
  const [highlight, setHighlight] = useState<string | null>(null);
  const exact = optimal?.best_is_exact ?? true;

  return (
    <Section id="compare" number="03" title="Every method on the same problem" stacked
             note="All portfolios are scored with the same function on the full list. The lines are the best return possible at each level of risk; the dots are each method's pick. Point at a row of the table to find that method on the chart.">
      <DrawIn><FrontierChart frontier={frontier} highlight={highlight} /></DrawIn>

      <div className="relative mt-8 overflow-x-auto">
        <table className="w-full min-w-190 border-t border-ink text-sm">
          <thead className="border-b border-rule">
            <tr>
              <Th>Method</Th><Th>Searched</Th><Th>{exact ? "True best?" : "Best known?"}</Th><Th>Portfolio</Th>
              <Th numeric>Score</Th><Th numeric>Return</Th><Th numeric>Volatility</Th><Th numeric>Time</Th><Th numeric>Hit rate</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.solver} tabIndex={0}
                  onMouseEnter={() => setHighlight(row.solver)} onMouseLeave={() => setHighlight(null)}
                  onFocus={() => setHighlight(row.solver)} onBlur={() => setHighlight(null)}
                  className={`cursor-default border-b border-rule outline-none transition-colors hover:bg-paper-2 focus-visible:bg-paper-2 ${
                    row.solver === "QAOA" ? "font-medium" : ""}`}>
                <Td className="text-ink">
                  {row.solver === "QAOA" && <span aria-hidden="true" className="mr-2 inline-block h-2 w-2 rounded-full bg-series-2" />}
                  {row.solver === "QAOA" ? "QAOA (quantum)" : row.solver}
                </Td>
                <Td className="text-ink-2">{row.universe === "shortlist" ? "Shortlist" : row.universe === "full" ? "Full list" : "–"}</Td>
                <Td>
                  <span className={`inline-flex items-center gap-1 ${row.found_best ? "text-good" : "text-bad"}`}>
                    {row.found_best ? <CheckIcon /> : <CrossIcon />}{row.found_best ? "yes" : "no"}
                  </span>
                </Td>
                <Td className="font-mono text-xs text-ink-2">{row.chosen ? portfolioName(row.chosen) : "–"}</Td>
                <Td numeric className="text-ink">{decimal(row.score, 4)}</Td>
                <Td numeric className="text-ink">{row.expected_return != null ? percent(row.expected_return) : "–"}</Td>
                <Td numeric className="text-ink">{row.risk != null ? percent(row.risk) : "–"}</Td>
                <Td numeric className="text-ink">{seconds(row.runtime_s)}</Td>
                <Td numeric className="text-ink">{row.hit_rate != null ? percent(row.hit_rate, 0) : "–"}</Td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-3 text-xs text-muted">
          Score: risk minus return plus trading costs (lower is better). Hit rate: share of 10 seeded runs that found the
          {exact ? " true" : " best known"} best (random methods only).
        </p>
      </div>

      {optimal && (
        <dl className="mt-12 grid gap-x-10 gap-y-6 sm:grid-cols-2 xl:grid-cols-4">
          <Fact term={exact ? "The true best (proven)" : "Best known (not proven)"} value={portfolioName(optimal.best.stocks)}
                detail={`score ${decimal(optimal.best.score, 4)} · ${optimal.best_found_by}`} />
          {optimal.num_valid != null && (
            <Fact term="Legal portfolios in the whole list" value={whole(optimal.num_valid)}
                  detail={exact ? "all checked by brute force" : "too many to check one by one"} />
          )}
          {optimal.shortlisting_gap != null && (
            <Fact term="Did the shortlist keep it?" value={optimal.shortlisting_gap <= 1e-9 ? "Yes" : `No: ${decimal(optimal.shortlisting_gap, 4)} worse`}
                  detail="the circuit only sees the shortlist" />
          )}
          {optimal.relaxation_lower_bound != null && (
            <Fact term="No portfolio can score below" value={decimal(optimal.relaxation_lower_bound, 4)}
                  detail={exact ? "from the relaxed problem" : `the best known is within ${decimal(optimal.best.score - optimal.relaxation_lower_bound, 4)} of this`} />
          )}
        </dl>
      )}
    </Section>
  );
}
