"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { getClientId } from "@/lib/userMemory";
import type { JobPreferences } from "@/lib/types";
import { ChevronDown, ChevronUp, Loader2, Save } from "lucide-react";
import { copy } from "@/lib/copy";

function joinList(arr: string[]) {
  return (arr || []).join("，");
}

function splitList(text: string) {
  return text
    .split(/[,，、]/)
    .map((s) => s.trim())
    .filter(Boolean);
}

const EMPTY: JobPreferences = {
  target_roles: [],
  target_cities: [],
  job_types: ["实习", "校招"],
  target_cohort: "27届",
  include_unknown_cohort: true,
  company_wishlist: [],
  company_blocklist: [],
  extra_notes: "",
};

export default function JobPreferencesPanel({ onSaved }: { onSaved?: () => void }) {
  const [open, setOpen] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [roles, setRoles] = useState("");
  const [cities, setCities] = useState("");
  const [types, setTypes] = useState("实习，校招");
  const [cohort, setCohort] = useState("27届");
  const [includeUnknown, setIncludeUnknown] = useState(true);
  const [wishlist, setWishlist] = useState("");
  const [blocklist, setBlocklist] = useState("");
  const [notes, setNotes] = useState("");

  useEffect(() => {
    let cancelled = false;
    setSyncing(true);
    api
      .getJobPreferences(getClientId())
      .then((res) => {
        if (cancelled || !res.success || !res.data) return;
        const p = res.data;
        setRoles(joinList(p.target_roles));
        setCities(joinList(p.target_cities));
        setTypes(joinList(p.job_types) || "实习，校招");
        setCohort(p.target_cohort || "27届");
        setIncludeUnknown(p.include_unknown_cohort !== false);
        setWishlist(joinList(p.company_wishlist));
        setBlocklist(joinList(p.company_blocklist));
        setNotes(p.extra_notes || "");
      })
      .catch(() => {
        /* 后端未启动或网络异常：保留默认空表单即可 */
      })
      .finally(() => {
        if (!cancelled) setSyncing(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function save() {
    setSaving(true);
    try {
      const prefs: JobPreferences = {
        target_roles: splitList(roles),
        target_cities: splitList(cities),
        job_types: splitList(types),
        target_cohort: cohort.trim() || "27届",
        include_unknown_cohort: includeUnknown,
        company_wishlist: splitList(wishlist),
        company_blocklist: splitList(blocklist),
        extra_notes: notes.trim(),
      };
      await api.saveJobPreferences(getClientId(), prefs);
      onSaved?.();
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="mb-4 surface-card overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--surface-base)]"
      >
        <span className="flex items-center gap-2">
          {copy.jobs.preferences}
          {syncing && <Loader2 className="animate-spin text-[var(--text-disabled)]" size={14} />}
        </span>
        {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>
      {open && (
        <div className="px-4 pb-4 border-t pt-3">
          <p className="text-xs text-[var(--text-secondary)] mb-3">
            {copy.jobs.preferencesHint}
          </p>
          <div className="grid md:grid-cols-2 gap-3 text-sm">
            <label className="block">
              <span className="text-[var(--text-secondary)] text-xs">目标岗位（逗号分隔）</span>
              <input
                className="mt-1 w-full input-field"
                placeholder="AI产品实习生，产品经理"
                value={roles}
                onChange={(e) => setRoles(e.target.value)}
              />
            </label>
            <label className="block">
              <span className="text-[var(--text-secondary)] text-xs">目标城市</span>
              <input
                className="mt-1 w-full input-field"
                placeholder="上海，北京"
                value={cities}
                onChange={(e) => setCities(e.target.value)}
              />
            </label>
            <label className="block">
              <span className="text-[var(--text-secondary)] text-xs">目标届别</span>
              <select className="mt-1 w-full input-field" value={cohort} onChange={(e) => setCohort(e.target.value)}>
                <option value="27届">27届（2027 毕业）</option>
                <option value="26届">26届</option>
                <option value="25届">25届</option>
                <option value="">不限</option>
              </select>
            </label>
            <label className="block flex items-end gap-2 pb-1">
              <input type="checkbox" checked={includeUnknown} onChange={(e) => setIncludeUnknown(e.target.checked)} />
              <span className="text-[var(--text-secondary)] text-xs">筛选时包含「届别待确认」岗位</span>
            </label>
            <label className="block">
              <span className="text-[var(--text-secondary)] text-xs">岗位类型</span>
              <input
                className="mt-1 w-full input-field"
                value={types}
                onChange={(e) => setTypes(e.target.value)}
              />
            </label>
            <label className="block">
              <span className="text-[var(--text-secondary)] text-xs">心仪公司</span>
              <input
                className="mt-1 w-full input-field"
                placeholder="字节跳动，携程"
                value={wishlist}
                onChange={(e) => setWishlist(e.target.value)}
              />
            </label>
            <label className="block md:col-span-2">
              <span className="text-[var(--text-secondary)] text-xs">屏蔽公司</span>
              <input
                className="mt-1 w-full input-field"
                value={blocklist}
                onChange={(e) => setBlocklist(e.target.value)}
              />
            </label>
            <label className="block md:col-span-2">
              <span className="text-[var(--text-secondary)] text-xs">补充说明</span>
              <textarea
                className="mt-1 w-full border rounded-lg px-3 py-2 min-h-[60px]"
                placeholder="例如：优先大厂 AI 方向，不接受外包"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </label>
          </div>
          <div className="mt-3 flex justify-end">
            <button
              type="button"
              onClick={save}
              disabled={saving}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 btn-primary"
            >
              {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
              保存偏好
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
