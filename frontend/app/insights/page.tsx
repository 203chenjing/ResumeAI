"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { getClientId } from "@/lib/userMemory";
import type { PatternInsights, Reminder, UserProfile } from "@/lib/types";
import { BarChart3, Bell, User } from "lucide-react";
import { ROUTES } from "@/lib/navigation";
import { copy } from "@/lib/copy";

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
    <main className="page-shell space-y-6">
      <h1 className="page-title">{copy.insights.title}</h1>

      <section className="surface-card p-5">
        <h2 className="font-semibold flex items-center gap-2 mb-4 text-[var(--text-primary)]">
          <User size={18} /> {copy.insights.profile}
        </h2>
        {profile && (
          <div className="grid md:grid-cols-2 gap-3 text-sm">
            <input
              className="input-field"
              placeholder={copy.insights.fields.name}
              value={profile.display_name}
              onChange={(e) => setProfile({ ...profile, display_name: e.target.value })}
            />
            <input
              className="input-field"
              placeholder={copy.insights.fields.school}
              value={profile.school}
              onChange={(e) => setProfile({ ...profile, school: e.target.value })}
            />
            <input
              className="input-field"
              placeholder={copy.insights.fields.major}
              value={profile.major}
              onChange={(e) => setProfile({ ...profile, major: e.target.value })}
            />
            <input
              className="input-field"
              type="number"
              placeholder={copy.insights.fields.weeklyLimit}
              value={profile.weekly_apply_limit}
              onChange={(e) =>
                setProfile({ ...profile, weekly_apply_limit: Number(e.target.value) })
              }
            />
            <input
              className="input-field"
              type="number"
              placeholder={copy.insights.fields.minMatch}
              value={profile.min_match_score}
              onChange={(e) =>
                setProfile({ ...profile, min_match_score: Number(e.target.value) })
              }
            />
            <button
              type="button"
              onClick={saveProfile}
              disabled={saving}
              className="md:col-span-2 btn-primary justify-center py-2.5"
            >
              {saving ? copy.insights.saving : copy.insights.saveProfile}
            </button>
          </div>
        )}
      </section>

      <section className="surface-card p-5">
        <h2 className="font-semibold flex items-center gap-2 mb-4 text-[var(--text-primary)]">
          <Bell size={18} /> {copy.insights.reminders}
        </h2>
        {reminders.length === 0 ? (
          <p className="text-sm text-[var(--text-secondary)]">{copy.insights.noReminders}</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {reminders.map((r, i) => (
              <li
                key={i}
                className={`p-3 rounded-lg border ${
                  r.urgency === "high"
                    ? "border-red-200 bg-red-50"
                    : "border-[var(--border-subtle)] bg-[var(--surface-base)]"
                }`}
              >
                <span className="font-medium text-[var(--text-primary)]">{r.company}</span>
                <span className="text-[var(--text-secondary)]"> · {r.role} — {r.message}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="surface-card p-5">
        <h2 className="font-semibold flex items-center gap-2 mb-4 text-[var(--text-primary)]">
          <BarChart3 size={18} /> {copy.insights.patterns}
        </h2>
        {patterns && (
          <>
            <p className="text-sm text-[var(--text-secondary)] mb-3">
              {copy.insights.rejectionRate((patterns.rejection_rate * 100).toFixed(0), patterns.total)}
            </p>
            <ul className="text-sm space-y-1 mb-4 text-[var(--text-primary)]">
              {patterns.insights.map((t) => (
                <li key={t} className="text-[var(--text-secondary)]">· {t}</li>
              ))}
            </ul>
            <div className="p-3 bg-[var(--primary-muted)] rounded-lg text-sm">
              <div className="font-medium mb-1 text-[var(--text-primary)]">{copy.insights.strategy}</div>
              {patterns.recommendations.map((t) => (
                <div key={t} className="text-[var(--text-secondary)]">→ {t}</div>
              ))}
            </div>
            <Link href={ROUTES.tracker} className="inline-block mt-4 text-link">
              {copy.insights.viewTracker} →
            </Link>
          </>
        )}
      </section>
    </main>
  );
}
