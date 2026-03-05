"use client";

import React from "react";
import {
  Lightbulb,
  Scale,
  BarChart3,
  Telescope,
  Microscope,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import { DimensionScore } from "@/lib/types";
import { getScoreColor } from "@/lib/utils";
import { useLocale } from "@/lib/i18n/context";

interface DimensionCardProps {
  dimension: DimensionScore;
  index: number;
}

const DIMENSION_ICONS: Record<string, LucideIcon> = {
  d1: Lightbulb,
  d2: Scale,
  d3: BarChart3,
  d4: Telescope,
  d5: Microscope,
  d6: ShieldCheck,
};

export default function DimensionCard({
  dimension,
  index,
}: DimensionCardProps) {
  const color = getScoreColor(dimension.score);
  const percentage = (dimension.score / dimension.maxScore) * 100;
  const IconComponent = DIMENSION_ICONS[dimension.key] || BarChart3;
  const weightPct = Math.round(dimension.weight * 100);
  const { locale } = useLocale();

  const label = locale === "en" ? dimension.labelEn : dimension.label;

  return (
    <div
      className="glass-card rounded-2xl p-4 animate-fade-up hover:border-white/10 transition-all duration-200"
      style={{ animationDelay: `${index * 50}ms` }}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg glass-accent flex items-center justify-center flex-shrink-0">
            <IconComponent size={13} className="text-[#fc6011]" />
          </div>
          <div>
            <p className="text-[13px] font-medium text-white leading-tight">{label}</p>
            <p className="text-[10px] text-white/30 font-mono leading-tight mt-0.5">
              {weightPct}%
            </p>
          </div>
        </div>
        <div className="text-right flex-shrink-0">
          <span className="text-2xl font-bold tabular-nums leading-none" style={{ color }}>
            {dimension.score.toFixed(1)}
          </span>
          <span className="text-[10px] text-white/20 font-mono ml-0.5">/{dimension.maxScore}</span>
        </div>
      </div>

      <div className="h-[3px] bg-white/5 rounded-full overflow-hidden mb-3">
        <div
          className="h-full rounded-full"
          style={{
            width: `${percentage}%`,
            backgroundColor: color,
            boxShadow: `0 0 6px ${color}60`,
            transition: "width 1s cubic-bezier(.16,1,.3,1)",
          }}
        />
      </div>

      <p className="text-[11px] text-white/30 leading-relaxed line-clamp-2">
        {dimension.description}
      </p>
    </div>
  );
}
