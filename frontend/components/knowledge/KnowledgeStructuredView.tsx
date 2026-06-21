"use client";

import type { ContentBlock } from "@/lib/knowledgeContentView";
import { parseSectionContent } from "@/lib/knowledgeContentView";

function RichText({ text }: { text: string }) {
  const parts = text.split(/(\[待确认\]|\[待补充：[^\]]+\]|\*\*[^*]+\*\*)/g);
  return (
    <span>
      {parts.map((part, i) => {
        if (part === "[待确认]") {
          return (
            <span
              key={i}
              className="inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded text-xs bg-amber-100 text-amber-800 border border-amber-200"
            >
              待确认
            </span>
          );
        }
        const pending = /^\[待补充：[^\]]+\]$/.exec(part);
        if (pending) {
          return (
            <span
              key={i}
              className="inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded text-xs bg-slate-100 text-slate-600 border border-slate-200"
            >
              待补充
            </span>
          );
        }
        const bold = /^\*\*([^*]+)\*\*$/.exec(part);
        if (bold) {
          return (
            <strong key={i} className="font-semibold text-[var(--text-primary)]">
              {bold[1]}
            </strong>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </span>
  );
}

function BlockView({ block }: { block: ContentBlock }) {
  switch (block.type) {
    case "subsection":
      return (
        <section className="rounded-xl border border-[var(--border-subtle)] bg-white overflow-hidden">
          <div className="px-4 py-2.5 bg-[var(--surface-base)] border-b border-[var(--border-subtle)]">
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">{block.title}</h3>
          </div>
          <div className="p-4 space-y-3">
            {block.blocks.length === 0 ? (
              <p className="text-sm text-[var(--text-disabled)]">（暂无内容）</p>
            ) : (
              block.blocks.map((b, i) => <BlockView key={i} block={b} />)
            )}
          </div>
        </section>
      );

    case "labeled":
      return (
        <div className="grid grid-cols-[5.5rem_1fr] md:grid-cols-[6.5rem_1fr] gap-2 md:gap-3 text-sm items-start">
          <span className="font-medium text-[var(--text-primary)] shrink-0">{block.label}</span>
          <span className="text-[var(--text-secondary)] leading-relaxed">
            {block.value ? <RichText text={block.value} /> : <span className="text-[var(--text-disabled)]">—</span>}
          </span>
        </div>
      );

    case "bullet":
      return (
        <div className="flex gap-2 text-sm text-[var(--text-secondary)] leading-relaxed">
          <span className="text-[var(--primary)] shrink-0 mt-0.5">•</span>
          <span>
            <RichText text={block.text} />
          </span>
        </div>
      );

    case "paragraph":
      return (
        <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
          <RichText text={block.text} />
        </p>
      );

    case "quote":
      return (
        <blockquote className="text-sm text-[var(--text-secondary)] border-l-[3px] border-[var(--primary)] pl-3 py-1 bg-[var(--primary-muted)]/40 rounded-r-lg">
          <RichText text={block.text} />
        </blockquote>
      );

    case "table":
      return (
        <div className="overflow-x-auto rounded-lg border border-[var(--border-subtle)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[var(--surface-base)]">
                {block.headers.map((h) => (
                  <th
                    key={h}
                    className="text-left px-3 py-2 font-medium text-[var(--text-primary)] border-b border-[var(--border-subtle)]"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.length === 0 ? (
                <tr>
                  <td
                    colSpan={block.headers.length}
                    className="px-3 py-3 text-[var(--text-disabled)] text-center"
                  >
                    暂无数据
                  </td>
                </tr>
              ) : (
                block.rows.map((row, ri) => (
                  <tr key={ri} className="border-t border-[var(--border-subtle)]">
                    {row.map((cell, ci) => (
                      <td key={ci} className="px-3 py-2 text-[var(--text-secondary)]">
                        <RichText text={cell || "—"} />
                      </td>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      );

    default:
      return null;
  }
}

export default function KnowledgeStructuredView({ content }: { content: string }) {
  const blocks = parseSectionContent(content);

  if (blocks.length === 0) {
    return <p className="text-sm text-[var(--text-disabled)]">（暂无内容，点击「编辑」补充）</p>;
  }

  return (
    <div className="space-y-4">
      {blocks.map((block, i) => (
        <BlockView key={i} block={block} />
      ))}
    </div>
  );
}
