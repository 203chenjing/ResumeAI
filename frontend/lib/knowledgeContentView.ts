/** 将知识库段落 Markdown 解析为可渲染的结构化块（预览用，非编辑） */

export type ContentBlock =
  | { type: "subsection"; title: string; blocks: ContentBlock[] }
  | { type: "labeled"; label: string; value: string }
  | { type: "bullet"; text: string }
  | { type: "paragraph"; text: string }
  | { type: "table"; headers: string[]; rows: string[][] }
  | { type: "quote"; text: string };

const LABELED_RE = /^[-*]\s+\*\*([^*]+)\*\*[：:]\s*(.*)$/;
const BULLET_RE = /^[-*]\s+(.+)$/;
const SUBSECTION_RE = /^###\s+(.+)$/;

function splitTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((c) => c.trim());
}

function parseBlocks(content: string, allowSubsections: boolean): ContentBlock[] {
  const lines = content.split("\n");
  const blocks: ContentBlock[] = [];
  let i = 0;

  while (i < lines.length) {
    const raw = lines[i];
    const line = raw.trim();
    if (!line) {
      i++;
      continue;
    }

    if (allowSubsections && SUBSECTION_RE.test(line)) {
      const title = line.replace(/^###\s+/, "").trim();
      i++;
      const chunk: string[] = [];
      while (i < lines.length) {
        const peek = lines[i].trim();
        if (SUBSECTION_RE.test(peek)) break;
        chunk.push(lines[i]);
        i++;
      }
      blocks.push({
        type: "subsection",
        title,
        blocks: parseBlocks(chunk.join("\n"), false),
      });
      continue;
    }

    if (line.startsWith("|") && i + 1 < lines.length && /^\|[-:\s|]+\|$/.test(lines[i + 1].trim())) {
      const headers = splitTableRow(line);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        rows.push(splitTableRow(lines[i]));
        i++;
      }
      blocks.push({ type: "table", headers, rows });
      continue;
    }

    if (line.startsWith(">")) {
      const quoteLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith(">")) {
        quoteLines.push(lines[i].trim().replace(/^>\s?/, ""));
        i++;
      }
      blocks.push({ type: "quote", text: quoteLines.join(" ") });
      continue;
    }

    const labeled = LABELED_RE.exec(line);
    if (labeled) {
      blocks.push({ type: "labeled", label: labeled[1].trim(), value: labeled[2].trim() });
      i++;
      continue;
    }

    const bullet = BULLET_RE.exec(line);
    if (bullet) {
      blocks.push({ type: "bullet", text: bullet[1].trim() });
      i++;
      continue;
    }

    const paraLines: string[] = [line];
    i++;
    while (i < lines.length) {
      const peek = lines[i].trim();
      if (
        !peek ||
        peek.startsWith("#") ||
        peek.startsWith("|") ||
        peek.startsWith(">") ||
        LABELED_RE.test(peek) ||
        BULLET_RE.test(peek)
      ) {
        break;
      }
      paraLines.push(peek);
      i++;
    }
    blocks.push({ type: "paragraph", text: paraLines.join(" ") });
  }

  return blocks;
}

export function parseSectionContent(content: string): ContentBlock[] {
  return parseBlocks(content.trim(), true);
}

/** 结构化摘要（用于卡片预览） */
export function summarizeSectionContent(content: string, maxItems = 4): string[] {
  const blocks = parseSectionContent(content);
  const lines: string[] = [];

  for (const b of blocks) {
    if (lines.length >= maxItems) break;
    if (b.type === "subsection") {
      lines.push(b.title);
      for (const inner of b.blocks.slice(0, 2)) {
        if (lines.length >= maxItems) break;
        if (inner.type === "labeled" && inner.value) {
          lines.push(`${inner.label}：${inner.value.slice(0, 48)}`);
        } else if (inner.type === "bullet") {
          lines.push(stripInlineMarkup(inner.text).slice(0, 56));
        }
      }
    } else if (b.type === "labeled" && b.value) {
      lines.push(`${b.label}：${b.value.slice(0, 56)}`);
    } else if (b.type === "bullet") {
      lines.push(stripInlineMarkup(b.text).slice(0, 64));
    } else if (b.type === "paragraph") {
      lines.push(stripInlineMarkup(b.text).slice(0, 64));
    }
  }

  return lines.filter(Boolean);
}

export function stripInlineMarkup(text: string): string {
  return text
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\[待确认\]/g, "待确认")
    .replace(/\[待补充：[^\]]+\]/g, "待补充")
    .replace(/`([^`]+)`/g, "$1")
    .trim();
}
