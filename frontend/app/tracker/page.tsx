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
import { copy } from "@/lib/copy";

const KANBAN_COLUMNS = ["Evaluated", "Applied", "WrittenTest", "Interview", "Offer", "Rejected"];

const STATUS_LABELS: Record<string, string> = copy.tracker.status as Record<string, string>;

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
    if (!window.confirm(copy.tracker.deleteConfirm(label))) return;
    const res = await api.deleteApplication(getClientId(), app.id);
    if (res.success) load();
  }

  const funnelData = stats
    ? [
        { name: copy.tracker.funnelSteps.applied, value: stats.applied_count },
        { name: copy.tracker.funnelSteps.written, value: Math.round((stats.written_test_rate || 0) * stats.applied_count) },
        { name: copy.tracker.funnelSteps.interview, value: stats.interview_count },
        { name: copy.tracker.funnelSteps.offer, value: stats.offer_count },
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
    <main className="page-shell">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
          <h1 className="page-title flex items-center gap-2">
            <Briefcase size={22} className="text-[var(--primary)]" /> {copy.tracker.title}
          </h1>
          <div className="flex flex-wrap gap-2 items-center">
            <Link href={ROUTES.jobs} className="text-link">
              {copy.tracker.jobsLink}
            </Link>
            <Link href={ROUTES.insights} className="text-link">
              {copy.tracker.insightsLink}
            </Link>
            <div className="flex border border-[var(--border-subtle)] rounded-lg overflow-hidden text-sm">
              <button
                type="button"
                onClick={() => setView("kanban")}
                className={`px-3 py-1.5 flex items-center gap-1 ${view === "kanban" ? "bg-[var(--primary)] text-white" : "text-[var(--text-secondary)]"}`}
              >
                <LayoutGrid size={14} /> {copy.tracker.viewKanban}
              </button>
              <button
                type="button"
                onClick={() => setView("table")}
                className={`px-3 py-1.5 flex items-center gap-1 ${view === "table" ? "bg-[var(--primary)] text-white" : "text-[var(--text-secondary)]"}`}
              >
                <List size={14} /> {copy.tracker.viewTable}
              </button>
            </div>
            <button
              type="button"
              onClick={() => setShowForm(!showForm)}
              className="btn-primary px-3 py-1.5"
            >
              <Plus size={14} /> {copy.tracker.addRecord}
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
              <StatCard label={copy.tracker.stats.total} value={stats.total} />
              <StatCard label={copy.tracker.stats.applied} value={stats.applied_count} />
              <StatCard label={copy.tracker.stats.interview} value={stats.interview_count} />
              <StatCard label={copy.tracker.stats.offer} value={stats.offer_count} />
            </div>
            <div className="surface-card p-4 h-36">
              <div className="text-xs text-[var(--text-secondary)] mb-2">{copy.tracker.funnel}</div>
              <ResponsiveContainer width="100%" height="85%">
                <BarChart data={funnelData}>
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Bar dataKey="value" fill="var(--primary)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {showForm && (
          <div className="mb-6 surface-card p-4 grid md:grid-cols-3 gap-3">
            <input
              className="input-field"
              placeholder={copy.tracker.form.company}
              value={form.company}
              onChange={(e) => setForm({ ...form, company: e.target.value })}
            />
            <input
              className="input-field"
              placeholder={copy.tracker.form.role}
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })}
            />
            <input
              className="input-field"
              placeholder={copy.tracker.form.deadline}
              value={form.deadline}
              onChange={(e) => setForm({ ...form, deadline: e.target.value })}
            />
            <button type="button" onClick={addApp} className="md:col-span-3 btn-primary justify-center py-2">
              {copy.tracker.form.save}
            </button>
          </div>
        )}

        {view === "kanban" ? (
          <div className="flex gap-3 overflow-x-auto pb-4">
            {KANBAN_COLUMNS.map((col) => (
              <div key={col} className="min-w-[200px] flex-1 bg-[var(--surface-base)] rounded-xl p-2">
                <div className="text-xs font-semibold text-[var(--text-secondary)] px-2 py-1 mb-2">
                  {STATUS_LABELS[col] || col}
                </div>
                <div className="space-y-2 min-h-[120px]">
                  {apps
                    .filter((a) => a.status === col)
                    .map((a) => (
                      <div key={a.id} className="surface-card p-3 text-sm shadow-sm">
                        <div className="font-medium text-[var(--text-primary)]">{a.company}</div>
                        <div className="text-xs text-[var(--text-secondary)]">{a.role}</div>
                        {a.match_score > 0 && (
                          <div className="text-xs text-[var(--primary)] mt-1">
                            {copy.tracker.match(a.match_score)}
                          </div>
                        )}
                        <div className="flex gap-1 mt-2 flex-wrap">
                          <Link
                            href={`/interview/${a.id}`}
                            className="text-xs text-link flex items-center gap-0.5"
                          >
                            <MessageSquare size={10} /> {copy.tracker.interviewPrep}
                          </Link>
                          <button
                            type="button"
                            onClick={(e) => continueEdit(a, e)}
                            className="text-xs text-link"
                          >
                            {copy.tracker.continueEdit}
                          </button>
                          <button
                            type="button"
                            onClick={() => removeApp(a)}
                            className="text-xs text-[var(--semantic-danger)] flex items-center gap-0.5"
                          >
                            <Trash2 size={10} /> {copy.common.delete}
                          </button>
                        </div>
                        <select
                          className="mt-2 w-full input-field text-xs py-1"
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
          <div className="surface-card overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-[var(--surface-base)] text-[var(--text-secondary)]">
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
                        <Link href={`/interview/${a.id}`} className="text-link text-xs">
                          {copy.tracker.interviewPrep}
                        </Link>
                        <button
                          type="button"
                          onClick={(e) => continueEdit(a, e)}
                          className="text-link text-xs"
                        >
                          {copy.tracker.continueEdit}
                        </button>
                        <button
                          type="button"
                          onClick={() => removeApp(a)}
                          className="text-[var(--semantic-danger)] text-xs inline-flex items-center gap-0.5"
                        >
                          <Trash2 size={12} /> {copy.common.delete}
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
    <div className="p-4 surface-card">
      <div className="text-2xl font-semibold text-[var(--text-primary)]">{value}</div>
      <div className="text-xs text-[var(--text-secondary)] mt-1">{label}</div>
    </div>
  );
}
