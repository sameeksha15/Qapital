import { Link } from "react-router";
import { useSavedRuns } from "../api/queries";
import { day } from "../lib/format";
import { ChevronIcon } from "./icons";

/** The saved runs (real runs on the current snapshot), as links; `kind` narrows them to one page's kind. */
export function SavedRuns({ kind, compact = false }: { kind?: "optimise" | "backtest"; compact?: boolean }) {
  const saved = useSavedRuns();
  if (!saved.data) return null;
  const runs = saved.data.runs.filter((run) => !kind || run.kind === kind);
  return (
    <div>
      <ul className="border-t border-rule">
        {runs.map((run) => (
          <li key={run.id} className="border-b border-rule">
            <Link to={run.kind === "backtest" ? `/backtest/${run.id}` : `/results/${run.id}`}
                  className="group flex items-start justify-between gap-3 py-3 transition-colors hover:bg-paper-2/70">
              <span className="min-w-0">
                <span className="block text-sm font-medium text-ink group-hover:underline">{run.title}</span>
                {!compact && <span className="mt-0.5 block text-xs leading-snug text-ink-2">{run.description}</span>}
              </span>
              <ChevronIcon className="mt-0.5 h-4 w-4 text-muted transition-transform group-hover:translate-x-0.5" />
            </Link>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-muted">Real runs on prices up to {day(saved.data.snapshot)}.</p>
    </div>
  );
}
