import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function getScoreColor(score: number): string {
  if (score >= 8) return "#22c55e";
  if (score >= 6) return "#fc6011";
  if (score >= 4) return "#f59e0b";
  return "#ef4444";
}

export function getGradeColor(grade: string): string {
  if (grade.startsWith("A")) return "#22c55e";
  if (grade.startsWith("B")) return "#fc6011";
  if (grade.startsWith("C")) return "#f59e0b";
  return "#ef4444";
}

export function getOverallScoreColor(score: number): string {
  if (score >= 75) return "#22c55e";
  if (score >= 55) return "#fc6011";
  if (score >= 40) return "#f59e0b";
  return "#ef4444";
}
