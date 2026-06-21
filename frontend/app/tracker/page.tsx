"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { getClientId } from "@/lib/userMemory";
import { ROUTES } from "@/lib/navigation";
import { useAppStore } from "@/stores/useAppStore";
import type { ApplicationRecord, ApplicationStats, Reminder } from "@/lib/types";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { Briefcase, LayoutGrid, List, MessageSquare, Plus, Trash2 } from "lucide-react";

const KANBAN_COLUMNS = ["Evaluated", "Applied", "WrittenTest", "Interview", "Offer", "Rejected"];

const STATUS_LABELS: Record<string, string> = {
  Evaluated: "已评估",
  Applied: "已投递",
  WrittenTest: "笔试",
  Interview: "面试",
  Offer: "Offer",
  Rejected: "拒信",
  Discarded: "放弃",
  SKIP: "跳过",
};

export default function TrackerPage() {
  const router = useRouter();
  const setSessionId = useAppStore((s) => s.setSessionId);
  const [apps, setApps] = useState<ApplicationRecord[]>([]);
  const [stats, setStats] = useState<ApplicationStats | null>(null);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [view, setView] = useState<"kanban" | "table">("kanban");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    company: "",
    role: "",
    channel: "官网",
    notes: "",
    deadline: "",
  });

  async function load() {
    const cid = getClientId();
    const [res, rem] = await Promise.all([api.getApplications(cid), api.getReminders(cid)]);
    if (res.success && res.data) {
      setApps(res.data.applications);
      setStats(res.data.stats);
    }
    if (rem.success && rem.data) setReminders(rem.data.reminders);
  }

  useEffect(() => {
    load();
  }, []);

  async function addApp() {
    if (!form.company.trim() || !form.role.trim()) return;
    await api.createApplication({
      client_id: getClientId(),
      ...form,
      status: "Evaluated",
    });
    setForm({ company: "", role: "", channel: "官网", notes: "", deadline: "" });
    setShowForm(false);
    load();
  }

  async function changeStatus(appId: string, status: string) {
    await api.updateApplicationStatus(getClientId(), appId, status);
    load();
  }

  async function removeApp(app: ApplicationRecord) {
    const label = `${app.company} · ${app.role}`;
    if (!window.confirm(`确定删除投递记录「${label}」？此操作不可撤销。`)) return;
    const res = await api.deleteApplication(getClientId(), app.id);
    if (res.success) load();
  }

  const funnelData = stats
    ? [
        { name: "投递", value: stats.applied_count },
        { name: "笔试", value: Math.round((stats.written_test_rate || 0) * stats.applied_count) },
        { name: "面试", value: stats.interview_count },
        { name: "Offer", value: stats.offer_count },
      ]
    : [];

  function continueEdit(app: ApplicationRecord, e: React.MouseEvent) {
    e.preventDefault();
    if (app.session_id) {
      setSessionId(app.session_id);
      router.push(ROUTES.studioEdit);
    } else {
      router.push(ROUTES.studioPrepare);
    }
  }

  return (
    <main className="max-w-6xl mx-auto px-6 py-8">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Briefcase /> 投递追踪
          </h1>
          <div className="flex flex-wrap gap-2 items-center">
            <Link href="/jobs" className="text-sm text-blue-600 hover:underline">
              岗位发现
            </Link>
            <Link href="/insights" className="text-sm text-blue-600 hover:underline">
              求职洞察
            </Link>
            <div className="flex border rounded-lg overflow-hidden text-sm">
              <button
                type="button"
                onClick={() => setView("kanban")}
                className={`px-3 py-1.5 flex items-center gap-1 ${view === "kanban" ? "bg-blue-600 text-white" : ""}`}
              >
                <LayoutGrid size={14} /> 看板
              </button>
              <button
                type="button"
                onClick={() => setView("table")}
                className={`px-3 py-1.5 flex items-center gap-1 ${view === "table" ? "bg-blue-600 text-white" : ""}`}
              >
                <List size={14} /> 表格
              </button>
            </div>
            <button
              type="button"
              onClick={() => setShowForm(!showForm)}
              className="inline-flex items-center gap-1 px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm"
            >
              <Plus size={14} /> 记录
            </button>
          </div>
        </div>

        {reminders.length > 0 && (
          <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-xl text-sm">
            {reminders.slice(0, 3).map((r, i) => (
              <div key={i}>
                <span className="font-medium">{r.company}</span> — {r.message}
              </div>
            ))}
          </div>
        )}

        {stats && (
          <div className="grid md:grid-cols-2 gap-4 mb-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <StatCard label="总岗位" value={stats.total} />
              <StatCard label="已投递" value={stats.applied_count} />
              <StatCard label="面试/Offer" value={stats.interview_count} />
              <StatCard label="Offer" value={stats.offer_count} />
            </div>
            <div className="bg-white border rounded-xl p-4 h-36">
              <div className="text-xs text-slate-500 mb-2">转化漏斗</div>
              <ResponsiveContainer width="100%" height="85%">
                <BarChart data={funnelData}>
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {showForm && (
          <div className="mb-6 p-4 bg-white border rounded-xl grid md:grid-cols-3 gap-3">
            <input
              className="border rounded-lg px-3 py-2 text-sm"
              placeholder="公司"
              value={form.company}
              onChange={(e) => setForm({ ...form, company: e.target.value })}
            />
            <input
              className="border rounded-lg px-3 py-2 text-sm"
              placeholder="岗位"
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })}
            />
            <input
              className="border rounded-lg px-3 py-2 text-sm"
              placeholder="截止日 YYYY-MM-DD"
              value={form.deadline}
              onChange={(e) => setForm({ ...form, deadline: e.target.value })}
            />
            <button
              type="button"
              onClick={addApp}
              className="md:col-span-3 py-2 bg-blue-600 text-white rounded-lg text-sm"
            >
              保存
            </button>
          </div>
        )}

        {view === "kanban" ? (
          <div className="flex gap-3 overflow-x-auto pb-4">
            {KANBAN_COLUMNS.map((col) => (
              <div key={col} className="min-w-[200px] flex-1 bg-slate-100 rounded-xl p-2">
                <div className="text-xs font-semibold text-slate-600 px-2 py-1 mb-2">
                  {STATUS_LABELS[col] || col}
                </div>
                <div className="space-y-2 min-h-[120px]">
                  {apps
                    .filter((a) => a.status === col)
                    .map((a) => (
                      <div key={a.id} className="bg-white border rounded-lg p-3 text-sm shadow-sm">
                        <div className="font-medium">{a.company}</div>
                        <div className="text-xs text-slate-500">{a.role}</div>
                        {a.match_score > 0 && (
                          <div className="text-xs text-blue-600 mt-1">匹配 {a.match_score}</div>
                        )}
                        <div className="flex gap-1 mt-2 flex-wrap">
                          <Link
                            href={`/interview/${a.id}`}
                            className="text-xs text-violet-600 flex items-center gap-0.5"
                          >
                            <MessageSquare size={10} /> 面试准备
                          </Link>
                          <button
                            type="button"
                            onClick={(e) => continueEdit(a, e)}
                            className="text-xs text-blue-600"
                          >
                            继续改稿
                          </button>
                          <button
                            type="button"
                            onClick={() => removeApp(a)}
                            className="text-xs text-red-600 flex items-center gap-0.5"
                          >
                            <Trash2 size={10} /> 删除
                          </button>
                        </div>
                        <select
                          className="mt-2 w-full border rounded text-xs py-1"
                          value={a.status}
                          onChange={(e) => changeStatus(a.id, e.target.value)}
                        >
                          {KANBAN_COLUMNS.map((s) => (
                            <option key={s} value={s}>
                              {STATUS_LABELS[s]}
                            </option>
                          ))}
                        </select>
                      </div>
                    ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="bg-white border rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="text-left p-3">公司</th>
                  <th className="text-left p-3">岗位</th>
                  <th className="text-left p-3">状态</th>
                  <th className="text-left p-3">匹配分</th>
                  <th className="text-left p-3">操作</th>
                </tr>
              </thead>
              <tbody>
                {apps.map((a) => (
                  <tr key={a.id} className="border-t">
                    <td className="p-3 font-medium">{a.company}</td>
                    <td className="p-3">{a.role}</td>
                    <td className="p-3">
                      <select
                        className="border rounded px-2 py-1 text-xs"
                        value={a.status}
                        onChange={(e) => changeStatus(a.id, e.target.value)}
                      >
                        {Object.keys(STATUS_LABELS).map((s) => (
                          <option key={s} value={s}>
                            {STATUS_LABELS[s]}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="p-3">{a.match_score || "—"}</td>
                    <td className="p-3">
                      <div className="flex gap-2">
                        <Link href={`/interview/${a.id}`} className="text-blue-600 text-xs">
                          面试准备
                        </Link>
                        <button
                          type="button"
                          onClick={(e) => continueEdit(a, e)}
                          className="text-blue-600 text-xs"
                        >
                          继续改稿
                        </button>
                        <button
                          type="button"
                          onClick={() => removeApp(a)}
                          className="text-red-600 text-xs inline-flex items-center gap-0.5"
                        >
                          <Trash2 size={12} /> 删除
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="p-4 bg-white border rounded-xl">
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs text-slate-500 mt-1">{label}</div>
    </div>
  );
}
