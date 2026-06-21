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
      <div className="text-sm text-slate-500 py-8 text-center">暂无匹配维度数据</div>
    );
  }

  return (
    <div className="w-full">
      <div className="text-center mb-2">
        <span className="text-3xl font-bold text-blue-600">{overallScore}</span>
        <span className="text-slate-500 text-sm ml-1">/ 100</span>
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <RadarChart data={data} cx="50%" cy="50%" outerRadius="70%">
          <PolarGrid stroke="#e2e8f0" />
          <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11, fill: "#64748b" }} />
          <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 10 }} />
          <Radar
            name="匹配度"
            dataKey="score"
            stroke="#2563eb"
            fill="#3b82f6"
            fillOpacity={0.35}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
