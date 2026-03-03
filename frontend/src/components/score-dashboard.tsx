"use client";

import React from "react";
import {
  Globe,
  User,
  Calendar,
  FileText,
  Tag,
  AlertTriangle,
} from "lucide-react";
import { AnalyzeResult } from "@/lib/types";
import ScoreRing from "./score-ring";
import RadarChartView from "./radar-chart";
import DimensionCard from "./dimension-card";

interface ScoreDashboardProps {
  result: AnalyzeResult;
}

export default function ScoreDashboard({ result }: ScoreDashboardProps) {
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
              {result.title || "未提取到标题"}
            </h2>
            <div className="flex flex-wrap gap-3">
              {[
                { Icon: Globe,    label: result.domain },
                result.author   ? { Icon: User,     label: result.author }    : null,
                result.published? { Icon: Calendar, label: result.published } : null,
                { Icon: FileText, label: `${result.word_count.toLocaleString()} 词` },
                { Icon: Tag,      label: result.content_type_label },
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
            <p className="text-[13px] font-semibold text-red-400 mb-1">Veto Gate 否决</p>
            <p className="text-[12px] text-red-400/60">{result.veto_reason}</p>
          </div>
        </div>
      )}

      {/* ── Score ring + radar ──────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="glass-panel rounded-3xl p-6 flex flex-col items-center">
          <ScoreRing score={result.overall_score} grade={result.grade} vetoed={result.vetoed} />

          <div className="divider w-full my-5" />

          <p className="text-[13px] text-white/55 leading-relaxed text-center">
            {result.analysis_summary}
          </p>

          {!result.vetoed && (
            <>
              <div className="divider w-full my-5" />
              <p className="text-[10px] text-white/20 font-mono uppercase tracking-widest mb-3">计算过程</p>
              <div className="flex flex-wrap justify-center gap-2 w-full">
                {Object.entries(result.intermediate).map(([key, value]) => (
                  <div key={key} className="glass-card rounded-xl px-3 py-2 flex flex-col items-center">
                    <span className="text-[10px] text-white/25 font-mono">{key}</span>
                    <span className="text-[13px] text-white/70 font-mono font-semibold tabular-nums">
                      {typeof value === "number" ? value.toFixed(3) : value}
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        <RadarChartView dimensions={result.dimensions} />
      </div>

      <div>
        <div className="flex items-center gap-3 mb-4">
          <p className="text-[11px] font-mono text-white/25 uppercase tracking-widest">10 维度详细评分</p>
          <div className="flex-1 divider" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {result.dimensions.map((dim, i) => (
            <DimensionCard key={dim.key} dimension={dim} index={i} />
          ))}
        </div>
      </div>

      <div className="glass-panel rounded-3xl p-5">
        <p className="text-[10px] font-mono text-white/20 uppercase tracking-widest mb-4">评分公式</p>
        <div className="space-y-2">
          {[
            { k: "B",       v: "w1·D1 + w2·D2 + w3·D3 + w4·D4 + w5·D5", note: "加权基础分" },
            { k: "P",       v: "0.25 + 0.75 / (1 + e^(−0.8·(D6−5)))",    note: "标题一致性调节" },
            { k: "K",       v: "1 + 0.3 · tanh((D7−5)/3)",                note: "传播潜力调节" },
            { k: "V_final", v: "sigmoid(B · P · K · depth_bonus) · 100",  note: "归一化 0–100" },
          ].map(({ k, v, note }) => (
            <div key={k} className="flex items-baseline gap-2 font-mono text-[12px]">
              <span className="text-[#fc6011] w-16 flex-shrink-0">{k}</span>
              <span className="text-white/20">=</span>
              <span className="text-white/40 flex-1">{v}</span>
              <span className="text-white/20 text-[11px] hidden md:block">{note}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
