"use client";

import React, { useEffect, useState } from "react";
import { use } from "react";
import Image from "next/image";
import Link from "next/link";
import {
  Globe,
  User,
  Calendar,
  FileText,
  ArrowLeft,
  Shield,
  CheckCircle,
  Clock,
} from "lucide-react";
import dynamic from "next/dynamic";
import { useLocale } from "@/lib/i18n/context";

const ShaderBackground = dynamic(
  () => import("@/components/shader-background"),
  { ssr: false }
);

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface VerifyData {
  badge_id: string;
  url: string;
  domain: string;
  title: string;
  author: string;
  published: string;
  cover_image: string;
  word_count: number;
  language: string;
  overall_score: number;
  grade: string;
  vetoed: boolean;
  veto_reason: string;
  dimensions: {
    key: string;
    label: string;
    labelEn: string;
    score: number;
    maxScore: number;
    description: string;
    weight: number;
  }[];
  analysis_summary: string;
  created_at: string;
  badge_url: string;
  verify_url: string;
}

const BRAND = "#fc6011";

export default function VerifyPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { t, locale } = useLocale();
  const [data, setData] = useState<VerifyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/api/verify/${id}`)
      .then((res) => {
        if (!res.ok) throw new Error("Not found");
        return res.json();
      })
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [id]);

  const brandColor = BRAND;

  return (
    <div className="min-h-screen flex flex-col">
      <ShaderBackground />

      <div className="fixed top-4 left-0 right-0 z-30 flex justify-center px-6 pointer-events-none">
        <header
          className="glass-bar rounded-2xl border pointer-events-auto w-full max-w-3xl"
          style={{ borderColor: "rgba(255,255,255,0.08)" }}
        >
          <div className="px-6 h-12 flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2.5">
              <Image
                src="/mutelens.svg"
                alt="MuteLens"
                width={22}
                height={22}
                className="rounded-md"
              />
              <span className="text-[14px] font-semibold text-white tracking-tight">
                MuteLens
              </span>
            </Link>
            <div className="flex items-center gap-2">
              <Shield size={14} className="text-[#fc6011]" />
              <span className="text-[12px] text-white/50 font-mono">
                {t("verify.title")}
              </span>
            </div>
          </div>
        </header>
      </div>

      <main className="flex-1 flex flex-col items-center pt-24 pb-16 px-5">
        {loading && (
          <div className="flex items-center gap-3 mt-20">
            <div className="w-5 h-5 border-2 border-[#fc6011]/30 border-t-[#fc6011] rounded-full animate-spin" />
            <span className="text-white/40 text-sm">Loading...</span>
          </div>
        )}

        {error && (
          <div className="mt-20 text-center space-y-4">
            <p className="text-white/50 text-sm">{t("verify.notFound")}</p>
            <Link
              href="/"
              className="inline-flex items-center gap-2 text-[#fc6011] text-sm hover:underline"
            >
              <ArrowLeft size={14} />
              {t("verify.backHome")}
            </Link>
          </div>
        )}

        {data && (
          <div className="w-full max-w-2xl space-y-4 animate-fade-up">
            <div className="glass-panel rounded-3xl p-6 text-center space-y-4">
              <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-[#fc6011]/10 border border-[#fc6011]/20">
                <CheckCircle size={14} className="text-[#fc6011]" />
                <span className="text-[12px] text-[#fc6011] font-medium">
                  {t("verify.authentic")}
                </span>
              </div>

              <div className="flex flex-col items-center gap-2">
                <div
                  className="text-6xl font-bold"
                  style={{ color: brandColor }}
                >
                  {Math.round(data.overall_score)}
                </div>
                <div
                  className="text-lg font-semibold"
                  style={{ color: brandColor }}
                >
                  {data.grade}
                </div>
                <p className="text-[11px] text-white/25 font-mono">
                  {t(
                    `grade.${data.grade}` as Parameters<typeof t>[0]
                  )}
                </p>
              </div>

              <div className="flex items-center justify-center gap-1.5 text-[11px] text-white/25">
                <Clock size={11} />
                {t("verify.evaluated")}:{" "}
                {new Date(data.created_at).toLocaleDateString(
                  locale === "zh" ? "zh-CN" : "en-US",
                  {
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                  }
                )}
              </div>
            </div>

            <div className="glass-panel rounded-3xl p-6">
              <h2 className="text-[17px] font-semibold text-white leading-snug mb-3 tracking-tight">
                {data.title || t("dashboard.noTitle")}
              </h2>
              <div className="flex flex-wrap gap-3 mb-3">
                {[
                  { Icon: Globe, label: data.domain },
                  data.author
                    ? { Icon: User, label: data.author }
                    : null,
                  data.published
                    ? { Icon: Calendar, label: data.published }
                    : null,
                  {
                    Icon: FileText,
                    label: `${data.word_count.toLocaleString()} ${t("dashboard.words")}`,
                  },
                ]
                  .filter(Boolean)
                  .map(
                    (item, i) =>
                      item && (
                        <span
                          key={i}
                          className="flex items-center gap-1.5 text-[12px] text-white/40"
                        >
                          <item.Icon size={12} className="text-white/20" />
                          {item.label}
                        </span>
                      )
                  )}
              </div>
              <a
                href={data.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[12px] text-[#fc6011]/70 hover:text-[#fc6011] transition-colors break-all"
              >
                {data.url}
              </a>
            </div>

            <div className="glass-panel rounded-3xl p-6">
              <p className="text-[15px] text-white/60 leading-relaxed">
                {data.analysis_summary}
              </p>
            </div>

            <div className="glass-panel rounded-3xl p-5">
              <p className="text-[10px] font-mono text-white/20 uppercase tracking-widest mb-4">
                {t("dashboard.dimensionsTitle")}
              </p>
              <div className="space-y-3">
                {data.dimensions.map((d) => {
                  const dimLabel =
                    locale === "en" ? d.labelEn : d.label;
                  const pct = (d.score / d.maxScore) * 100;
                  return (
                    <div key={d.key} className="space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-[12px] text-white/50">
                          {dimLabel}
                        </span>
                        <span
                          className="text-[12px] font-mono font-semibold"
                          style={{ color: brandColor }}
                        >
                          {d.score}/{d.maxScore}
                        </span>
                      </div>
                      <div className="h-[4px] bg-white/5 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-700"
                          style={{
                            width: `${pct}%`,
                            backgroundColor: brandColor,
                            opacity: 0.7,
                          }}
                        />
                      </div>
                      <p className="text-[11px] text-white/25 leading-relaxed">
                        {d.description}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="text-center py-4">
              <p className="text-[10px] text-white/15 font-mono">
                Badge ID: {data.badge_id}
              </p>
            </div>

            <div className="text-center">
              <Link
                href="/"
                className="inline-flex items-center gap-2 text-[#fc6011]/70 hover:text-[#fc6011] text-[13px] transition-colors"
              >
                <ArrowLeft size={14} />
                {t("verify.backHome")}
              </Link>
            </div>
          </div>
        )}
      </main>

      <footer className="glass-bar border-t">
        <div className="max-w-4xl mx-auto px-6 h-12 flex items-center justify-center">
          <p className="text-[11px] text-white/20 font-mono">
            {t("footer.tagline")}
          </p>
        </div>
      </footer>
    </div>
  );
}
