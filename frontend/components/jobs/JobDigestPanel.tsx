"use client";

import type { JobDigest } from "@/lib/types";
import { displayRole } from "@/lib/jobDisplay";
import { Loader2, Sparkles } from "lucide-react";

const PRIORITY_STYLE: Record<string, string> = {
  P0: "bg-red-100 text-red-800 border-red-200",
  P1: "bg-amber-100 text-amber-900 border-amber-200",
  P2: "bg-slate-100 text-slate-700 border-slate-200",
};

export default function JobDigestPanel({
  digest,
  loading,
  onRegenerate,
  onApplyJob,
}: {
  digest: JobDigest | null;
  loading?: boolean;
  onRegenerate?: () => void;
  onApplyJob?: (jobId: string) => void;
}) {
  if (loading) {
    return (
      <div className="mb-4 p-4 bg-violet-50 border border-violet-100 rounded-xl flex items-center gap-2 text-sm text-violet-800">
        <Loader2 size={16} className="animate-spin" /> AI 正在分析可投递岗位…
      </div>
    );
  }

  if (!digest) {
    return (
      <div className="mb-4 p-4 bg-slate-50 border rounded-xl text-sm text-slate-600">
        填写求职偏好后点击「刷新岗位」，AI 将总结新增职位并给出投递优先级。
        {onRegenerate && (
          <button type="button" onClick={onRegenerate} className="ml-2 text-violet-600 hover:underline">
            立即生成摘要
          </button>
        )}
      </div>
    );
  }

  return (
    <section className="mb-4 bg-gradient-to-br from-violet-50 to-white border border-violet-100 rounded-xl p-4">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2">
          <Sparkles size={18} className="text-violet-600 shrink-0" />
          <h2 className="font-semibold text-slate-900">{digest.headline}</h2>
        </div>
        {onRegenerate && (
          <button
            type="button"
            onClick={onRegenerate}
            className="text-xs text-violet-600 hover:underline shrink-0"
          >
            重新分析
          </button>
        )}
      </div>
      <p className="text-sm text-slate-700 leading-relaxed">{digest.summary}</p>
      {digest.action_tips?.length > 0 && (
        <ul className="mt-2 text-xs text-slate-600 space-y-1 list-disc pl-4">
          {digest.action_tips.map((t) => (
            <li key={t}>{t}</li>
          ))}
        </ul>
      )}
      {digest.priority_jobs?.length > 0 && (
        <div className="mt-4">
          <h3 className="text-xs font-semibold text-slate-500 mb-2 uppercase tracking-wide">
            建议投递顺序
          </h3>
          <div className="space-y-2">
            {digest.priority_jobs.slice(0, 8).map((item, idx) => (
              <div
                key={item.job_id}
                className="flex flex-wrap items-center gap-2 bg-white/80 border rounded-lg px-3 py-2 text-sm"
              >
                <span className="text-slate-400 w-5 text-xs">{idx + 1}</span>
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded border font-bold ${
                    PRIORITY_STYLE[item.priority] || PRIORITY_STYLE.P2
                  }`}
                >
                  {item.priority}
                </span>
                {item.is_new && (
                  <span className="text-[10px] px-1.5 py-0.5 bg-green-100 text-green-800 rounded">新</span>
                )}
                <span className="font-medium text-slate-900">{item.company}</span>
                <span className="text-blue-700">{displayRole(item as { role: string; company: string })}</span>
                <span className="text-xs text-slate-500">{item.reasons?.join(" · ")}</span>
                {onApplyJob && (
                  <button
                    type="button"
                    onClick={() => onApplyJob(item.job_id)}
                    className="ml-auto text-xs text-violet-600 hover:underline"
                  >
                    用此 JD 改简历
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
      {digest.generated_at && (
        <p className="mt-3 text-[10px] text-slate-400">
          生成于 {digest.generated_at.slice(0, 16).replace("T", " ")}
          {digest.used_llm ? " · AI 润色" : " · 规则引擎"}
        </p>
      )}
    </section>
  );
}
