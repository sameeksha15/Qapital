import type { ReactNode } from "react";

interface IconProps {
  className?: string;
}

// Small line icons (24×24 grid, 1.75 stroke), coloured by the surrounding text.
function Icon({ children, className = "h-4 w-4" }: IconProps & { children: ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round"
         strokeLinejoin="round" aria-hidden="true" className={`shrink-0 ${className}`}>
      {children}
    </svg>
  );
}

export const CheckIcon = (props: IconProps) => <Icon {...props}><path d="M5 12.5l4.5 4.5L19 7.5" /></Icon>;
export const CrossIcon = (props: IconProps) => <Icon {...props}><path d="M6 6l12 12M18 6L6 18" /></Icon>;
export const InfoIcon = (props: IconProps) => <Icon {...props}><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></Icon>;
export const AlertIcon = (props: IconProps) => <Icon {...props}><path d="M12 3l9.5 17h-19z" /><path d="M12 10v4M12 17h.01" /></Icon>;
export const LockIcon = (props: IconProps) => <Icon {...props}><rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 018 0v3" /></Icon>;
export const PlayIcon = (props: IconProps) => <Icon {...props}><path d="M8 5.5v13l10.5-6.5z" /></Icon>;
export const PauseIcon = (props: IconProps) => <Icon {...props}><path d="M9 5v14M15 5v14" /></Icon>;
export const ArrowLeftIcon = (props: IconProps) => <Icon {...props}><path d="M19 12H5M11 6l-6 6 6 6" /></Icon>;
export const ArrowRightIcon = (props: IconProps) => <Icon {...props}><path d="M5 12h14M13 6l6 6-6 6" /></Icon>;
export const SearchIcon = (props: IconProps) => <Icon {...props}><circle cx="11" cy="11" r="6.5" /><path d="M20 20l-4.2-4.2" /></Icon>;
export const LinkIcon = (props: IconProps) => <Icon {...props}><path d="M10 14a4 4 0 005.7 0l3-3a4 4 0 00-5.7-5.7l-1 1" /><path d="M14 10a4 4 0 00-5.7 0l-3 3a4 4 0 005.7 5.7l1-1" /></Icon>;
export const PlusIcon = (props: IconProps) => <Icon {...props}><path d="M12 5v14M5 12h14" /></Icon>;
export const TrashIcon = (props: IconProps) => <Icon {...props}><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" /></Icon>;
export const ClockIcon = (props: IconProps) => <Icon {...props}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></Icon>;
export const ChevronIcon = (props: IconProps) => <Icon {...props}><path d="M9 6l6 6-6 6" /></Icon>;

/** The brand mark: a Bloch sphere (the picture of one qubit) drawn as a circle, an equator and a state arrow. */
export function BrandMark({ className = "h-7 w-7" }: IconProps) {
  return (
    <svg viewBox="0 0 32 32" fill="none" aria-hidden="true" className={className}>
      <circle cx="16" cy="16" r="12.5" stroke="currentColor" strokeWidth="1.5" opacity="0.9" />
      <ellipse cx="16" cy="16" rx="12.5" ry="4.5" stroke="currentColor" strokeWidth="1.2" opacity="0.45" />
      <path d="M16 16L23 7.5" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" />
      <circle cx="23" cy="7.5" r="2" fill="var(--accent)" />
      <circle cx="16" cy="16" r="1.4" fill="currentColor" />
    </svg>
  );
}
