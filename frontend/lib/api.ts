// API 请求封装
import { ApiResponse, JDAnalysis, MatchResult, ParsedResume, Suggestion, ApplicationRecord, ApplicationStats, PendingKnowledgeItem, JobPosting, JobFeedMeta, JobPreferences, JobDigest, CompareRow, InterviewPrepPack, Reminder, PatternInsights, UserProfile, CareerCopilotEvent, CrawlHealth } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers || {}),
    },
  });
  if (!res.ok) {
    let errMsg = `${res.status} ${res.statusText}`;
    try {
      const data = await res.json();
      errMsg = data.detail || data.error || errMsg;
    } catch {}
    throw new Error(errMsg);
  }
  return (await res.json()) as T;
}

export const api = {
  async parseResume(file: File) {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`${API_BASE}/api/parse-resume`, { method: "POST", body: fd });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || `解析失败 (${res.status})`);
    }
    return (await res.json()) as ApiResponse<{
      session_id: string;
      format: string;
      parsed: ParsedResume;
      markdown: string;
    }>;
  },

  analyzeJD(session_id: string, jd_text: string) {
    return request<ApiResponse<{ analysis: JDAnalysis }>>("/api/analyze-jd", {
      method: "POST",
      body: JSON.stringify({ session_id, jd_text }),
    });
  },

  analyzeMatch(session_id: string) {
    return request<
      ApiResponse<{
        match: MatchResult;
        decision?: {
          match_score: number;
          legitimacy_score: number;
          level: string;
          label: string;
          recommend_apply: boolean;
          top_gaps: string[];
        };
      }>
    >("/api/analyze-match", {
      method: "POST",
      body: JSON.stringify({ session_id }),
    });
  },

  getUserMemory(client_id: string) {
    return request<ApiResponse<Record<string, unknown>>>(`/api/user-memory/${client_id}`);
  },

  saveUserMemory(payload: {
    client_id: string;
    knowledge_base_md?: string;
    notes?: string;
    preferences?: Record<string, unknown>;
  }) {
    return request<ApiResponse<Record<string, unknown>>>("/api/user-memory", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },

  getKnowledgeTemplate() {
    return request<ApiResponse<{ template: string }>>("/api/knowledge-base/template");
  },

  getKnowledgeBase(session_id: string) {
    return request<
      ApiResponse<{ content: string; has_content: boolean; has_photo?: boolean; photo_url?: string }>
    >(`/api/knowledge-base/${session_id}`);
  },

  saveKnowledgeBase(session_id: string, content: string) {
    return request<
      ApiResponse<{
        content: string;
        current_markdown?: string;
        has_photo?: boolean;
      }>
    >("/api/knowledge-base", {
      method: "PUT",
      body: JSON.stringify({ session_id, content }),
    });
  },

  knowledgeAgent: {
    initFromResume(body: { client_id: string; session_id: string }) {
      return request<ApiResponse<{ markdown: string }>>("/api/knowledge-agent/init-from-resume", {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
    expandStar(body: { section_title: string; content: string; hint?: string }) {
      return request<ApiResponse<{ markdown: string }>>("/api/knowledge-agent/expand-star", {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
    audit(body: { content: string }) {
      return request<
        ApiResponse<{
          issues: string[];
          pending_count: number;
          summary: string;
        }>
      >("/api/knowledge-agent/audit", {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
    chat(body: {
      client_id: string;
      content: string;
      message: string;
      session_id?: string;
      ui_context?: Record<string, unknown>;
      history?: { role: string; content: string }[];
    }) {
      return request<
        ApiResponse<{
          reply: string;
          updated_markdown?: string | null;
          saved?: boolean;
          ui_patch?: {
            focus_panel?: "topics" | "pending";
            select_section_title?: string;
            saved?: boolean;
          };
        }>
      >("/api/knowledge-agent/chat", {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
  },

  async uploadProfilePhoto(session_id: string, file: File) {
    const fd = new FormData();
    fd.append("session_id", session_id);
    fd.append("file", file);
    const res = await fetch(`${API_BASE}/api/knowledge-base/photo`, {
      method: "POST",
      body: fd,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || `照片上传失败 (${res.status})`);
    }
    return (await res.json()) as ApiResponse<{
      photo_ref: string;
      photo_url: string;
      current_markdown: string;
      finalize_status?: string;
    }>;
  },

  deleteProfilePhoto(session_id: string) {
    return request<ApiResponse<{ current_markdown: string }>>(
      `/api/knowledge-base/photo/${session_id}`,
      { method: "DELETE" }
    );
  },

  generateSuggestions(session_id: string, knowledge_base = "") {
    return request<
      ApiResponse<{
        suggestions: Suggestion[];
        summary: Record<string, unknown>;
        density?: { char_count: number; status: string; message: string };
      }>
    >("/api/generate-suggestions", {
      method: "POST",
      body: JSON.stringify({ session_id, knowledge_base }),
    });
  },

  updateSuggestionStatus(
    session_id: string,
    suggestion_id: string,
    status: string,
    client_id?: string
  ) {
    return request<
      ApiResponse<{
        current_markdown: string;
        suggestion: Suggestion;
        finalize_status?: string;
        match?: MatchResult;
        suggestions?: Suggestion[];
        density?: { char_count: number; status: string; message: string };
      }>
    >("/api/update-suggestion-status", {
      method: "POST",
      body: JSON.stringify({
        session_id,
        suggestion_id,
        status,
        client_id: client_id || "default",
      }),
    });
  },

  adjustSuggestion(session_id: string, suggestion_id: string, instruction: string) {
    return request<ApiResponse<{ updated: Suggestion }>>("/api/adjust-suggestion", {
      method: "POST",
      body: JSON.stringify({ session_id, suggestion_id, instruction }),
    });
  },

  exportPdfUrl(session_id: string, mode: "standard" | "diff" = "standard") {
    // 直接 POST 触发下载
    return `${API_BASE}/api/export-pdf`;
  },

  finalizeResume(session_id: string) {
    return request<
      ApiResponse<{
        markdown: string;
        regenerated: boolean;
        validation: {
          skill_passed: boolean;
          page_passed: boolean;
          page_count: number;
          skill_issues?: string[];
          layout_issues?: string[];
        };
        finalize_status: "draft" | "finalized" | "stale";
      }>
    >("/api/finalize-resume", {
      method: "POST",
      body: JSON.stringify({ session_id }),
    });
  },

  getSession(session_id: string) {
    return request<ApiResponse<Record<string, unknown>>>(`/api/session/${session_id}`);
  },

  getApplications(client_id: string) {
    return request<
      ApiResponse<{
        applications: ApplicationRecord[];
        stats: ApplicationStats;
      }>
    >(`/api/applications/${client_id}`);
  },

  createApplication(payload: Partial<ApplicationRecord> & { client_id: string }) {
    return request<ApiResponse<ApplicationRecord>>("/api/applications", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  updateApplicationStatus(
    client_id: string,
    app_id: string,
    status: string,
    notes = ""
  ) {
    return request<ApiResponse<ApplicationRecord>>("/api/applications/status", {
      method: "PATCH",
      body: JSON.stringify({ client_id, app_id, status, notes }),
    });
  },

  deleteApplication(client_id: string, app_id: string) {
    return request<ApiResponse<ApplicationRecord>>(`/api/applications/${client_id}/${app_id}`, {
      method: "DELETE",
    });
  },

  getPendingKnowledge(client_id: string) {
    return request<ApiResponse<{ items: PendingKnowledgeItem[] }>>(
      `/api/pending-knowledge/${client_id}`
    );
  },

  confirmPendingKnowledge(client_id: string, entry_id: string, action: "confirm" | "ignore") {
    return request<ApiResponse<PendingKnowledgeItem>>("/api/pending-knowledge/confirm", {
      method: "POST",
      body: JSON.stringify({ client_id, entry_id, action }),
    });
  },

  mergePendingToKnowledge(client_id: string) {
    return request<ApiResponse<{ knowledge_base_md: string }>>(
      `/api/pending-knowledge/merge-to-kb?client_id=${encodeURIComponent(client_id)}`,
      { method: "POST" }
    );
  },

  getJobFeed(
    client_id: string,
    params?: { source?: string; job_type?: string; work_city?: string; include_weak?: boolean }
  ) {
    const q = new URLSearchParams();
    if (params?.source) q.set("source", params.source);
    if (params?.job_type) q.set("job_type", params.job_type);
    if (params?.work_city) q.set("work_city", params.work_city);
    if (params?.include_weak === false) q.set("include_weak", "false");
    const qs = q.toString();
    return request<ApiResponse<{ jobs: JobPosting[]; meta?: JobFeedMeta; digest?: JobDigest | null }>>(
      `/api/jobs/feed/${client_id}${qs ? `?${qs}` : ""}`
    );
  },

  getJobPreferences(client_id: string) {
    return request<ApiResponse<JobPreferences>>(`/api/jobs/preferences/${client_id}`);
  },

  saveJobPreferences(client_id: string, prefs: JobPreferences) {
    return request<ApiResponse<JobPreferences>>("/api/jobs/preferences", {
      method: "PUT",
      body: JSON.stringify({ client_id, ...prefs }),
    });
  },

  getJobDigest(client_id: string) {
    return request<ApiResponse<JobDigest | null>>(`/api/jobs/digest/${client_id}`);
  },

  generateJobDigest(client_id: string, new_job_ids?: string[]) {
    return request<ApiResponse<JobDigest>>("/api/jobs/digest", {
      method: "POST",
      body: JSON.stringify({ client_id, new_job_ids: new_job_ids ?? [] }),
    });
  },

  crawlJobs(client_id: string, providers?: string[]) {
    return request<
      ApiResponse<{
        new_count: number;
        total: number;
        report: Array<{
          provider: string;
          status: string;
          fetched?: number;
          added?: number;
          duration_ms?: number;
          error?: string;
        }>;
        quality?: {
          validated_ok?: number;
          validated_weak?: number;
          rejected?: number;
          dup_skipped_new?: number;
          duplicates_removed?: number;
        };
        jobs: JobPosting[];
        digest?: JobDigest;
      }>
    >("/api/jobs/crawl", {
      method: "POST",
      body: JSON.stringify({ client_id, providers: providers ?? null }),
    });
  },

  syncFeishuJobs(client_id: string) {
    return request<
      ApiResponse<{
        new_count: number;
        total: number;
        report: Array<{
          provider: string;
          status: string;
          fetched?: number;
          duration_ms?: number;
          error?: string;
        }>;
        quality?: {
          validated_ok?: number;
          validated_weak?: number;
          rejected?: number;
        };
        jobs: JobPosting[];
        digest?: JobDigest;
      }>
    >("/api/jobs/sync-feishu", {
      method: "POST",
      body: JSON.stringify({ client_id }),
    });
  },

  getFeishuJobStatus() {
    return request<
      ApiResponse<{
        configured: boolean;
        enabled: boolean;
        job_types_include: string[];
        source_count: number;
        sources: Array<{
          id?: string;
          name?: string;
          base_token?: string;
          table_id?: string;
          view_id?: string;
        }>;
      }>
    >("/api/jobs/feishu/status");
  },

  dedupeJobFeed(client_id: string) {
    return request<
      ApiResponse<{
        before: number;
        after: number;
        duplicates_removed: number;
        jobs: JobPosting[];
      }>
    >("/api/jobs/dedupe", {
      method: "POST",
      body: JSON.stringify({ client_id }),
    });
  },

  ingestWechatJob(client_id: string, url: string) {
    return request<ApiResponse<JobPosting>>("/api/jobs/ingest-wechat", {
      method: "POST",
      body: JSON.stringify({ client_id, url }),
    });
  },

  compareJobs(client_id: string, job_ids: string[], resume_md = "") {
    return request<ApiResponse<{ rows: CompareRow[]; compared_count: number }>>("/api/jobs/compare", {
      method: "POST",
      body: JSON.stringify({ client_id, job_ids, resume_md }),
    });
  },

  getCrawlHealth(client_id: string) {
    return request<ApiResponse<CrawlHealth>>(`/api/jobs/crawl-health/${client_id}`);
  },

  rerankJobs(client_id: string, top_k = 20) {
    return request<
      ApiResponse<{
        algorithm: string;
        count: number;
        rows: Array<{
          job_id: string;
          company: string;
          role: string;
          hybrid_score: number;
          score_breakdown: Record<string, number>;
          match: MatchResult;
        }>;
      }>
    >("/api/jobs/rerank", {
      method: "POST",
      body: JSON.stringify({ client_id, top_k }),
    });
  },

  async streamCareerCopilot(
    client_id: string,
    message: string,
    onEvent: (event: CareerCopilotEvent) => void,
    onError: (err: Error) => void
  ) {
    try {
      const res = await fetch(`${API_BASE}/api/career-copilot/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client_id, message }),
      });
      if (!res.ok) throw new Error(`Copilot 失败 (${res.status})`);
      if (!res.body) throw new Error("无响应流");
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";
        for (const block of events) {
          const line = block.split("\n").find((l) => l.startsWith("data:"));
          if (!line) continue;
          const payload = JSON.parse(line.slice(5).trim()) as CareerCopilotEvent;
          onEvent(payload);
          if (payload.type === "error") onError(new Error(payload.message || "失败"));
        }
      }
    } catch (e) {
      onError(e as Error);
    }
  },

  getMasterResume(client_id: string) {
    return request<ApiResponse<{ masters: unknown[]; active: { markdown: string } | null }>>(
      `/api/master-resume/${client_id}`
    );
  },

  saveMasterResume(client_id: string, markdown: string, title = "母版简历") {
    return request<ApiResponse<unknown>>("/api/master-resume", {
      method: "POST",
      body: JSON.stringify({ client_id, markdown, title }),
    });
  },

  getInterviewPrep(client_id: string, application_id = "", extra?: { jd_text?: string; company?: string; role?: string }) {
    return request<ApiResponse<InterviewPrepPack>>("/api/interview/prep", {
      method: "POST",
      body: JSON.stringify({ client_id, application_id, ...extra }),
    });
  },

  async streamMockInterview(
    params: {
      client_id: string;
      application_id?: string;
      round_type?: string;
      user_answer?: string;
      turn?: number;
      company?: string;
      role?: string;
      jd_text?: string;
    },
    onEvent: (event: MockInterviewEvent) => void,
    onError: (err: Error) => void
  ) {
    try {
      const res = await fetch(`${API_BASE}/api/interview/mock`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(params),
      });
      if (!res.ok) throw new Error(`模拟面试失败 (${res.status})`);
      if (!res.body) throw new Error("无响应流");
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";
        for (const block of events) {
          const line = block.split("\n").find((l) => l.startsWith("data:"));
          if (!line) continue;
          const payload = JSON.parse(line.slice(5).trim()) as MockInterviewEvent;
          onEvent(payload);
          if (payload.type === "error") onError(new Error(payload.message || "失败"));
        }
      }
    } catch (e) {
      onError(e as Error);
    }
  },

  getReminders(client_id: string) {
    return request<ApiResponse<{ reminders: Reminder[] }>>(`/api/reminders/${client_id}`);
  },

  getPatternInsights(client_id: string) {
    return request<ApiResponse<PatternInsights>>(`/api/insights/patterns/${client_id}`);
  },

  getUserProfile(client_id: string) {
    return request<ApiResponse<UserProfile>>(`/api/user-profile/${client_id}`);
  },

  saveUserProfile(payload: Partial<UserProfile> & { client_id: string }) {
    return request<ApiResponse<UserProfile>>("/api/user-profile", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },

  getFinalizeStatus(session_id: string) {
    return request<
      ApiResponse<{
        finalize_status: "draft" | "finalized" | "stale";
        finalized_markdown: string;
        working_markdown: string;
      }>
    >(`/api/finalize-status/${session_id}`);
  },

  async exportPdf(session_id: string, mode: "standard" | "diff" = "standard"): Promise<Blob> {
    const res = await fetch(`${API_BASE}/api/export-pdf`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id, mode }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || `导出失败 (${res.status})`);
    }
    return await res.blob();
  },

  /** 流式聊天：fetch + ReadableStream 解析 SSE（兼容 CRLF）。 */
  async streamChat(
    session_id: string,
    message: string,
    onText: (chunk: string) => void,
    onDone: (payload: {
      reply: string;
      new_suggestions: Suggestion[];
      suggestions?: Suggestion[];
      current_markdown?: string;
      match?: MatchResult | null;
      finalize_status?: "draft" | "finalized" | "stale";
    }) => void,
    onError: (err: Error) => void
  ) {
    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id, message }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `聊天失败 (${res.status})`);
      }
      if (!res.body) throw new Error("无响应流");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let gotDone = false;

      const handleEvent = (raw: string) => {
        const line = raw
          .split("\n")
          .map((l) => l.trimEnd())
          .find((l) => l.startsWith("data:"));
        if (!line) return;
        const jsonText = line.slice(5).trimStart();
        if (!jsonText) return;

        const payload = JSON.parse(jsonText) as {
          type: string;
          content?: string;
          reply?: string;
          message?: string;
          new_suggestions?: Suggestion[];
          suggestions?: Suggestion[];
          current_markdown?: string;
          match?: MatchResult | null;
          finalize_status?: "draft" | "finalized" | "stale";
        };

        if (payload.type === "text" && payload.content) onText(payload.content);
        if (payload.type === "done") {
          gotDone = true;
          onDone({
            reply: payload.reply || "",
            new_suggestions: payload.new_suggestions || [],
            suggestions: payload.suggestions,
            current_markdown: payload.current_markdown,
            match: payload.match,
            finalize_status: payload.finalize_status,
          });
        }
        if (payload.type === "error") onError(new Error(payload.message || "聊天失败"));
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        buffer = buffer.replace(/\r\n/g, "\n");
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";
        for (const eventBlock of events) {
          try {
            handleEvent(eventBlock);
          } catch (err) {
            console.error("SSE parse error:", err, eventBlock);
          }
        }
      }

      if (buffer.trim()) {
        try {
          handleEvent(buffer);
        } catch (err) {
          console.error("SSE tail parse error:", err, buffer);
        }
      }

      if (!gotDone) {
        onError(new Error("聊天响应未完成"));
      }
    } catch (e) {
      onError(e as Error);
    }
  },

  /** Agent 编排：SSE 流式工具调用 */
  async streamAgent(
    params: {
      session_id: string;
      goal?: string;
      jd_text?: string;
      knowledge_base?: string;
      client_id?: string;
      auto_finalize?: boolean;
      use_multi_agent?: boolean;
      confirmed?: boolean;
      confirmed_action?: { action: string; action_input?: Record<string, unknown> };
    },
    onEvent: (event: AgentStreamEvent) => void,
    onError: (err: Error) => void
  ) {
    try {
      const res = await fetch(`${API_BASE}/api/agent/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(params),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Agent 启动失败 (${res.status})`);
      }
      if (!res.body) throw new Error("无响应流");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let gotDone = false;

      const handleEvent = (raw: string) => {
        const line = raw
          .split("\n")
          .map((l) => l.trimEnd())
          .find((l) => l.startsWith("data:"));
        if (!line) return;
        const jsonText = line.slice(5).trimStart();
        if (!jsonText) return;
        const payload = JSON.parse(jsonText) as AgentStreamEvent;
        onEvent(payload);
        if (payload.type === "done" || payload.type === "confirmation_required") gotDone = true;
        if (payload.type === "error") onError(new Error(payload.message || "Agent 失败"));
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        buffer = buffer.replace(/\r\n/g, "\n");
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";
        for (const eventBlock of events) {
          try {
            handleEvent(eventBlock);
          } catch (err) {
            console.error("Agent SSE parse error:", err, eventBlock);
          }
        }
      }
      if (buffer.trim()) {
        try {
          handleEvent(buffer);
        } catch (err) {
          console.error("Agent SSE tail error:", err, buffer);
        }
      }
      if (!gotDone && !params.confirmed_action) onError(new Error("Agent 响应未完成"));
    } catch (e) {
      onError(e as Error);
    }
  },

  /** 编辑页 Agent 对话（工具 + 确认 + 改稿） */
  async streamEditChatAgent(
    params: {
      session_id: string;
      message: string;
      client_id?: string;
      ui_context?: Record<string, unknown>;
      confirmed_action?: { action: string; action_input?: Record<string, unknown> };
    },
    onEvent: (event: EditChatEvent) => void,
    onError: (err: Error) => void
  ) {
    try {
      const res = await fetch(`${API_BASE}/api/chat/agent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(params),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Agent 对话失败 (${res.status})`);
      }
      if (!res.body) throw new Error("无响应流");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let gotTerminal = false;

      const handleEvent = (raw: string) => {
        const line = raw
          .split("\n")
          .map((l) => l.trimEnd())
          .find((l) => l.startsWith("data:"));
        if (!line) return;
        const payload = JSON.parse(line.slice(5).trimStart()) as EditChatEvent;
        onEvent(payload);
        if (payload.type === "done" || payload.type === "confirmation_required") {
          gotTerminal = true;
        }
        if (payload.type === "error") onError(new Error(payload.message || "失败"));
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";
        for (const block of events) {
          try {
            handleEvent(block);
          } catch (err) {
            console.error("Edit agent SSE error:", err);
          }
        }
      }
      if (buffer.trim()) {
        try {
          handleEvent(buffer);
        } catch {
          /* ignore */
        }
      }
      if (!gotTerminal && !params.confirmed_action) {
        onError(new Error("Agent 对话未完成"));
      }
    } catch (e) {
      onError(e as Error);
    }
  },
};

export type EditChatEvent =
  | { type: "text"; content: string }
  | { type: "reply_end" }
  | { type: "thought"; content: string; agent?: string }
  | { type: "tool_call"; action: string; input?: Record<string, unknown>; agent?: string }
  | { type: "tool_result"; action: string; result?: Record<string, unknown>; agent?: string }
  | {
      type: "confirmation_required";
      action: string;
      input?: Record<string, unknown>;
      message: string;
      agent?: string;
    }
  | { type: "export_ready"; filename?: string }
  | { type: "customization_update"; updates?: Record<string, unknown>; agent?: string }
  | {
      type: "done";
      reply?: string;
      new_suggestions?: Suggestion[];
      ui_patch?: {
        filter?: "all" | "pending" | "accepted" | "rejected";
        highlight_ids?: string[];
        focus_panel?: string;
      };
      session?: {
        current_resume_md: string;
        finalized_resume_md: string;
        finalize_status: "draft" | "finalized" | "stale";
        suggestions: Suggestion[];
        match: MatchResult | null;
        density?: { char_count: number; status: string; message: string };
      };
    }
  | { type: "error"; message?: string };

export type MockInterviewEvent =
  | { type: "text"; content?: string }
  | {
      type: "done";
      reply?: string;
      question?: string;
      turn?: number;
      score?: number | null;
      feedback?: string;
    }
  | { type: "error"; message?: string };

export type AgentStreamEvent =
  | { type: "agent_phase"; agent: string; content: string }
  | { type: "thought"; content: string; step?: number; agent?: string }
  | { type: "tool_call"; action: string; input?: Record<string, unknown>; step?: number; agent?: string }
  | { type: "tool_result"; action: string; result?: Record<string, unknown>; step?: number; agent?: string }
  | {
      type: "confirmation_required";
      action: string;
      input?: Record<string, unknown>;
      message: string;
      agent?: string;
    }
  | { type: "customization_update"; updates?: Record<string, unknown>; agent?: string }
  | {
      type: "done";
      summary: string;
      session?: {
        current_resume_md: string;
        finalized_resume_md: string;
        finalize_status: "draft" | "finalized" | "stale";
        suggestions: Suggestion[];
        match: MatchResult | null;
        jd_analysis: JDAnalysis | null;
        density?: { char_count: number; status: string; message: string };
      };
    }
  | { type: "error"; message?: string };
