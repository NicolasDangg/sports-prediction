import type { CSSProperties, ReactNode } from "react";

/** Staggered entrance in pure CSS: content is in the HTML from the first paint (no JS needed),
 *  and each tile rises in 45ms after the previous one. Disabled under prefers-reduced-motion. */
export default function Reveal({ i = 0, children, className = "" }: { i?: number; children: ReactNode; className?: string }) {
  return (
    <div className={`reveal ${className}`} style={{ "--i": i } as CSSProperties}>
      {children}
    </div>
  );
}
