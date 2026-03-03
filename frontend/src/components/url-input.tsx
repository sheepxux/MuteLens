"use client";

import React, { useCallback, useState } from "react";
import { Search, Link2, ArrowRight, X } from "lucide-react";

interface UrlInputProps {
  onSubmit: (url: string) => void;
  loading: boolean;
  onReset: () => void;
  hasResult: boolean;
}

export default function UrlInput({
  onSubmit,
  loading,
  onReset,
  hasResult,
}: UrlInputProps) {
  const [url, setUrl] = useState("");
  const [focused, setFocused] = useState(false);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const trimmed = url.trim();
      if (!trimmed) return;
      onSubmit(trimmed);
    },
    [url, onSubmit]
  );

  const handleClear = useCallback(() => {
    setUrl("");
    onReset();
  }, [onReset]);

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <div
        className={`
          glass-input relative flex items-center rounded-2xl h-14
          transition-all duration-200
          ${focused
            ? "border-[#fc6011]/40 shadow-[0_0_0_3px_rgba(252,96,17,0.12)]"
            : "hover:border-white/14"
          }
        `}
      >
        <div className={`pl-4 transition-colors duration-200 ${focused ? "text-[#fc6011]/70" : "text-white/25"}`}>
          <Link2 size={16} strokeWidth={1.8} />
        </div>

        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder="粘贴文章链接，开始分析..."
          disabled={loading}
          className="flex-1 bg-transparent px-3 h-full text-[14px] text-white placeholder:text-white/25 outline-none disabled:opacity-40"
        />

        {url && !loading && (
          <button
            type="button"
            onClick={() => setUrl("")}
            className="p-2 mr-1 text-white/20 hover:text-white/50 transition-colors rounded-lg"
          >
            <X size={14} />
          </button>
        )}

        <button
          type="submit"
          disabled={loading || !url.trim()}
          className={`
            mr-2 h-10 flex items-center gap-2 px-5 rounded-xl
            text-[13px] font-medium tracking-wide transition-all duration-150
            ${loading || !url.trim()
              ? "bg-white/5 text-white/20 cursor-not-allowed"
              : "bg-[#fc6011] text-white hover:bg-[#ff7322] active:scale-[0.97] shadow-[0_2px_12px_rgba(252,96,17,0.35)]"
            }
          `}
        >
          {loading ? (
            <div className="w-4 h-4 rounded-full border-2 border-white/20 border-t-white/70"
              style={{ animation: "spin-slow 0.8s linear infinite" }} />
          ) : (
            <>
              <Search size={14} strokeWidth={2} />
              分析
            </>
          )}
        </button>
      </div>

      {hasResult && !loading && (
        <div className="flex justify-center mt-3">
          <button
            type="button"
            onClick={handleClear}
            className="flex items-center gap-1.5 text-[12px] text-white/25 hover:text-[#fc6011] transition-colors duration-150"
          >
            <ArrowRight size={11} />
            分析新文章
          </button>
        </div>
      )}
    </form>
  );
}
