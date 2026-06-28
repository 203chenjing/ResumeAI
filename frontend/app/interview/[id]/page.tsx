"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import Header from "@/components/layout/Header";
import { api } from "@/lib/api";
import { getClientId } from "@/lib/userMemory";
import type { InterviewPrepPack } from "@/lib/types";
import { BookOpen, Loader2, MessageSquare } from "lucide-react";
import ChatInput from "@/components/ui/ChatInput";
import { copy } from "@/lib/copy";
import { ROUTES } from "@/lib/navigation";

const ROUNDS = [
  { id: "hr", label: "HR 面" },
  { id: "technical", label: "技术面" },
  { id: "group", label: "群面" },
];

export default function InterviewPage() {
  const params = useParams();
  const appId = typeof params.id === "string" ? params.id : "";
  const [pack, setPack] = useState<InterviewPrepPack | null>(null);
  const [round, setRound] = useState("hr");
  const [answer, setAnswer] = useState("");
  const [turn, setTurn] = useState(0);
  const [question, setQuestion] = useState("");
  const [feedback, setFeedback] = useState("");
  const [score, setScore] = useState<number | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [chatLog, setChatLog] = useState<{ role: string; content: string }[]>([]);

  useEffect(() => {
    api.getInterviewPrep(getClientId(), appId).then((res) => {
      if (res.success && res.data) setPack(res.data);
    });
  }, [appId]);

  function startMock() {
    setStreaming(true);
    setChatLog([]);
    setFeedback("");
    setScore(null);
    api.streamMockInterview(
      { client_id: getClientId(), application_id: appId, round_type: round, turn: 0, user_answer: "" },
      (ev) => {
        if (ev.type === "done") {
          setQuestion(ev.question || "");
          setTurn(ev.turn || 0);
          if (ev.reply) setChatLog([{ role: "assistant", content: ev.reply }]);
          setStreaming(false);
        }
      },
      () => setStreaming(false)
    );
  }

  function submitAnswer() {
    const msg = answer.trim();
    if (!msg) return;
    if (msg.length < 20) {
      setChatLog((l) => [
        ...l,
        { role: "user", content: msg },
        {
          role: "assistant",
          content:
            "回答过短，无法评估。请用 STAR 结构写至少 20 字：情境、任务、行动、结果（尽量含量化指标）。",
        },
      ]);
      setAnswer("");
      return;
    }
    setChatLog((l) => [...l, { role: "user", content: msg }]);
    setStreaming(true);
    setAnswer("");
    api.streamMockInterview(
      {
        client_id: getClientId(),
        application_id: appId,
        round_type: round,
        turn,
        user_answer: msg,
      },
      (ev) => {
        if (ev.type === "text" && ev.content) setFeedback(ev.content);
        if (ev.type === "done") {
          setQuestion(ev.question || "");
          setTurn(ev.turn || turn + 1);
          setScore(ev.score ?? null);
          if (ev.feedback) setChatLog((l) => [...l, { role: "assistant", content: ev.feedback! }]);
          setStreaming(false);
        }
      },
      () => setStreaming(false)
    );
  }

  return (
    <>
      <Header />
      <main className="max-w-6xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <MessageSquare /> 面试准备
            {pack && (
              <span className="text-base font-normal text-[var(--text-secondary)]">
                {pack.company} · {pack.role}
              </span>
            )}
          </h1>
          <Link href="/tracker" className="text-link">
            返回追踪器
          </Link>
        </div>

        {!pack ? (
          <Loader2 className="animate-spin mx-auto text-[var(--text-disabled)]" />
        ) : (
          <div className="grid lg:grid-cols-2 gap-6">
            <section className="space-y-4">
              <div className="surface-card p-4">
                <h2 className="font-semibold flex items-center gap-2 mb-3">
                  <BookOpen size={16} /> 相关 STAR 故事
                </h2>
                <ul className="space-y-2 text-sm">
                  {pack.stories.map((s) => (
                    <li key={s.id} className="p-2 bg-[var(--surface-base)] rounded border">
                      <div className="font-medium">{s.title}</div>
                      <div className="text-xs text-[var(--text-secondary)] mt-1">
                        相关度 {Math.round(s.relevance * 100)}%
                      </div>
                    </li>
                  ))}
                </ul>
              </div>

              {(["hr", "technical", "group"] as const).map((cat) => (
                <div key={cat} className="surface-card p-4">
                  <h3 className="text-sm font-semibold mb-2 capitalize">{cat} 题库</h3>
                  <ul className="text-sm space-y-2">
                    {(pack.questions[cat] || []).slice(0, 3).map((q) => (
                      <li key={q.question} className="text-[var(--text-primary)]">
                        <span
                          className={`text-xs px-1 rounded mr-1 ${
                            q.story_fit === "strong"
                              ? "bg-green-100 text-green-700"
                              : q.story_fit === "partial"
                                ? "bg-amber-100 text-amber-700"
                                : "bg-[var(--surface-base)]"
                          }`}
                        >
                          {q.story_fit}
                        </span>
                        {q.question}
                        <div className="text-xs text-[var(--text-disabled)] mt-0.5">{q.tips}</div>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </section>

            <section className="surface-card p-4 flex flex-col min-h-[480px]">
              <h2 className="font-semibold mb-3">模拟面试</h2>
              <div className="flex gap-2 mb-3">
                {ROUNDS.map((r) => (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() => setRound(r.id)}
                    className={`px-3 py-1 text-xs rounded-full border ${
                      round === r.id ? "bg-[var(--primary)] text-white border-[var(--primary)]" : ""
                    }`}
                  >
                    {r.label}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={startMock}
                  disabled={streaming}
                  className="ml-auto text-xs px-3 py-1 bg-[var(--primary)] text-white rounded-full"
                >
                  开始
                </button>
              </div>

              <div className="flex-1 overflow-y-auto space-y-2 mb-3 text-sm bg-[var(--surface-base)] rounded-lg p-3">
                {chatLog.length === 0 && (
                  <p className="text-[var(--text-disabled)] text-xs">点击「开始」进入模拟面试</p>
                )}
                {chatLog.map((m, i) => (
                  <div
                    key={i}
                    className={`p-2 rounded-[var(--radius-sm)] ${
                      m.role === "user"
                        ? "bg-[var(--primary-muted)] text-[var(--text-primary)] ml-8"
                        : "bg-[var(--surface-base)] text-[var(--text-secondary)] mr-8"
                    }`}
                  >
                    {m.content}
                  </div>
                ))}
                {streaming && <Loader2 size={14} className="animate-spin text-[var(--text-disabled)]" />}
              </div>

              {score !== null && (
                <div className="text-xs text-[var(--semantic-success)] mb-2">STAR 评分：{score}/100</div>
              )}

              <ChatInput
                value={answer}
                onChange={setAnswer}
                onSend={submitAnswer}
                placeholder={question || "输入你的回答…"}
                streaming={streaming}
              />
            </section>
          </div>
        )}
      </main>
    </>
  );
}
