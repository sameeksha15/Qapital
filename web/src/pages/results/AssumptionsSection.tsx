import type { FullResult } from "../../api/types";
import { Fact, Note, Section } from "../../components/ui";
import { day, ESTIMATOR_NAMES, money, percent, shortName } from "../../lib/format";

/** Where every number came from: the price window, the estimator, the cost card and its sources. */
export function AssumptionsSection({ result }: { result: FullResult }) {
  const { estimation, costs, dataset, request } = result;
  return (
    <Section id="assumptions" number="05" title="Data and assumptions" stacked
             note="Every estimate is a guess from the past. Here is exactly what this run used, so it can be checked or repeated.">
      {estimation ? (
        <dl className="grid gap-x-10 gap-y-6 sm:grid-cols-2 xl:grid-cols-3">
          <Fact term="Prices used" value={`${day(estimation.window[0])} – ${day(estimation.window[1])}`}
                detail={`${estimation.days} trading days, snapshot ${estimation.snapshot}`} />
          <Fact term="Estimates" value={ESTIMATOR_NAMES[estimation.method]}
                detail={estimation.method === "historical" ? "no shrinkage" : `returns pulled ${percent(estimation.shrinkage, 0)} of the way to the middle`} />
          {dataset?.safe_rate != null && <Fact term="Risk-free rate" value={percent(dataset.safe_rate, 2)} detail="per year, for Sharpe ratios" />}
          {costs && (
            <Fact term="Trading costs" value={costs.model}
                  detail={`rate card of ${day(costs.as_of)}; spread over ${costs.horizon_years} year${costs.horizon_years === 1 ? "" : "s"} of holding`} />
          )}
          {costs && <Fact term="Money per stock" value={money(costs.position_value, costs.currency)} detail="what the costs were worked out for" />}
          {request && <Fact term="Seed" value={String(request.settings.seed)} detail="same settings and seed give the same result" />}
        </dl>
      ) : <Note>This result doesn't record its data window.</Note>}

      {estimation && Object.keys(estimation.excluded).length > 0 && (
        <div className="mt-8">
          <Note tone="warn" title="Left out for lack of data">
            <ul className="mt-1 space-y-0.5">
              {Object.entries(estimation.excluded).map(([ticker, why]) => <li key={ticker}><span className="font-mono">{shortName(ticker)}</span>: {why}</li>)}
            </ul>
          </Note>
        </div>
      )}
      {costs && costs.held.length > 0 && (
        <p className="mt-6 text-sm text-ink-2">
          Already held: {costs.held.map(shortName).join(", ")}. Keeping a holding avoids its selling costs, so the score
          favours it slightly.
        </p>
      )}
      {costs && (
        <p className="mt-6 text-xs leading-relaxed text-muted">
          Sources: {costs.sources.map((source, i) => {
            const url = source.match(/https?:\/\/\S+/)?.[0];
            return <span key={source}>{i > 0 && "; "}{url ? <a href={url} target="_blank" rel="noreferrer" className="underline underline-offset-2 hover:text-ink">{source.replace(url, "").trim() || url}</a> : source}</span>;
          })}.
        </p>
      )}
    </Section>
  );
}
