"use client";

import React from "react";
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { DimensionScore } from "@/lib/types";
import { useLocale } from "@/lib/i18n/context";

interface RadarChartViewProps {
  dimensions: DimensionScore[];
}

export default function RadarChartView({ dimensions }: RadarChartViewProps) {
  const { locale } = useLocale();

  const data = dimensions.map((d) => ({
    subject: locale === "en" ? d.labelEn : d.label,
    score: d.score,
    fullMark: 10,
  }));

  return (
    <div className="glass-panel rounded-2xl p-6">
      <div className="w-full h-[340px]">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart
            cx="50%"
            cy="50%"
            outerRadius="75%"
            data={data}
          >
            <PolarGrid
              stroke="#2a2a3a"
              strokeDasharray="3 3"
            />
            <PolarAngleAxis
              dataKey="subject"
              tick={{
                fill: "rgba(255,255,255,0.5)",
                fontSize: 12,
              }}
            />
            <PolarRadiusAxis
              angle={90}
              domain={[0, 10]}
              tick={{ fill: "#52525b", fontSize: 10 }}
              axisLine={false}
            />
            <Radar
              name="Score"
              dataKey="score"
              stroke="#fc6011"
              fill="#fc6011"
              fillOpacity={0.2}
              strokeWidth={2}
              dot={{
                r: 4,
                fill: "#fc6011",
                stroke: "#fc6011",
              }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "rgba(6,4,4,0.92)",
                border: "1px solid #2a2018",
                borderRadius: "8px",
                fontSize: "13px",
                color: "#e8e8ed",
              }}
              formatter={(value: number | undefined) => [
                `${(value ?? 0).toFixed(1)} / 10`,
                locale === "en" ? "Score" : "分数",
              ]}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
