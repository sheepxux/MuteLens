"use client";

import React from "react";
import {
  Globe,
  User,
  Calendar,
  FileText,
  AlertTriangle,
} from "lucide-react";
import { AnalyzeResult } from "@/lib/types";
import { useLocale } from "@/lib/i18n/context";
import ScoreRing from "./score-ring";
import RadarChartView from "./radar-chart";
import DimensionCard from "./dimension-card";
import BadgeEmbed from "./badge-embed";

interface ScoreDashboardProps {
  result: AnalyzeResult;
}

export default function ScoreDashboard({ result }: ScoreDashboardProps) {
  const { t, locale } = useLocale();

  const gradeLabel = t(
    `grade.${result.grade}` as Parameters<typeof t>[0],
  );

  return (
    <div className="w-full max-w-5xl mx-auto space-y-4">

      <div className="glass-panel rounded-3xl p-6">
        <div className="flex flex-col md:flex-row gap-5">
          {result.cover_image && (
            <div className="flex-shrink-0">
              <img
                src={result.cover_image}
                alt={result.title}
                className="w-full md:w-44 h-28 object-cover rounded-2xl"
                onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
              />
            </div>
          )}
          <div className="flex-1 min-w-0">
            <h2 className="text-[17px] font-semibold text-white leading-snug mb-3 line-clamp-2 tracking-tight">
              {result.title || t("dashboard.noTitle")}
            </h2>
            <div className="flex flex-wrap gap-3">
              {[
                { Icon: Globe,    label: result.domain },
                result.author   ? { Icon: User,     label: result.author }    : null,
                result.published? { Icon: Calendar, label: result.published } : null,
                { Icon: FileText, label: `${result.word_count.toLocaleString()} ${t("dashboard.words")}` },
              ].filter(Boolean).map((item, i) => item && (
                <span key={i} className="flex items-center gap-1.5 text-[12px] text-white/40">
                  <item.Icon size={12} className="text-white/20" />
                  {item.label}
                </span>
              ))}
            </div>
            {result.content_preview && (
              <p className="mt-3 text-[12px] text-white/25 leading-relaxed line-clamp-2">
                {result.content_preview}
              </p>
            )}
          </div>
        </div>
      </div>

      {result.vetoed && (
        <div className="flex items-start gap-4 rounded-2xl p-5 border border-red-500/20 bg-red-500/5 backdrop-blur-xl animate-scale-in">
          <AlertTriangle size={18} className="text-red-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-[13px] font-semibold text-red-400 mb-1">{t("dashboard.vetoTitle")}</p>
            <p className="text-[12px] text-red-400/60">{result.veto_reason}</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="glass-panel rounded-3xl p-6 flex flex-col items-center">
          <ScoreRing score={result.overall_score} grade={result.grade} vetoed={result.vetoed} />

          {!result.vetoed && (
            <p className="text-[12px] text-white/30 mt-2">
              {gradeLabel}
            </p>
          )}

          <div className="divider w-full my-5" />

          <p className="text-[15px] text-white/60 leading-relaxed text-center">
            {result.analysis_summary}
          </p>
        </div>

        <RadarChartView dimensions={result.dimensions} />
      </div>

      <div>
        <div className="flex items-center gap-3 mb-4">
          <p className="text-[11px] font-mono text-white/25 uppercase tracking-widest">{t("dashboard.dimensionsTitle")}</p>
          <div className="flex-1 divider" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {result.dimensions.map((dim, i) => (
            <DimensionCard key={dim.key} dimension={dim} index={i} />
          ))}
        </div>
      </div>

      <div className="glass-panel rounded-3xl p-5">
        <p className="text-[10px] font-mono text-white/20 uppercase tracking-widest mb-4">{t("dashboard.weightsTitle")}</p>
        <div className="space-y-2.5">
          {result.dimensions.map((d) => {
            const dimLabel = locale === "en" ? d.labelEn : d.label;
            const pct = Math.round(d.weight * 100);
            return (
              <div key={d.key} className="flex items-center gap-3">
                <span className="text-[11px] text-white/40 w-20 flex-shrink-0 text-right font-mono">{dimLabel}</span>
                <div className="flex-1 h-[6px] bg-white/5 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full bg-[#fc6011]/70"
                    style={{ width: `${pct * 4}%`, transition: "width 0.8s ease" }}
                  />
                </div>
                <span className="text-[11px] text-white/25 font-mono w-8 flex-shrink-0">{pct}%</span>
              </div>
            );
          })}
        </div>
      </div>

      {result.badge_id && (
        <BadgeEmbed
          badgeId={result.badge_id}
          score={result.overall_score}
          grade={result.grade}
        />
      )}
    </div>
  );
}
