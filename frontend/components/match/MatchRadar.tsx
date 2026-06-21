"use client";

import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from "recharts";
import type { MatchDimension } from "@/lib/types";
import { copy } from "@/lib/copy";

export default function MatchRadar({
  dimensions,
  overallScore,
}: {
  dimensions: MatchDimension[];
  overallScore: number;
}) {
  const data = dimensions.map((d) => ({
    subject: d.name.length > 6 ? d.name.slice(0, 6) + "…" : d.name,
    fullName: d.name,
    score: d.score,
    fullMark: d.max || 100,
  }));

  if (!data.length) {
    return (
      <div className="text-sm text-[var(--text-secondary)] py-8 text-center">
        {copy.match.noDimensions}
      </div>
    );
  }

  return (
    <div className="w-full">
      <div className="text-center mb-2">
        <span className="text-3xl font-bold text-[var(--primary)]">{overallScore}</span>
        <span className="text-[var(--text-secondary)] text-sm ml-1">/ 100</span>
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <RadarChart data={data} cx="50%" cy="50%" outerRadius="70%">
          <PolarGrid stroke="var(--border-subtle)" />
          <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11, fill: "var(--text-secondary)" }} />
          <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 10 }} />
          <Radar
            name="匹配度"
            dataKey="score"
            stroke="var(--primary)"
            fill="var(--primary)"
            fillOpacity={0.35}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
