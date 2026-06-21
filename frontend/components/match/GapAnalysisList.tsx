import type { GapItem } from "@/lib/types";

const STATUS_LABEL: Record<GapItem["status"], { text: string; className: string }> = {
  match: { text: "高", className: "bg-green-100 text-green-800" },
  partial: { text: "中", className: "bg-amber-100 text-amber-800" },
  missing: { text: "缺失", className: "bg-red-100 text-red-800" },
};

export default function GapAnalysisList({ gaps }: { gaps: GapItem[] }) {
  if (!gaps.length) {
    return <p className="text-sm text-slate-500">暂无差距分析</p>;
  }

  return (
    <ul className="space-y-2 max-h-64 overflow-y-auto">
      {gaps.map((g, i) => {
        const st = STATUS_LABEL[g.status];
        return (
          <li
            key={i}
            className="flex gap-2 items-start text-sm border border-slate-100 rounded-lg p-2 bg-slate-50"
          >
            <span className={`shrink-0 px-1.5 py-0.5 rounded text-xs font-medium ${st.className}`}>
              {st.text}
            </span>
            <div>
              <div className="font-medium text-slate-800">{g.requirement}</div>
              {g.detail && <div className="text-xs text-slate-500 mt-0.5">{g.detail}</div>}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
