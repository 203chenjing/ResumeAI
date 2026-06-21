const STORAGE_KEY = "resumeai_user_memory";
const CLIENT_ID_KEY = "resumeai_client_id";

export interface UserMemory {
  knowledge_base_md: string;
  notes: string;
  preferences: {
    writing_style: string;
    prefer_accept_safe: boolean;
    remind_finalize: boolean;
    review_policy?: string;
    recent_intent?: string;
  };
}

const DEFAULT: UserMemory = {
  knowledge_base_md: "",
  notes: "",
  preferences: {
    writing_style: "量化数据、STAR 结构、有力动词",
    prefer_accept_safe: true,
    remind_finalize: true,
    review_policy: "accept_safe",
    recent_intent: "",
  },
};

/** 根据记忆与偏好生成编辑页快捷提示（非写死列表） */
export function buildQuickPrompts(mem?: UserMemory): string[] {
  const m = mem || loadLocalMemory();
  const style = m.preferences.writing_style || "量化";
  const policy = m.preferences.review_policy || "accept_safe";
  const recent = m.preferences.recent_intent?.trim();
  const prompts = [
    m.knowledge_base_md?.trim() ? "根据知识库重新生成简历" : recent || "按目标岗位优化经历描述",
    policy === "accept_all" ? "全部采纳建议" : "采纳稳妥的建议",
    "现在进展怎么样",
    "定稿并下载 PDF",
  ];
  return [...new Set(prompts.filter(Boolean))].slice(0, 4);
}

/** 上传页 Agent 目标：优先用户近期意图，否则由后端根据会话推断 */
export function buildOrchestrateGoal(mem?: UserMemory): string {
  const m = mem || loadLocalMemory();
  const recent = m.preferences.recent_intent?.trim();
  if (recent) return recent;
  const style = m.preferences.writing_style || "量化";
  return `针对当前岗位完成匹配与建议生成，写作风格偏向：${style}`;
}

export function getClientId(): string {
  if (typeof window === "undefined") return "default";
  let id = localStorage.getItem(CLIENT_ID_KEY);
  if (!id) {
    id = `u_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
    localStorage.setItem(CLIENT_ID_KEY, id);
  }
  return id;
}

export function loadLocalMemory(): UserMemory {
  if (typeof window === "undefined") return DEFAULT;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT };
    const data = JSON.parse(raw) as Partial<UserMemory>;
    return {
      ...DEFAULT,
      ...data,
      preferences: { ...DEFAULT.preferences, ...data.preferences },
    };
  } catch {
    return { ...DEFAULT };
  }
}

export function saveLocalMemory(mem: Partial<UserMemory>) {
  const merged = { ...loadLocalMemory(), ...mem };
  if (mem.preferences) {
    merged.preferences = { ...loadLocalMemory().preferences, ...mem.preferences };
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(merged));
  return merged;
}
