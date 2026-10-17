import { useEffect, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router";
import { useConnection } from "../../api/connection";
import { useMarkets, useResult } from "../../api/queries";
import type { FullResult } from "../../api/types";
import { ArrowLeftIcon, CheckIcon, InfoIcon, LinkIcon } from "../../components/icons";
import { CountUp } from "../../components/motion";
import { SectionIndex } from "../../components/SectionIndex";
import { Button, ButtonLink, Container, Hero, Kicker, Loading, Note, Stat, StatStrip } from "../../components/ui";
import { day, describeCircuit, percent, times } from "../../lib/format";
import { addToHistory, useHistory } from "../../lib/history";
import { useDraft } from "../../state/draft";
import { AssumptionsSection } from "./AssumptionsSection";
import { CircuitSection } from "./CircuitSection";
import { CompareSection } from "./CompareSection";
import { OrdersSection } from "./OrdersSection";
import { PortfolioSection } from "./PortfolioSection";

const SECTIONS = [
  { id: "portfolio", label: "The portfolio" },
  { id: "orders", label: "Orders and costs" },
  { id: "compare", label: "How it compares" },
  { id: "circuit", label: "Inside the circuit" },
  { id: "assumptions", label: "Data and assumptions" },
];

export function ResultPage() {
  const { resultId = "" } = useParams();
  const result = useResult(resultId);
  const { state } = useConnection();

  if (result.error) {
    return (
      <Container className="py-20">
        <Note tone={state === "live" ? "bad" : "warn"} title="Couldn't open this result">{result.error.message}</Note>
        <ButtonLink to="/" variant="primary" className="mt-8">Go to the optimiser</ButtonLink>
      </Container>
    );
  }
  if (!result.data) return <Container><Loading>Opening the result…</Loading></Container>;
  if (result.data.kind === "backtest") return <Navigate to={`/backtest/${resultId}`} replace />;
  if (!result.data.result) return <Container className="py-20"><Note tone="bad" title="This run has no result">{result.data.error}</Note></Container>;
  return <Report result={result.data.result} />;
}

function Report({ result }: { result: FullResult }) {
  const { quantum, optimal, estimation, request } = result;
  const navigate = useNavigate();
  const { setDraft } = useDraft();
  const history = useHistory();
  const markets = useMarkets();
  const [copied, setCopied] = useState(false);
  const marketName = markets.data?.markets.find((m) => m.id === (estimation?.market ?? request?.market))?.name ?? estimation?.market ?? "";
  const qaoa = result.report_card.find((row) => row.solver === "QAOA");
  const finalChances = quantum.layer_probs[quantum.layer_probs.length - 1];
  const exact = optimal?.best_is_exact ?? true;
  const currency = estimation?.currency ?? "INR";

  useEffect(() => {  // results opened from a shared link join this browser's history too
    if (!result.result_id || history.some((entry) => entry.id === result.result_id) || !request) return;
    addToHistory({
      id: result.result_id, kind: "optimise", title: `${marketName || request.market}: ${request.settings.k} stocks`,
      market: request.market, detail: describeCircuit(request.settings), createdAt: new Date().toISOString(),
    });
  }, [result, history, request, marketName]);

  const share = async () => {
    try {
      await navigator.clipboard.writeText(location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };
  const editSettings = () => {
    if (request) setDraft(request);
    navigate("/");
  };

  const headline = !qaoa?.found_best ? "The quantum circuit came close, but missed the best portfolio."
    : exact ? "The quantum circuit found the best portfolio." : "The quantum circuit found the best portfolio any method found.";
  const badge = !qaoa?.found_best ? (exact ? "Not the true best portfolio" : "Not the best known portfolio")
    : exact ? "Matches the true best, found by checking every portfolio" : "Matches the best known; there were too many portfolios to check them all";

  return (
    <>
      <Hero peaks={[...finalChances].reverse()} highlight={finalChances.length - 1}
            caption={`The wave: the circuit's final chances for the ${finalChances.length} best legal portfolios on its shortlist. Orange is the best one.`}>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <Kicker onDark>
            {request ? describeCircuit(request.settings) : "Saved result"}
            {estimation && ` · ${marketName} · prices to ${day(estimation.window[1])}`}
          </Kicker>
          <div className="flex flex-wrap gap-2">
            <Button variant="onDark" onClick={editSettings}><ArrowLeftIcon />Change settings</Button>
            <Button variant="onDark" onClick={share}><LinkIcon />{copied ? "Link copied" : "Copy link"}</Button>
          </div>
        </div>
        <p className={`mt-10 flex items-center gap-2 text-sm ${qaoa?.found_best ? "text-emerald-300" : "text-amber-300"}`}>
          {qaoa?.found_best ? <CheckIcon /> : <InfoIcon />}{badge}
        </p>
        <h1 className="mt-3 max-w-4xl font-serif text-4xl leading-[1.12] sm:text-[52px]">{headline}</h1>
        <p className="mt-5 max-w-3xl leading-relaxed text-navy-muted">{result.verdict}</p>
        <StatStrip onDark className="mt-12 max-w-4xl">
          <Stat onDark label="expected return per year" value={<CountUp value={quantum.expected_return} format={(v) => percent(v)} />}
                detail="of the circuit's pick, equal money" />
          <Stat onDark label="volatility per year" value={<CountUp value={quantum.risk} format={(v) => percent(v)} />} />
          <Stat onDark highlight label="better than random guessing" value={<CountUp value={quantum.lift_over_random} format={times} />}
                detail={quantum.warm_start_alone ? `warm start alone: ${times(quantum.warm_start_alone.lift_over_random)}` : undefined} />
          <Stat onDark label="of shots followed every rule" value={<CountUp value={quantum.feasible_rate} format={(v) => percent(v)} />} />
        </StatStrip>
      </Hero>

      <Container className="pb-20">
        <div className="grid gap-x-12 lg:grid-cols-[180px_minmax(0,1fr)]">
          <SectionIndex sections={SECTIONS} />
          <div className="min-w-0">
            <PortfolioSection result={result} />
            <OrdersSection result={result} currency={currency} />
            <CompareSection result={result} />
            <CircuitSection result={result} />
            <AssumptionsSection result={result} />
            <div className="mt-4 flex flex-wrap gap-3 border-t border-rule pt-10">
              <Button variant="primary" onClick={editSettings}>Change settings and run again</Button>
              <Button onClick={() => {
                if (request) setDraft(request);
                navigate("/backtest");
              }}>Backtest these settings</Button>
            </div>
          </div>
        </div>
      </Container>
    </>
  );
}
