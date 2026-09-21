"use client";

import { useTranslations } from "next-intl";
import type { Stage } from "@/lib/types";

export const FLOW: Stage[] = ["IDENTITY", "PROFILING", "RECOMMENDATION", "APPLICATION"];

/**
 * Index of the current step in FLOW. SUBMITTED means every step is done (FLOW.length).
 * Terminal stages that do not say where the flow stopped (HANDOFF, DECLINED, WITHDRAWN) use `fallback`.
 */
export function stageIndex(stage: Stage, fallback = 0): number {
  if (stage === "SUBMITTED") return FLOW.length;
  const i = FLOW.indexOf(stage);
  return i === -1 ? fallback : i;
}

export function StageStrip({ stage, fallback, compact }: { stage: Stage; fallback?: number; compact?: boolean }) {
  const t = useTranslations();
  const current = stageIndex(stage, fallback);
  return (
    <ol className={`stages ${compact ? "stages--compact" : ""}`} aria-label={t("stageStrip.label")}>
      {FLOW.map((s, i) => {
        const state = i < current ? "done" : i === current ? "current" : "todo";
        return (
          <li key={s} className={`stages__step stages__step--${state}`} aria-current={state === "current" ? "step" : undefined}>
            <span className="stages__dot">{state === "done" ? "✓" : i + 1}</span>
            <span className="stages__label">{t(`stage.${s}`)}</span>
          </li>
        );
      })}
    </ol>
  );
}
