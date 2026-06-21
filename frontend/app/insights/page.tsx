"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { getClientId } from "@/lib/userMemory";
import type { PatternInsights, Reminder, UserProfile } from "@/lib/types";
import { BarChart3, Bell, User } from "lucide-react";

export default function InsightsPage() {
  const [patterns, setPatterns] = useState<PatternInsights | null>(null);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [saving, setSaving] = useState(false);

  const cid = getClientId();

  async function load() {
    const [p, r, u] = await Promise.all([
      api.getPatternInsights(cid),
      api.getReminders(cid),
      api.getUserProfile(cid),
    ]);
    if (p.success && p.data) setPatterns(p.data);
    if (r.success && r.data) setReminders(r.data.reminders);
    if (u.success && u.data) setProfile(u.data);
  }

  useEffect(() => {
    load();
  }, []);

  async function saveProfile() {
    if (!profile) return;
    setSaving(true);
    await api.saveUserProfile({ ...profile, client_id: cid });
    setSaving(false);
  }

  return (
    <main className="max-w-5xl mx-auto px-6 py-8 space-y-8">
        <h1 className="text-2xl font-bold">求职洞察</h1>

        <section className="bg-white border rounded-xl p-5">
          <h2 className="font-semibold flex items-center gap-2 mb-4">
            <User size={18} /> 用户档案
          </h2>
          {profile && (
            <div className="grid md:grid-cols-2 gap-3 text-sm">
              <input
                className="border rounded-lg px-3 py-2"
                placeholder="姓名"
                value={profile.display_name}
                onChange={(e) => setProfile({ ...profile, display_name: e.target.value })}
              />
              <input
                className="border rounded-lg px-3 py-2"
                placeholder="学校"
                value={profile.school}
                onChange={(e) => setProfile({ ...profile, school: e.target.value })}
              />
              <input
                className="border rounded-lg px-3 py-2"
                placeholder="专业"
                value={profile.major}
                onChange={(e) => setProfile({ ...profile, major: e.target.value })}
              />
              <input
                className="border rounded-lg px-3 py-2"
                type="number"
                placeholder="周投递上限"
                value={profile.weekly_apply_limit}
                onChange={(e) =>
                  setProfile({ ...profile, weekly_apply_limit: Number(e.target.value) })
                }
              />
              <input
                className="border rounded-lg px-3 py-2"
                type="number"
                placeholder="最低匹配分门槛"
                value={profile.min_match_score}
                onChange={(e) =>
                  setProfile({ ...profile, min_match_score: Number(e.target.value) })
                }
              />
              <button
                type="button"
                onClick={saveProfile}
                disabled={saving}
                className="md:col-span-2 py-2 bg-blue-600 text-white rounded-lg"
              >
                {saving ? "保存中…" : "保存档案"}
              </button>
            </div>
          )}
        </section>

        <section className="bg-white border rounded-xl p-5">
          <h2 className="font-semibold flex items-center gap-2 mb-4">
            <Bell size={18} /> 跟进提醒
          </h2>
          {reminders.length === 0 ? (
            <p className="text-sm text-slate-500">暂无待办提醒</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {reminders.map((r, i) => (
                <li
                  key={i}
                  className={`p-3 rounded-lg border ${
                    r.urgency === "high" ? "border-red-200 bg-red-50" : "border-slate-100"
                  }`}
                >
                  <span className="font-medium">{r.company}</span> · {r.role} — {r.message}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="bg-white border rounded-xl p-5">
          <h2 className="font-semibold flex items-center gap-2 mb-4">
            <BarChart3 size={18} /> 拒信模式分析
          </h2>
          {patterns && (
            <>
              <p className="text-sm text-slate-600 mb-3">
                拒信率 {(patterns.rejection_rate * 100).toFixed(0)}% · 共 {patterns.total} 条记录
              </p>
              <ul className="text-sm space-y-1 mb-4">
                {patterns.insights.map((t) => (
                  <li key={t}>· {t}</li>
                ))}
              </ul>
              <div className="p-3 bg-blue-50 rounded-lg text-sm">
                <div className="font-medium mb-1">策略建议</div>
                {patterns.recommendations.map((t) => (
                  <div key={t}>→ {t}</div>
                ))}
              </div>
              <Link href="/tracker" className="inline-block mt-4 text-sm text-blue-600 hover:underline">
                查看投递追踪 →
              </Link>
            </>
          )}
        </section>
      </main>
  );
}
