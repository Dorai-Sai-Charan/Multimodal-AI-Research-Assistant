import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatPercent(n: number): string {
  return `${Math.round(n * 100)}%`;
}

export function truncate(s: string, max = 300): string {
  if (s.length <= max) return s;
  return s.slice(0, max) + "…";
}
