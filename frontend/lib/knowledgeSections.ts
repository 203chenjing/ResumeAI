export interface KnowledgeSection {
  id: string;
  title: string;
  content: string;
  lineStart: number;
}

/** 按 ## 标题拆分知识库段落 */
export function parseKnowledgeSections(md: string): KnowledgeSection[] {
  const lines = md.split("\n");
  const sections: KnowledgeSection[] = [];
  let current: KnowledgeSection | null = null;

  for (let i = 0; i < lines.length; i++) {
    const m = /^##\s+(.+)/.exec(lines[i]);
    if (m) {
      if (current) sections.push(current);
      current = {
        id: `s-${i}`,
        title: m[1].trim(),
        content: "",
        lineStart: i,
      };
    } else if (current) {
      current.content += (current.content ? "\n" : "") + lines[i];
    }
  }
  if (current) sections.push(current);
  return sections;
}

export function countPendingMarkers(text: string): number {
  return (text.match(/\[待确认\]/g) || []).length;
}

export function isPhotoSection(section: KnowledgeSection): boolean {
  const t = section.title;
  return t.includes("个人照片") || t.includes("个人自定义");
}

export function sectionForLine(sections: KnowledgeSection[], line: number): KnowledgeSection | null {
  let found: KnowledgeSection | null = null;
  for (const s of sections) {
    if (s.lineStart <= line) found = s;
    else break;
  }
  return found;
}

/** 将某段 ## 区块的正文替换回完整 Markdown */
export function updateSectionContent(
  md: string,
  section: KnowledgeSection,
  newBody: string
): string {
  const lines = md.split("\n");
  let end = lines.length;
  for (let i = section.lineStart + 1; i < lines.length; i++) {
    if (/^##\s+/.test(lines[i])) {
      end = i;
      break;
    }
  }
  const bodyLines = newBody.replace(/\r\n/g, "\n").split("\n");
  return [...lines.slice(0, section.lineStart + 1), ...bodyLines, ...lines.slice(end)].join("\n");
}
