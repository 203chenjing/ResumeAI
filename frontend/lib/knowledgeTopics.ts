export interface KnowledgeTopic {
  id: string;
  title: string;
  level: number;
  lineStart: number;
}

/** 从 Markdown 标题解析左侧 Topic 树（对标 noosphere topic 层级 MVP） */
export function parseKnowledgeTopics(md: string): KnowledgeTopic[] {
  return md.split("\n").flatMap((line, idx) => {
    const m = /^(#{1,3})\s+(.+)/.exec(line);
    if (!m) return [];
    return [
      {
        id: `t-${idx}`,
        title: m[2].trim(),
        level: m[1].length,
        lineStart: idx,
      },
    ];
  });
}

/** 统计已记录事实条数（列表项） */
export function countKnowledgeFacts(md: string): number {
  return md.split("\n").filter((l) => /^[-*]\s+\S/.test(l.trim())).length;
}

/** 滚动到指定标题行（按行号近似定位） */
export function scrollToLine(lineStart: number) {
  const el = document.getElementById("knowledge-editor");
  if (!el || !(el instanceof HTMLTextAreaElement)) return;
  const lines = el.value.split("\n");
  let pos = 0;
  for (let i = 0; i < lineStart && i < lines.length; i++) {
    pos += lines[i].length + 1;
  }
  el.focus();
  el.setSelectionRange(pos, pos);
  const lineHeight = 20;
  el.scrollTop = Math.max(0, lineStart * lineHeight - 80);
}
