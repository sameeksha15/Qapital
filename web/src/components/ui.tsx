import { motion } from "motion/react";
import { useId, type ButtonHTMLAttributes, type ReactNode } from "react";
import { Link, type LinkProps } from "react-router";
import { AlertIcon, ArrowRightIcon, CheckIcon, CrossIcon, InfoIcon, LockIcon } from "./icons";
import { Reveal } from "./motion";
import { WaveField } from "./WaveField";

export function Container({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`mx-auto w-full max-w-6xl px-4 sm:px-8 ${className}`}>{children}</div>;
}

interface HeroProps {
  children: ReactNode;
  peaks?: number[];
  highlight?: number;
  speed?: number;
  caption?: string;
  className?: string;
}

/** The navy opening band of a page, with the probability wave behind it. */
export function Hero({ children, peaks, highlight, speed, caption, className = "" }: HeroProps) {
  return (
    <section className={`relative isolate overflow-hidden bg-navy text-navy-ink ${className}`}>
      <div className="absolute inset-x-0 bottom-0 -z-10 h-1/2 opacity-90 sm:h-[78%]">
        <WaveField peaks={peaks} highlight={highlight} speed={speed} />
      </div>
      <Container className="relative py-14 sm:py-20">{children}</Container>
      {caption && <p className="absolute bottom-3 right-5 hidden text-[11px] italic text-navy-muted sm:right-8 sm:block">{caption}</p>}
    </section>
  );
}

export function Kicker({ children, onDark = false }: { children: ReactNode; onDark?: boolean }) {
  return <p className={`font-mono text-xs uppercase tracking-[0.14em] ${onDark ? "text-navy-muted" : "text-muted"}`}>{children}</p>;
}

interface SectionProps {
  id?: string;
  number?: string;
  title: ReactNode;
  note?: ReactNode;
  children: ReactNode;
  stacked?: boolean;
}

/**
 * A numbered report section: a hairline on top, the title and a short margin note on the left,
 * the content on the right. `stacked` puts the title above the content instead.
 */
export function Section({ id, number, title, note, children, stacked = false }: SectionProps) {
  return (
    <Reveal as="section" id={id}
            className={`scroll-mt-24 border-t border-rule py-12 ${stacked ? "" : "grid gap-x-12 gap-y-6 lg:grid-cols-[230px_minmax(0,1fr)]"}`}>
      <header className={stacked ? "mb-8 max-w-3xl" : ""}>
        {number && <p className="font-mono text-xs text-signal">{number}</p>}
        <h2 className="mt-1.5 font-serif text-[26px] leading-tight text-ink">{title}</h2>
        {note && <p className="mt-3 text-sm leading-relaxed text-ink-2">{note}</p>}
      </header>
      <div className="min-w-0">{children}</div>
    </Reveal>
  );
}

export function Subsection({ title, note, children }: { title: ReactNode; note?: ReactNode; children: ReactNode }) {
  return (
    <div className="mt-14 min-w-0">
      <h3 className="font-serif text-xl text-ink">{title}</h3>
      {note && <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-2">{note}</p>}
      <div className="mt-5">{children}</div>
    </div>
  );
}

/** Large figures in a row, divided by hairlines rather than boxed. */
export function StatStrip({ children, onDark = false, className = "" }: { children: ReactNode; onDark?: boolean; className?: string }) {
  return (
    <dl className={`grid grid-cols-2 gap-y-8 lg:grid-flow-col lg:auto-cols-fr ${onDark ? "[--strip-rule:rgba(238,241,247,0.18)]" : "[--strip-rule:var(--rule)]"} ${className}`}>
      {children}
    </dl>
  );
}

interface StatProps {
  label: ReactNode;
  value: ReactNode;
  detail?: ReactNode;
  onDark?: boolean;
  highlight?: boolean;
}

export function Stat({ label, value, detail, onDark = false, highlight = false }: StatProps) {
  return (
    <div className="min-w-0 border-l border-(--strip-rule) pl-4 pr-3 sm:pl-5 sm:pr-4">
      <dd className={`font-serif text-[32px] leading-none tracking-tight sm:text-[40px] ${highlight ? "text-signal" : onDark ? "text-navy-ink" : "text-ink"}`}>{value}</dd>
      <dt className={`mt-2.5 text-sm ${onDark ? "text-navy-ink" : "text-ink"}`}>{label}</dt>
      {detail && <p className={`mt-0.5 text-xs leading-snug ${onDark ? "text-navy-muted" : "text-muted"}`}>{detail}</p>}
    </div>
  );
}

export interface Option<T> {
  value: T;
  label: ReactNode;
}

interface SegmentedProps<T> {
  label?: string;
  options: Option<T>[];
  value: T;
  onChange: (value: T) => void;
  disabled?: boolean;
  size?: "sm" | "md";
}

/** A row of mutually exclusive choices; the selection pill slides to the chosen option. */
export function Segmented<T>({ label, options, value, onChange, disabled = false, size = "md" }: SegmentedProps<T>) {
  const id = useId();
  const pad = size === "sm" ? "px-3 py-1 text-xs" : "px-3.5 py-1.5 text-sm";
  return (
    <div className="min-w-0">
      {label && <div className="mb-2 text-xs font-medium text-ink-2">{label}</div>}
      <div role="radiogroup" aria-label={label}
           className={`inline-flex flex-wrap gap-0.5 rounded-[18px] border border-rule p-0.5 ${disabled ? "opacity-55" : ""}`}>
        {options.map((option) => {
          const selected = option.value === value;
          return (
            <button key={String(option.value)} type="button" role="radio" aria-checked={selected} disabled={disabled}
                    onClick={() => onChange(option.value)}
                    className={`relative rounded-full ${pad} transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed ${
                      selected ? "text-paper" : "text-ink-2 enabled:hover:text-ink"
                    }`}>
              {selected && (
                <motion.span layoutId={`pill-${id}`} className="absolute inset-0 rounded-full bg-ink"
                             transition={{ type: "spring", stiffness: 520, damping: 42 }} />
              )}
              <span className="relative">{option.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

interface ToggleProps {
  label: ReactNode;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  note?: ReactNode;
}

export function Toggle({ label, checked, onChange, disabled = false, note }: ToggleProps) {
  return (
    <label className={`flex items-start gap-3 ${disabled ? "cursor-not-allowed" : "cursor-pointer"}`}>
      <span className="relative mt-0.5 inline-flex">
        <input type="checkbox" className="peer sr-only" checked={checked} disabled={disabled}
               onChange={(event) => onChange(event.target.checked)} />
        <span className="h-5 w-9 rounded-full bg-rule-strong transition-colors peer-checked:bg-ink peer-disabled:opacity-40 peer-focus-visible:outline-2 peer-focus-visible:outline-accent" />
        <span className="absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-paper shadow transition-transform peer-checked:translate-x-4" />
      </span>
      <span>
        <span className={`block text-sm ${disabled ? "text-muted" : "text-ink"}`}>{label}</span>
        {note && <span className="block text-xs text-muted">{note}</span>}
      </span>
    </label>
  );
}

const BUTTONS = {
  primary: "bg-ink text-paper hover:bg-ink/90",
  secondary: "border border-rule-strong text-ink hover:border-ink",
  ghost: "text-ink-2 hover:text-ink",
  onDark: "border border-white/25 text-navy-ink hover:border-white/60",
};

type ButtonStyle = { variant?: keyof typeof BUTTONS; size?: "sm" | "md"; arrow?: boolean };

function buttonClass({ variant = "secondary", size = "md" }: ButtonStyle, className = "") {
  const padding = size === "sm" ? "gap-1.5 px-2.5 py-0.5" : "gap-2 px-5 py-2.5";
  return `group inline-flex items-center justify-center rounded-full text-sm font-medium transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-40 ${padding} ${BUTTONS[variant]} ${className}`;
}

const arrowIcon = <ArrowRightIcon className="h-4 w-4 transition-transform group-enabled:group-hover:translate-x-1 group-[a]:group-hover:translate-x-1" />;

export function Button({ variant, size, arrow = false, className = "", children, ...props }: ButtonStyle & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button type="button" {...props} className={buttonClass({ variant, size }, className)}>
      {children}
      {arrow && arrowIcon}
    </button>
  );
}

/** A link that looks like a button. */
export function ButtonLink({ variant, size, arrow = false, className = "", children, ...props }: ButtonStyle & LinkProps) {
  return (
    <Link {...props} className={buttonClass({ variant, size }, className)}>
      {children}
      {arrow && arrowIcon}
    </Link>
  );
}

const NOTE_STYLES = {
  good: { rule: "border-good", text: "text-good", Icon: CheckIcon },
  bad: { rule: "border-bad", text: "text-bad", Icon: CrossIcon },
  warn: { rule: "border-warn", text: "text-warn", Icon: AlertIcon },
  neutral: { rule: "border-rule-strong", text: "text-ink-2", Icon: InfoIcon },
};

/** A message marked by a coloured rule on its left, always with an icon and words (never colour alone). */
export function Note({ tone = "neutral", title, children }: { tone?: keyof typeof NOTE_STYLES; title?: ReactNode; children?: ReactNode }) {
  const { rule, text, Icon } = NOTE_STYLES[tone];
  return (
    <div role={tone === "bad" ? "alert" : "status"} className={`flex gap-3 border-l-2 py-1 pl-4 ${rule}`}>
      <Icon className={`mt-0.5 h-4 w-4 ${text}`} />
      <div className="min-w-0 text-sm leading-relaxed">
        {title && <p className={`font-medium ${text}`}>{title}</p>}
        {children && <div className="text-ink-2">{children}</div>}
      </div>
    </div>
  );
}

export function LockedNote({ children }: { children: ReactNode }) {
  return <p className="flex items-center gap-1.5 text-xs text-muted"><LockIcon className="h-3.5 w-3.5" />{children}</p>;
}

/** 01 Settings — 02 Run — 03 Results, with the current step underlined. */
export function Stepper({ steps, current }: { steps: string[]; current: number }) {
  return (
    <ol className="flex flex-wrap items-center gap-x-6 gap-y-2">
      {steps.map((step, i) => (
        <li key={step} className="relative flex items-baseline gap-2 pb-1.5">
          <span className={`font-mono text-xs ${i <= current ? "text-signal" : "text-muted"}`}>{String(i + 1).padStart(2, "0")}</span>
          <span className={`text-sm ${i === current ? "font-medium text-ink" : i < current ? "text-ink-2" : "text-muted"}`}>{step}</span>
          {i === current && <motion.span layoutId="stepper-underline" className="absolute inset-x-0 bottom-0 h-px bg-ink" />}
        </li>
      ))}
    </ol>
  );
}

export function Loading({ children = "Loading…" }: { children?: ReactNode }) {
  return (
    <div role="status" className="flex items-center gap-3 py-16 text-sm text-ink-2">
      <span className="relative h-px w-16 overflow-hidden bg-rule">
        <motion.span className="absolute inset-y-0 w-6 bg-ink" animate={{ x: [-24, 64] }}
                     transition={{ duration: 1.1, repeat: Infinity, ease: "easeInOut" }} />
      </span>
      {children}
    </div>
  );
}

export function Ticker({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <span className={`font-mono font-medium tracking-tight ${className}`}>{children}</span>;
}

/** Table cells in the report style: hairline rows, right-aligned numbers. */
export function Th({ children, numeric = false, className = "" }: { children?: ReactNode; numeric?: boolean; className?: string }) {
  return <th className={`py-2.5 pr-4 text-xs font-medium text-muted ${numeric ? "text-right" : "text-left"} ${className}`}>{children}</th>;
}

export function Td({ children, numeric = false, className = "", colSpan }: { children?: ReactNode; numeric?: boolean; className?: string; colSpan?: number }) {
  return <td colSpan={colSpan} className={`py-3 pr-4 ${numeric ? "text-right tabular-nums" : ""} ${className}`}>{children}</td>;
}

/** A label above a form control, with an optional hint below it. */
export function Field({ label, hint, children, htmlFor }: { label: ReactNode; hint?: ReactNode; children: ReactNode; htmlFor?: string }) {
  return (
    <div className="min-w-0">
      <label htmlFor={htmlFor} className="mb-2 block text-xs font-medium text-ink-2">{label}</label>
      {children}
      {hint && <p className="mt-1.5 text-xs leading-snug text-muted">{hint}</p>}
    </div>
  );
}

export const inputClass =
  "w-full rounded-lg border border-rule-strong bg-paper px-3 py-2 text-sm text-ink tabular-nums placeholder:text-muted focus:border-ink focus:outline-none disabled:opacity-50";

/** A term and its value in a side panel's list. */
export function Row({ term, value }: { term: ReactNode; value: ReactNode }) {
  return (
    <div className="flex justify-between gap-3 border-b border-rule pb-2.5">
      <dt className="text-muted">{term}</dt>
      <dd className="text-right text-ink">{value}</dd>
    </div>
  );
}

/** A fact under a hairline: small label, serif value, optional detail. */
export function Fact({ term, value, detail }: { term: ReactNode; value: ReactNode; detail?: ReactNode }) {
  return (
    <div className="border-t border-rule pt-3">
      <dt className="text-xs text-muted">{term}</dt>
      <dd className="mt-1 font-serif text-lg leading-snug text-ink">{value}</dd>
      {detail && <dd className="mt-0.5 text-xs text-ink-2">{detail}</dd>}
    </div>
  );
}
