import type { Stage } from "@/lib/types";

export const FLOW: { stage: Stage; label: string }[] = [
  { stage: "IDENTITY", label: "Identity" },
  { stage: "PROFILING", label: "Profiling" },
  { stage: "RECOMMENDATION", label: "Recommendation" },
  { stage: "APPLICATION", label: "Application" },
];

/**
 * Index of the current step in FLOW. SUBMITTED means every step is done (FLOW.length).
 * Terminal stages that do not say where the flow stopped (HANDOFF, DECLINED, WITHDRAWN) use `fallback`.
 */
export function stageIndex(stage: Stage, fallback = 0): number {
  if (stage === "SUBMITTED") return FLOW.length;
  const i = FLOW.findIndex((s) => s.stage === stage);
  return i === -1 ? fallback : i;
}

export function StageStrip({ stage, fallback, compact }: { stage: Stage; fallback?: number; compact?: boolean }) {
  const current = stageIndex(stage, fallback);
  return (
    <ol className={`stages ${compact ? "stages--compact" : ""}`} aria-label="Onboarding progress">
      {FLOW.map((s, i) => {
        const state = i < current ? "done" : i === current ? "current" : "todo";
        return (
          <li key={s.stage} className={`stages__step stages__step--${state}`} aria-current={state === "current" ? "step" : undefined}>
            <span className="stages__dot">{state === "done" ? "✓" : i + 1}</span>
            <span className="stages__label">{s.label}</span>
          </li>
        );
      })}
    </ol>
  );
}
