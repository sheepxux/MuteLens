export interface DimensionScore {
  key: string;
  label: string;
  labelEn: string;
  score: number;
  maxScore: number;
  description: string;
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
  content_type: string;
  content_type_label: string;
  dimensions: DimensionScore[];
  intermediate: Record<string, number>;
  analysis_summary: string;
}
