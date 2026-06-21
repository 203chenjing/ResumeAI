/** 知识库内 [待确认] / [待补充：…] 标记解析与替换 */

export interface PendingMarkerItem {
  id: string;
  lineIndex: number;
  kind: "待确认" | "待补充";
  label: string;
  context: string;
  marker: string;
}

const MARKER_RE = /\[待确认\]|\[待补充：([^\]]+)\]/g;

export function extractPendingMarkers(md: string): PendingMarkerItem[] {
  const items: PendingMarkerItem[] = [];
  const lines = md.split("\n");

  lines.forEach((line, lineIndex) => {
    let match: RegExpExecArray | null;
    const re = new RegExp(MARKER_RE.source, "g");
    while ((match = re.exec(line)) !== null) {
      const marker = match[0];
      const isTodo = marker === "[待确认]";
      items.push({
        id: `m-${lineIndex}-${match.index}`,
        lineIndex,
        kind: isTodo ? "待确认" : "待补充",
        label: isTodo ? "待确认事实" : match[1] || "补充项",
        context: line.trim().replace(/^[-*]\s+/, ""),
        marker,
      });
    }
  });

  return items;
}

export function resolvePendingMarker(md: string, item: PendingMarkerItem, value: string): string {
  const lines = md.split("\n");
  const line = lines[item.lineIndex];
  if (!line) return md;

  const replacement = value.trim();
  if (!replacement) return md;

  lines[item.lineIndex] = line.replace(item.marker, replacement);
  return lines.join("\n");
}

export function removePendingMarker(md: string, item: PendingMarkerItem): string {
  const lines = md.split("\n");
  const line = lines[item.lineIndex];
  if (!line) return md;
  lines[item.lineIndex] = line.replace(item.marker, "").replace(/\s{2,}/g, " ").trim();
  return lines.join("\n");
}
