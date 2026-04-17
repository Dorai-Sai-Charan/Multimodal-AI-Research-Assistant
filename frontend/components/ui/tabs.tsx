"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

interface TabsProps {
  tabs: { value: string; label: React.ReactNode; icon?: React.ReactNode }[];
  value: string;
  onChange: (v: string) => void;
  variant?: "pill" | "underline";
  className?: string;
}

export function Tabs({ tabs, value, onChange, variant = "pill", className }: TabsProps) {
  if (variant === "underline") {
    return (
      <div className={cn("flex gap-1 border-b border-border", className)}>
        {tabs.map((t) => {
          const active = t.value === value;
          return (
            <button
              key={t.value}
              onClick={() => onChange(t.value)}
              className={cn(
                "relative px-4 py-2.5 text-sm font-medium transition-colors flex items-center gap-2",
                active
                  ? "text-brand-300"
                  : "text-slate-400 hover:text-slate-200",
              )}
            >
              {t.icon}
              {t.label}
              {active && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-brand" />
              )}
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div
      className={cn(
        "inline-flex items-center gap-1 p-1 rounded-xl glass-strong",
        className,
      )}
    >
      {tabs.map((t) => {
        const active = t.value === value;
        return (
          <button
            key={t.value}
            onClick={() => onChange(t.value)}
            className={cn(
              "relative px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-2 whitespace-nowrap",
              active
                ? "bg-gradient-brand text-white shadow-md shadow-brand-600/20"
                : "text-slate-300 hover:text-white hover:bg-bg-elevated",
            )}
          >
            {t.icon}
            {t.label}
          </button>
        );
      })}
    </div>
  );
}
