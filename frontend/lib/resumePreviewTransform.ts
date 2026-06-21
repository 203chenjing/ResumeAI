/** 与 PDF 导出器一致：教育/实习表头行 → 三列 HTML */
const HEADER_LONG_NAME_THRESHOLD = 13;

const ROLE_HINT =
  /(实习生|工程师|经理|专员|顾问|管培|分析师|设计师|开发|产品|运营|方向|管培生)/;
const CITY_NAMES = new Set([
  "上海",
  "北京",
  "深圳",
  "广州",
  "杭州",
  "南京",
  "成都",
  "武汉",
  "西安",
  "苏州",
]);

function looksLikeRole(text: string): boolean {
  const t = text.trim();
  return ROLE_HINT.test(t) || t.includes("（") || t.includes("(");
}

function looksLikeCity(text: string): boolean {
  const t = text.trim();
  return CITY_NAMES.has(t) || t.endsWith("市");
}

function formatContactHtml(line: string): string {
  const raw = line.replace(/\*\*([^*]+)\*\*/g, "$1").trim();
  if (raw.startsWith("求职意向")) {
    const role = raw.replace(/^求职意向[：:]\s*/, "").trim();
    return `<p class="target-role"><strong>${role}</strong></p>`;
  }
  if (raw.startsWith("手机")) {
    const parts = raw.split(/\s*[|｜]\s*/);
    const cleaned = parts.map((p) => {
      const s = p.trim();
      if (s.startsWith("手机：")) return s.replace("手机：", "").trim();
      if (s.startsWith("邮箱：")) return s.replace("邮箱：", "").trim();
      return s;
    });
    return `<p class="contact-line">${cleaned.join(" · ")}</p>`;
  }
  const parts = raw.split(/\s*[·|｜]\s*/).map((p) => p.trim()).filter(Boolean);
  let role: string | undefined;
  if (parts.length && looksLikeRole(parts[parts.length - 1]) && !looksLikeCity(parts[parts.length - 1])) {
    role = parts.pop();
  }
  let html = `<p class="contact-line">${parts.join(" · ")}</p>`;
  if (role) html += `\n<p class="target-role"><strong>${role}</strong></p>`;
  return html;
}

export function transformContactHeader(md: string): string {
  const lines = md.split("\n");
  const out: string[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.startsWith("# ") && !line.startsWith("## ")) {
      out.push(line);
      i += 1;
      while (i < lines.length && !lines[i].trim()) i += 1;
      if (i >= lines.length) break;
      const nxt = lines[i].trim();
      if (nxt.startsWith("## ") || nxt.startsWith("![个人照片]")) continue;
      if (
        nxt.includes("·") ||
        nxt.includes("|") ||
        nxt.includes("｜") ||
        nxt.startsWith("手机") ||
        nxt.startsWith("求职意向")
      ) {
        out.push("");
        out.push(formatContactHtml(nxt));
        i += 1;
        while (i < lines.length && !lines[i].trim()) i += 1;
        if (i < lines.length && lines[i].trim().startsWith("求职意向")) {
          out.push(formatContactHtml(lines[i].trim()));
          i += 1;
        }
        continue;
      }
    }
    out.push(line);
    i += 1;
  }
  return out.join("\n");
}

function normalizeHeaderLeft(left: string): string {
  return left.trim().replace(/\s+/g, "");
}

function mergeHeaderContinuations(md: string): string {
  const lines = md.split("\n");
  const out: string[] = [];
  const headerRe =
    /^\*\*([^*]+)\*\*\s{2,}(.+?)\s{2,}(\d{4}\.\d{2}(?:-\d{4}\.\d{2}|-\S+)|至今)\s*$/;
  const suffixRe = /^[\(（][^)）]+[\)）]?\s*有限公司$|^有限公司$/;
  let i = 0;
  while (i < lines.length) {
    let line = lines[i];
    const stripped = line.trim();
    const m = stripped.startsWith("**") ? headerRe.exec(stripped) : null;
    if (m && i + 1 < lines.length) {
      const nxt = lines[i + 1].trim();
      if (
        nxt &&
        !nxt.startsWith("**") &&
        !nxt.startsWith("#") &&
        !nxt.startsWith("-") &&
        !nxt.startsWith("*") &&
        !/^\d+\./.test(nxt)
      ) {
        if (suffixRe.test(nxt) || (nxt.includes("公司") && nxt.length <= 24)) {
          const left = normalizeHeaderLeft(m[1] + nxt);
          line = `**${left}**  ${m[2].trim()}  ${m[3].trim()}`;
          i += 1;
        }
      }
    }
    out.push(line);
    i += 1;
  }
  return out.join("\n");
}

export function transformHeaderRows(md: string): string {
  return mergeHeaderContinuations(md)
    .split("\n")
    .map((line) => parseHeaderLine(line) ?? line)
    .join("\n");
}

function headerRowHtml(left: string, mid: string, right: string): string {
  const leftClean = normalizeHeaderLeft(left);
  const longCls = leftClean.length > HEADER_LONG_NAME_THRESHOLD ? " long-left" : "";
  return (
    `<div class="resume-header-row">` +
    `<span class="col-left${longCls}"><strong>${leftClean}</strong></span>` +
    `<span class="col-mid">${mid}</span>` +
    `<span class="col-right">${right}</span>` +
    `</div>`
  );
}

function parseHeaderLine(line: string): string | null {
  const stripped = line.trim();
  if (!stripped.startsWith("**")) return null;

  const exp = /^\*\*([^*]+)\*\*\s{2,}(.+?)\s{2,}(\d{4}\.\d{2}(?:-\d{4}\.\d{2}|-\S+)|至今)\s*$/.exec(
    stripped
  );
  if (exp) return headerRowHtml(exp[1], exp[2].trim(), exp[3].trim());

  const edu = /^\*\*([^*]+)\*\*\s{2,}(.+?)[，,]\s*(\d{4}\.\d{2}(?:-\d{4}\.\d{2}|-\S+))\s*$/.exec(
    stripped
  );
  if (edu) return headerRowHtml(edu[1], edu[2].trim(), edu[3].trim());

  return null;
}

export function stripPhotoMarkdown(md: string): { md: string; hadPhoto: boolean } {
  const hadPhoto = /!\[个人照片\]/.test(md);
  const cleaned = md.replace(/!\[个人照片\]\([^)]+\)\s*\n?/, "");
  return { md: cleaned, hadPhoto };
}

export function prepareResumePreviewMarkdown(md: string): string {
  return transformHeaderRows(transformContactHeader(md));
}
