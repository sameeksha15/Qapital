import { useEffect, useId, useState } from "react";
import { Field, inputClass } from "./ui";

interface NumberInputProps {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  hint?: string;
  prefix?: string;
  disabled?: boolean;
}

/**
 * A number box that lets the visitor clear it and type freely; the value is passed on whenever the text is a valid
 * number within the limits, and the box goes back to the last valid value when it loses focus.
 */
export function NumberInput({ label, value, onChange, min, max, step = 1, hint, prefix, disabled }: NumberInputProps) {
  const id = useId();
  const [text, setText] = useState(String(value));
  useEffect(() => setText((current) => (Number(current) === value ? current : String(value))), [value]);
  const valid = (n: number) => Number.isFinite(n) && (min == null || n >= min) && (max == null || n <= max);

  return (
    <Field label={label} hint={hint} htmlFor={id}>
      <div className="relative">
        {prefix && <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted">{prefix}</span>}
        <input id={id} type="number" inputMode="decimal" className={`${inputClass} ${prefix ? "pl-7" : ""}`}
               value={text} min={min} max={max} step={step} disabled={disabled}
               onChange={(event) => {
                 setText(event.target.value);
                 const n = Number(event.target.value);
                 if (event.target.value.trim() !== "" && valid(n)) onChange(n);
               }}
               onBlur={() => setText(String(value))} />
      </div>
    </Field>
  );
}

/** − 4 + : a small whole-number stepper. */
export function NumberStepper({ label, value, min, max, onChange, disabled }: {
  label: string; value: number; min: number; max: number; onChange: (value: number) => void; disabled?: boolean;
}) {
  const button = "h-9 w-9 rounded-full border border-rule-strong text-lg text-ink-2 transition enabled:hover:border-ink enabled:hover:text-ink disabled:opacity-35";
  return (
    <div>
      <div className="mb-2 text-xs font-medium text-ink-2">{label}</div>
      <div className="inline-flex items-center gap-3">
        <button type="button" className={button} disabled={disabled || value <= min} aria-label={`Fewer: ${label}`} onClick={() => onChange(value - 1)}>−</button>
        <span className="w-8 text-center font-serif text-3xl tabular-nums text-ink" aria-live="polite">{value}</span>
        <button type="button" className={button} disabled={disabled || value >= max} aria-label={`More: ${label}`} onClick={() => onChange(value + 1)}>+</button>
      </div>
    </div>
  );
}

const RISK_LEVELS = [0.25, 0.5, 1, 2, 4];

export function RiskSlider({ value, onChange, disabled }: { value: number; onChange: (value: number) => void; disabled?: boolean }) {
  const position = Math.max(0, RISK_LEVELS.indexOf(value));
  return (
    <div>
      <div className="mb-2 flex justify-between text-xs font-medium text-ink-2">
        <span>Risk appetite</span>
        <span className="tabular-nums text-ink">risk aversion {value}</span>
      </div>
      <input type="range" min={0} max={RISK_LEVELS.length - 1} step={1} value={position} disabled={disabled}
             aria-label="Risk aversion" onChange={(event) => onChange(RISK_LEVELS[Number(event.target.value)])}
             className="w-full accent-signal disabled:opacity-50" />
      <div className="flex justify-between text-xs text-muted"><span>Higher return</span><span>Safer</span></div>
    </div>
  );
}
