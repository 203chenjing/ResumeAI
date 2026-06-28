import type { GapItem } from "@/lib/types";
import { copy } from "@/lib/copy";

const STATUS_LABEL: Record<GapItem["status"], { text: string; className: string }> = {
  match: { text: copy.match.gapHigh, className: "alert-success" },
  partial: { text: copy.match.gapMid, className: "alert-warning" },
  missing: { text: copy.match.gapMissing, className: "alert-error" },
};

export default function GapAnalysisList({ gaps }: { gaps: GapItem[] }) {
  if (!gaps.length) {
    return <p className="text-sm text-[var(--text-secondary)]">{copy.match.noGaps}</p>;
  }

  return (
    <ul className="space-y-2 max-h-64 overflow-y-auto">
      {gaps.map((g, i) => {
        const st = STATUS_LABEL[g.status];
        return (
          <li
            key={i}
            className="flex gap-2 items-start text-sm border border-[var(--border-subtle)] rounded-lg p-2 bg-[var(--surface-base)]"
          >
            <span className={`shrink-0 px-1.5 py-0.5 rounded text-xs font-medium ${st.className}`}>
              {st.text}
            </span>
            <div>
              <div className="font-medium text-[var(--text-primary)]">{g.requirement}</div>
              {g.detail && <div className="text-xs text-[var(--text-secondary)] mt-0.5">{g.detail}</div>}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
