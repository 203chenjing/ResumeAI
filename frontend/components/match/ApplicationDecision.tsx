import { copy } from "@/lib/copy";

export interface ApplicationDecision {
  match_score: number;
  legitimacy_score: number;
  level: "strong" | "moderate" | "weak" | "risk";
  label: string;
  recommend_apply: boolean;
  top_gaps: string[];
}

const LEVEL_STYLE: Record<ApplicationDecision["level"], string> = {
  strong: "bg-green-50 border-green-200 text-green-800",
  moderate: "bg-[var(--primary-muted)] border-[var(--primary)]/20 text-[var(--primary)]",
  weak: "bg-[var(--surface-base)] border-[var(--border-subtle)] text-[var(--text-secondary)]",
  risk: "bg-red-50 border-red-200 text-red-800",
};

export default function ApplicationDecisionCard({
  decision,
}: {
  decision: ApplicationDecision;
}) {
  return (
    <div className={`rounded-lg border p-4 ${LEVEL_STYLE[decision.level]}`}>
      <div className="font-semibold">{decision.label}</div>
      <div className="text-xs mt-1 opacity-90">
        {copy.match.scoreLine(decision.match_score, decision.legitimacy_score)}
      </div>
      {decision.top_gaps.length > 0 && (
        <div className="mt-2 text-xs">
          <span className="font-medium">{copy.match.topGaps}</span>
          {decision.top_gaps.join("、")}
        </div>
      )}
    </div>
  );
}
