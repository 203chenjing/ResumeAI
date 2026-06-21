"use client";

import type { KnowledgeSection } from "@/lib/knowledgeSections";
import { countPendingMarkers } from "@/lib/knowledgeSections";
import { summarizeSectionContent } from "@/lib/knowledgeContentView";

type Props = {
  section: KnowledgeSection;
  selected?: boolean;
  onSelect?: () => void;
};

export default function KnowledgeSectionCard({ section, selected, onSelect }: Props) {
  const pending = countPendingMarkers(section.content);
  const summary = summarizeSectionContent(section.content, 3);

  return (
    <article
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => e.key === "Enter" && onSelect?.()}
      className={`p-4 rounded-xl border cursor-pointer transition ${
        selected
          ? "border-[var(--primary)] bg-[var(--primary)]/5"
          : "border-[var(--border-subtle)] bg-[var(--surface-container)] hover:border-[var(--primary)]/40"
      }`}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <h3 className="font-semibold text-sm text-[var(--text-primary)]">{section.title}</h3>
        {pending > 0 && (
          <span className="shrink-0 text-xs px-2 py-0.5 rounded bg-[var(--semantic-warning)]/15 text-[var(--semantic-warning)]">
            {pending} 待确认
          </span>
        )}
      </div>
      {summary.length === 0 ? (
        <p className="text-xs text-[var(--text-disabled)]">（空）</p>
      ) : (
        <ul className="space-y-1.5">
          {summary.map((line, i) => (
            <li key={i} className="text-xs text-[var(--text-secondary)] leading-relaxed flex gap-1.5">
              <span className="text-[var(--primary)] shrink-0">·</span>
              <span className="line-clamp-2">{line}</span>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
