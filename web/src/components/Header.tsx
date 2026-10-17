import { motion } from "motion/react";
import { Link, NavLink } from "react-router";
import { useConnection, type ConnectionState } from "../api/connection";
import { APP_NAME } from "../lib/format";
import { useHistory } from "../lib/history";
import { BrandMark, ClockIcon } from "./icons";

export const PAGES = [
  { to: "/", label: "Optimise", end: true },
  { to: "/backtest", label: "Backtest" },
  { to: "/data", label: "Data" },
  { to: "/research", label: "Research" },
  { to: "/how", label: "How it works" },
];

const STATUS: Record<ConnectionState, { label: string; dot: string; pulse: boolean; title: string }> = {
  checking: { label: "Connecting", dot: "bg-navy-muted", pulse: true, title: "Asking the live engine whether it is up." },
  live: { label: "Live engine", dot: "bg-emerald-400", pulse: true, title: "Runs start on the live engine." },
  waking: { label: "Engine starting", dot: "bg-amber-400", pulse: true,
    title: "The live engine isn't answering yet (it may be restarting after an update). Saved runs are shown meanwhile." },
  saved: { label: "Saved runs", dot: "bg-navy-muted", pulse: false, title: "The live engine isn't reachable; showing saved runs." },
};

export function Header() {
  const { state, retry } = useConnection();
  const history = useHistory();
  const status = STATUS[state];

  return (
    <header className="sticky top-0 z-30 border-b border-white/10 bg-navy/95 text-navy-ink backdrop-blur">
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-x-8 gap-y-2 px-4 py-3 sm:px-8">
        <Link to="/" className="flex items-center gap-2.5">
          <BrandMark className="h-6 w-6" />
          <span className="font-serif text-lg tracking-tight">{APP_NAME}</span>
        </Link>
        <nav className="order-3 -mx-1 flex w-full gap-5 overflow-x-auto px-1 sm:order-0 sm:w-auto" aria-label="Main">
          {PAGES.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end}
                     className={({ isActive }) => `relative shrink-0 py-1.5 text-sm transition-colors ${isActive ? "text-navy-ink" : "text-navy-muted hover:text-navy-ink"}`}>
              {({ isActive }) => (
                <>
                  {item.label}
                  {isActive && (
                    <motion.span layoutId="nav-underline" className="absolute inset-x-0 -bottom-3.25 h-0.5 bg-signal"
                                 transition={{ type: "spring", stiffness: 420, damping: 36 }} />
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="flex items-center gap-4 text-xs text-navy-muted">
          <NavLink to="/history" className={({ isActive }) => `flex items-center gap-1.5 transition-colors hover:text-navy-ink ${isActive ? "text-navy-ink" : ""}`}>
            <ClockIcon className="h-3.5 w-3.5" />History{history.length > 0 && <span className="tabular-nums">· {history.length}</span>}
          </NavLink>
          <span className="flex items-center gap-2" title={status.title}>
            <motion.span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${status.dot}`}
                         animate={status.pulse ? { opacity: [1, 0.35, 1] } : undefined}
                         transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }} />
            {status.label}
            {state === "saved" && (
              <button type="button" onClick={retry} className="underline underline-offset-2 hover:text-navy-ink">retry</button>
            )}
          </span>
        </div>
      </div>
    </header>
  );
}
