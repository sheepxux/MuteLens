"use client";

import React from "react";
import dynamic from "next/dynamic";
import Image from "next/image";
import { BarChart3, ShieldAlert, FlaskConical, Github } from "lucide-react";
import UrlInput from "@/components/url-input";
import LoadingAnimation from "@/components/loading-animation";
import ScoreDashboard from "@/components/score-dashboard";
import { useArticleScore } from "@/hooks/use-article-score";
import PlatformLogoLoop from "@/components/platform-logo-loop";

const ShaderBackground = dynamic(
  () => import("@/components/shader-background"),
  { ssr: false }
);

export default function Home() {
  const { result, loading, error, analyze, reset } = useArticleScore();

  return (
    <div className="min-h-screen flex flex-col">
      <ShaderBackground />

      <div className="fixed top-4 left-0 right-0 z-30 flex justify-center px-6 pointer-events-none">
        <header className="glass-bar rounded-2xl border pointer-events-auto w-full max-w-3xl" style={{ borderColor: "rgba(255,255,255,0.08)" }}>
          <div className="px-6 h-12 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <Image src="/mutelens.svg" alt="Mutelens" width={22} height={22} className="rounded-md" />
              <span className="text-[14px] font-semibold text-white tracking-tight">MuteLens</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="tag-pill">v2.0.3</span>
              <div className="w-px h-4 bg-white/10" />
              <a
                href="https://github.com/sheepxux/Mutelens"
                target="_blank"
                rel="noopener noreferrer"
                className="text-white/30 hover:text-white/80 transition-colors duration-150"
                aria-label="GitHub"
              >
                <Github size={16} strokeWidth={1.8} />
              </a>
            </div>
          </div>
        </header>
      </div>

      <main className="flex-1 flex flex-col items-center">

        {!result && !loading && (
          <section className="w-full max-w-2xl px-5 pt-28 pb-10 animate-fade-up">
            <div className="flex justify-center mb-8">
              <span className="tag-pill">
                <span className="w-1.5 h-1.5 rounded-full bg-[#fc6011]" style={{ animation: "glow-pulse 2s ease-in-out infinite" }} />
                AI 多维度分析引擎
              </span>
            </div>

            <h2 className="text-center text-4xl font-bold text-white leading-tight tracking-tight mb-4">
              消除信息噪音，<br />
              <span style={{ color: "#fc6011" }}>看清文章质量</span>
            </h2>
            <p className="text-center text-[15px] text-white/40 max-w-sm mx-auto leading-relaxed mb-10">
              粘贴任意文章链接，从 10 个维度深度评测，生成客观的质量评分报告。
            </p>

            <UrlInput onSubmit={analyze} loading={loading} onReset={reset} hasResult={!!result} />

            <div className="divider my-8" />
            <div className="grid grid-cols-3 gap-3">
              {[
                { title: "10 维度评分", desc: "事实密度、信源质量、内容深度、情绪中立度", Icon: BarChart3 },
                { title: "Veto Gate",   desc: "自动识别标题党、广告软文、极端情绪内容",   Icon: ShieldAlert },
                { title: "公式透明",    desc: "Sigmoid 归一化，动态权重，全程可追溯",     Icon: FlaskConical },
              ].map((item) => (
                <div key={item.title} className="glass-card rounded-2xl p-4 flex flex-col gap-2.5 hover:border-[#fc6011]/20 transition-colors duration-200">
                  <div className="w-8 h-8 rounded-xl glass-accent flex items-center justify-center flex-shrink-0">
                    <item.Icon size={15} className="text-[#fc6011]" />
                  </div>
                  <div>
                    <p className="text-[13px] font-medium text-white mb-0.5">{item.title}</p>
                    <p className="text-[11px] text-white/35 leading-relaxed">{item.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {!result && !loading && (
          <div className="w-full py-6 animate-fade-in" style={{ animationDelay: "200ms" }}>
            <PlatformLogoLoop />
          </div>
        )}

        {loading && (
          <div className="w-full max-w-2xl px-5 pt-24">
            <div className="glass-panel rounded-3xl">
              <LoadingAnimation />
            </div>
            <div className="mt-4">
              <UrlInput onSubmit={analyze} loading={loading} onReset={reset} hasResult={!!result} />
            </div>
          </div>
        )}

        {error && !loading && (
          <div className="w-full max-w-2xl px-5 pt-24 pb-6 animate-fade-in">
            <div className="glass-panel rounded-2xl px-5 py-4 border border-red-500/20 flex items-start gap-3">
              <div className="w-5 h-5 rounded-full bg-red-500/15 flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-red-400 text-xs font-bold">!</span>
              </div>
              <div>
                <p className="text-sm font-medium text-red-400 mb-0.5">分析失败</p>
                <p className="text-xs text-red-400/70">{error}</p>
              </div>
            </div>
            <div className="mt-4">
              <UrlInput onSubmit={analyze} loading={loading} onReset={reset} hasResult={!!result} />
            </div>
          </div>
        )}

        {result && !loading && (
          <section className="w-full max-w-5xl px-5 pt-20 pb-16 animate-scale-in">
            <div className="mb-6">
              <UrlInput onSubmit={analyze} loading={loading} onReset={reset} hasResult={!!result} />
            </div>
            <ScoreDashboard result={result} />
          </section>
        )}

      </main>

      <footer className="glass-bar border-t">
        <div className="max-w-4xl mx-auto px-6 h-12 flex items-center justify-between">
          <p className="text-[11px] text-white/20 font-mono">
            MuteLens v2.0.3 · 基于多维度评分引擎
          </p>
          <p className="text-[11px] text-white/25 font-mono">
            由{" "}
            <a
              href="https://github.com/sheepxux"
              target="_blank"
              rel="noopener noreferrer"
              className="text-white/45 hover:text-[#fc6011] transition-colors duration-150"
            >
              @Sheepxux
            </a>
            {" "}设计开发
          </p>
        </div>
      </footer>
    </div>
  );
}
