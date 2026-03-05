export interface DimensionScore {
  key: string;
  label: string;
  labelEn: string;
  score: number;
  maxScore: number;
  description: string;
  weight: number;
}

export interface AnalyzeResult {
  url: string;
  domain: string;
  title: string;
  author: string;
  published: string;
  cover_image: string;
  word_count: number;
  language: string;
  content_preview: string;
  overall_score: number;
  grade: string;
  vetoed: boolean;
  veto_reason: string;
  dimensions: DimensionScore[];
  weights: Record<string, number>;
  analysis_summary: string;
  badge_id: string;
}
