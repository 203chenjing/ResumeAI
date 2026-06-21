import type { JobPosting } from "@/lib/types";

const SOURCE_LABELS: Record<string, string> = {
  job_aggregator: "求职平台",
  company_campus: "企业官网",
  university_html: "高校就业网",
  wechat_article: "公众号",
  feishu_bitable: "飞书秋招表",
};

export function sourceLabel(job: JobPosting): string {
  if (job.channel) return job.channel;
  return SOURCE_LABELS[job.source] || "校招";
}

export function workCities(job: JobPosting): string[] {
  const fromTags = (job.tags || [])
    .filter((t) => t.startsWith("工作地:"))
    .map((t) => t.replace("工作地:", ""));
  const merged = [...(job.locations || []), ...(job.location ? [job.location] : []), ...fromTags];
  return Array.from(new Set(merged.filter(Boolean))).slice(0, 4);
}

export function displayRole(job: JobPosting): string {
  const role = (job.role || "").trim();
  const company = (job.company || "").trim();
  if (!role || role === company) {
    const batch = role.match(/\d+(?:届)?(?:实习|校招|提前批|补录|秋招|春招)/);
    return batch?.[0] || job.job_type || "校招";
  }
  if (role.length > 36) return `${role.slice(0, 36)}…`;
  return role;
}

export function positionTitles(job: JobPosting): string {
  const m = (job.jd_text || "").match(/招聘岗位[：:]\s*([^\n]+)/);
  return m?.[1]?.trim() || "";
}

export function formatDateShort(iso?: string): string {
  if (!iso) return "—";
  const d = iso.slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(d)) return iso.slice(0, 10) || "—";
  return d.replace(/^\d{4}-/, "").replace("-", ".");
}

export function relativeTime(iso?: string): string {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const diff = Date.now() - t;
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${Math.max(1, mins)} 分钟前`;
  const hours = Math.floor(mins / 60);
  if (hours < 48) return `${hours} 小时前`;
  const days = Math.floor(hours / 24);
  if (days < 14) return `${days} 天前`;
  return formatDateShort(iso);
}

export function freshnessLabel(job: JobPosting): string {
  if (job.published_at) return `收录 ${formatDateShort(job.published_at)}`;
  if (job.crawled_at) return relativeTime(job.crawled_at);
  return "—";
}

export function isActionableJob(job: JobPosting): boolean {
  return job.validation_status !== "invalid";
}

export function publisherLabel(job: JobPosting): string {
  const fromTag = (job.tags || []).find((t) => t.startsWith("发布方:"));
  if (fromTag) return fromTag.replace("发布方:", "");
  if (job.source === "university_html") {
    const facet = facetTags(job).find((t) => /清华|北大|复旦|交大|浙大|武大|华科|中大|华工|人大|北航|同济|厦大|西交|成电/.test(t));
    if (facet) return facet;
    return job.city ? `${job.city}·高校就业网` : "高校就业网";
  }
  return sourceLabel(job);
}

export function displayCompany(job: JobPosting): string {
  const c = (job.company || "").trim();
  if (!c || c === "招聘单位待确认" || c === "待确认公司") return "—";
  if (/大学|学院|学校/.test(c) && c.length <= 20) return "—";
  return c;
}

export function facetTags(job: JobPosting): string[] {
  const internal = new Set(["job_aggregator", "company_campus", "university_html", "wechat_article", "聚合"]);
  return (job.tags || []).filter(
    (t) => !t.startsWith("来源:") && !t.startsWith("工作地:") && !t.startsWith("发布方:") && !internal.has(t)
  );
}
