"use client";

import React, { useEffect, useState } from "react";
import { getOverallScoreColor } from "@/lib/utils";

interface ScoreRingProps {
  score: number;
  grade: string;
  vetoed: boolean;
}

export default function ScoreRing({ score, grade, vetoed }: ScoreRingProps) {
  const [animatedScore, setAnimatedScore] = useState(0);

  useEffect(() => {
    let frame: number;
    const duration = 1200;
    const start = performance.now();

    const animate = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setAnimatedScore(Math.round(eased * score * 10) / 10);
      if (progress < 1) {
        frame = requestAnimationFrame(animate);
      }
    };

    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [score]);

  const radius = 70;
  const circumference = 2 * Math.PI * radius;
  const progress = vetoed ? 0 : animatedScore / 100;
  const dashOffset = circumference * (1 - progress);
  const color = vetoed ? "#ef4444" : getOverallScoreColor(score);

  return (
    <div className="relative flex flex-col items-center">
      <div className="relative w-48 h-48">
        <div
          className="absolute inset-0 rounded-full blur-2xl opacity-20"
          style={{ background: color }}
        />
        <svg viewBox="0 0 160 160" className="w-full h-full -rotate-90 score-ring">
          <circle cx="80" cy="80" r={radius} fill="none"
            stroke="rgba(255,255,255,0.05)" strokeWidth="6" />
          <circle cx="80" cy="80" r={radius - 10} fill="none"
            stroke="rgba(255,255,255,0.03)" strokeWidth="1" />
          <circle cx="80" cy="80" r={radius} fill="none"
            stroke={color} strokeWidth="6" strokeLinecap="round"
            strokeDasharray={circumference} strokeDashoffset={dashOffset}
            style={{ transition: "stroke-dashoffset 1.2s cubic-bezier(.16,1,.3,1), stroke 0.3s" }}
          />
        </svg>

        <div className="absolute inset-0 flex flex-col items-center justify-center">
          {vetoed ? (
            <>
              <span className="text-2xl font-bold text-red-400 tracking-tight">VETO</span>
              <span className="text-[11px] text-red-400/60 mt-1 font-mono">已否决</span>
            </>
          ) : (
            <>
              <span className="text-[11px] text-white/30 font-mono mb-1 tracking-widest">SCORE</span>
              <span className="text-5xl font-bold tabular-nums leading-none tracking-tight" style={{ color }}>
                {animatedScore.toFixed(0)}
              </span>
              <span className="text-xl font-semibold mt-1.5 tracking-wide" style={{ color: `${color}99` }}>
                {grade}
              </span>
            </>
          )}
        </div>
      </div>
      <p className="text-[11px] text-white/20 font-mono mt-3 tracking-wider">综合评分 / 100</p>
    </div>
  );
}
