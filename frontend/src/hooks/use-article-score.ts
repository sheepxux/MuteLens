"use client";

import { useCallback, useState } from "react";
import { analyzeArticle } from "@/lib/api";
import { AnalyzeResult } from "@/lib/types";

interface UseArticleScoreReturn {
  result: AnalyzeResult | null;
  loading: boolean;
  error: string | null;
  analyze: (url: string) => Promise<void>;
  reset: () => void;
}

export function useArticleScore(): UseArticleScoreReturn {
  const [result, setResult] = useState<AnalyzeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const analyze = useCallback(async (url: string) => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await analyzeArticle(url);
      setResult(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "分析失败，请稍后重试"
      );
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setResult(null);
    setError(null);
    setLoading(false);
  }, []);

  return { result, loading, error, analyze, reset };
}
