import type { ReactNode } from "react";

export type Tone = "neutral" | "accent" | "success" | "warning" | "danger" | "muted";

export function Badge({ tone = "neutral", children, title }: { tone?: Tone; children: ReactNode; title?: string }) {
  return (
    <span className={`badge badge--${tone}`} title={title}>
      {children}
    </span>
  );
}
