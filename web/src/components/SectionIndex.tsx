import { motion } from "motion/react";
import { useEffect, useState } from "react";

/**
 * A sticky list of the page's sections; the marker follows the section being read.
 * `sections` ({id, label}) must be a stable array (defined outside the component).
 */
export function SectionIndex({ sections }: { sections: { id: string; label: string }[] }) {
  const [active, setActive] = useState(sections[0].id);

  useEffect(() => {
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting);
      if (visible.length) setActive(visible[0].target.id);
    }, { rootMargin: "-25% 0px -65% 0px" });
    for (const { id } of sections) {
      const element = document.getElementById(id);
      if (element) observer.observe(element);
    }
    return () => observer.disconnect();
  }, [sections]);

  return (
    <nav aria-label="On this page" className="hidden lg:block">
      <ol className="sticky top-28 mt-12 border-l border-rule">
        {sections.map((section, i) => (
          <li key={section.id} className="relative">
            {active === section.id && (
              <motion.span layoutId="section-marker" className="absolute -left-px inset-y-0 w-0.5 bg-signal"
                           transition={{ type: "spring", stiffness: 380, damping: 34 }} />
            )}
            <button type="button" onClick={() => document.getElementById(section.id)?.scrollIntoView({ behavior: "smooth" })}
                    className={`block py-1.5 pl-4 text-left text-sm transition-colors ${active === section.id ? "text-ink" : "text-muted hover:text-ink-2"}`}>
              <span className="mr-2 font-mono text-xs text-signal/80">{String(i + 1).padStart(2, "0")}</span>{section.label}
            </button>
          </li>
        ))}
      </ol>
    </nav>
  );
}
