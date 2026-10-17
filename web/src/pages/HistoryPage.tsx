import { Link } from "react-router";
import { TrashIcon } from "../components/icons";
import { SavedRuns } from "../components/SavedRuns";
import { Button, ButtonLink, Container, Kicker, Section } from "../components/ui";
import { ago } from "../lib/format";
import { clearHistory, removeFromHistory, useHistory } from "../lib/history";

/** Runs started or opened in this browser. The results live on the server, so every link can be shared. */
export function HistoryPage() {
  const history = useHistory();
  return (
    <Container className="pb-20 pt-12">
      <Kicker>History</Kicker>
      <h1 className="mt-3 font-serif text-4xl text-ink">Your runs</h1>
      <p className="mt-3 max-w-2xl text-sm leading-relaxed text-ink-2">
        Kept in this browser only; there are no accounts. Each link opens the result itself, so you can send it to anyone.
      </p>

      <Section title={history.length ? `${history.length} run${history.length > 1 ? "s" : ""}` : "Nothing yet"} stacked>
        {history.length === 0 ? (
          <div>
            <p className="text-sm text-ink-2">Runs you start or open appear here.</p>
            <ButtonLink to="/" variant="primary" arrow className="mt-6">Run the optimiser</ButtonLink>
          </div>
        ) : (
          <>
            <ul className="border-t border-ink">
              {history.map((entry) => (
                <li key={entry.id} className="flex items-start justify-between gap-4 border-b border-rule py-4">
                  <Link to={entry.kind === "backtest" ? `/backtest/${entry.id}` : `/results/${entry.id}`} className="group min-w-0">
                    <span className="block font-medium text-ink group-hover:underline">{entry.title}</span>
                    <span className="mt-0.5 block text-xs text-ink-2">{entry.kind === "backtest" ? "Backtest" : "Optimisation"}{entry.detail && ` · ${entry.detail}`}</span>
                    <span className="mt-0.5 block text-xs text-muted">{ago(entry.createdAt)}</span>
                  </Link>
                  <button type="button" aria-label={`Forget ${entry.title}`} onClick={() => removeFromHistory(entry.id)}
                          className="rounded-full p-2 text-muted transition hover:bg-paper-2 hover:text-bad">
                    <TrashIcon />
                  </button>
                </li>
              ))}
            </ul>
            <Button variant="ghost" className="mt-4 px-0" onClick={clearHistory}>Forget all</Button>
          </>
        )}
      </Section>

      <Section title="Saved runs" stacked note="Real runs on the current prices, always available, even when the live engine is asleep.">
        <SavedRuns />
      </Section>
    </Container>
  );
}
