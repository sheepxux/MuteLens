"use client";

import React, { useState } from "react";
import { Check, Copy, Code, FileText, ExternalLink, Shield } from "lucide-react";
import { useLocale } from "@/lib/i18n/context";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
const SITE_BASE = process.env.NEXT_PUBLIC_SITE_URL || "";

interface BadgeEmbedProps {
  badgeId: string;
  score: number;
  grade: string;
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const { t } = useLocale();
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={handleCopy}
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-mono
                 bg-white/5 hover:bg-white/10 text-white/50 hover:text-white/80
                 transition-all duration-150 border border-white/5 hover:border-white/10"
      title={label}
    >
      {copied ? (
        <>
          <Check size={12} className="text-emerald-400" />
          <span className="text-emerald-400">{t("badge.copied")}</span>
        </>
      ) : (
        <>
          <Copy size={12} />
          <span>{label}</span>
        </>
      )}
    </button>
  );
}

export default function BadgeEmbed({ badgeId, score, grade }: BadgeEmbedProps) {
  const { t } = useLocale();
  const [style, setStyle] = useState<"flat" | "seal">("flat");

  const badgeUrl = `${API_BASE}/api/badge/${badgeId}?style=${style}`;
  const verifyUrl = `${SITE_BASE}/verify/${badgeId}`;

  const htmlCode = `<a href="${verifyUrl}" target="_blank" rel="noopener noreferrer">\n  <img src="${badgeUrl}" alt="MuteLens Score: ${Math.round(score)} (${grade})" />\n</a>`;
  const markdownCode = `[![MuteLens Score](${badgeUrl})](${verifyUrl})`;

  return (
    <div className="glass-panel rounded-3xl p-5 space-y-4">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-xl bg-[#fc6011]/10 flex items-center justify-center">
          <Shield size={15} className="text-[#fc6011]" />
        </div>
        <div>
          <p className="text-[13px] font-semibold text-white">{t("badge.title")}</p>
          <p className="text-[11px] text-white/30">{t("badge.description")}</p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <span className="text-[10px] text-white/25 uppercase tracking-wider font-mono">Style</span>
        <div className="flex rounded-lg border border-white/10 overflow-hidden text-[11px] font-mono">
          <button
            onClick={() => setStyle("flat")}
            className={`px-3 py-1 transition-colors duration-150 ${
              style === "flat" ? "bg-white/10 text-white/80" : "text-white/30 hover:text-white/50"
            }`}
          >
            Flat
          </button>
          <div className="w-px bg-white/10" />
          <button
            onClick={() => setStyle("seal")}
            className={`px-3 py-1 transition-colors duration-150 ${
              style === "seal" ? "bg-white/10 text-white/80" : "text-white/30 hover:text-white/50"
            }`}
          >
            Seal
          </button>
        </div>
      </div>

      <div className="flex flex-col items-center gap-3 py-4 rounded-2xl bg-white/[0.02] border border-white/5">
        <p className="text-[10px] text-white/20 uppercase tracking-wider font-mono">{t("badge.preview")}</p>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={badgeUrl}
          alt={`MuteLens Score: ${Math.round(score)} (${grade})`}
          className={style === "seal" ? "w-60" : "h-7"}
        />
      </div>

      <div className="space-y-3">
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-1.5">
              <Code size={12} className="text-white/25" />
              <span className="text-[10px] text-white/30 uppercase tracking-wider font-mono">{t("badge.html")}</span>
            </div>
            <CopyButton text={htmlCode} label={t("badge.copy")} />
          </div>
          <pre className="text-[11px] text-white/40 bg-white/[0.03] rounded-xl p-3 overflow-x-auto border border-white/5 font-mono leading-relaxed">
            {htmlCode}
          </pre>
        </div>

        <div>
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-1.5">
              <FileText size={12} className="text-white/25" />
              <span className="text-[10px] text-white/30 uppercase tracking-wider font-mono">{t("badge.markdown")}</span>
            </div>
            <CopyButton text={markdownCode} label={t("badge.copy")} />
          </div>
          <pre className="text-[11px] text-white/40 bg-white/[0.03] rounded-xl p-3 overflow-x-auto border border-white/5 font-mono leading-relaxed">
            {markdownCode}
          </pre>
        </div>
      </div>

      <a
        href={verifyUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center justify-center gap-2 py-2.5 rounded-xl
                   bg-[#fc6011]/10 hover:bg-[#fc6011]/20 border border-[#fc6011]/20
                   text-[12px] text-[#fc6011] font-medium transition-all duration-200"
      >
        <ExternalLink size={13} />
        {t("badge.verifyPage")}
      </a>
    </div>
  );
}
