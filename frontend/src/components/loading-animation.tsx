"use client";

import React from "react";

const STEPS = [
  "正在获取文章内容...",
  "解析文章结构与元数据...",
  "计算事实密度与信源质量...",
  "评估内容新颖性与深度...",
  "检测标题一致性与情绪...",
  "生成综合评分报告...",
];

export default function LoadingAnimation() {
  const [step, setStep] = React.useState(0);

  React.useEffect(() => {
    const interval = setInterval(() => {
      setStep((prev) => (prev + 1) % STEPS.length);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col items-center justify-center py-16 px-8 animate-fade-in">
      <div className="relative w-16 h-16 mb-8">
        <div className="absolute inset-0 rounded-full"
          style={{ background: "conic-gradient(from 0deg, transparent 0%, rgba(252,96,17,0.8) 100%)", animation: "spin-slow 1.1s linear infinite" }} />
        <div className="absolute inset-[3px] rounded-full bg-black/60 backdrop-blur-sm" />
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-2 h-2 rounded-full bg-[#fc6011]"
            style={{ animation: "glow-pulse 1.5s ease-in-out infinite" }} />
        </div>
      </div>

      <p key={step} className="text-[13px] text-white/50 animate-fade-in mb-6 text-center font-mono">
        {STEPS[step]}
      </p>

      <div className="w-48 h-[2px] rounded-full bg-white/5 overflow-hidden">
        <div
          className="h-full rounded-full bg-[#fc6011] transition-all duration-700 ease-out"
          style={{ width: `${((step + 1) / STEPS.length) * 100}%`, boxShadow: "0 0 8px rgba(252,96,17,0.6)" }}
        />
      </div>
      <p className="text-[11px] text-white/15 font-mono mt-2">
        {step + 1} / {STEPS.length}
      </p>
    </div>
  );
}
