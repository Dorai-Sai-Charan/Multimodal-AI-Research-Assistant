"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

interface ToggleProps {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: React.ReactNode;
  description?: string;
  icon?: React.ReactNode;
}

export function Toggle({ checked, onChange, label, description, icon }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={cn(
        "group flex items-center gap-3 w-full p-2.5 rounded-lg border transition-all text-left",
        checked
          ? "bg-brand-500/10 border-brand-500/50"
          : "bg-bg-elevated border-border hover:border-border-strong",
      )}
    >
      {icon && (
        <div
          className={cn(
            "w-8 h-8 rounded-md flex items-center justify-center shrink-0 transition-colors",
            checked
              ? "bg-brand-500/20 text-brand-300"
              : "bg-bg-subtle text-slate-400",
          )}
        >
          {icon}
        </div>
      )}
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-slate-200">{label}</div>
        {description && (
          <div className="text-[11px] text-slate-500 mt-0.5 leading-snug">
            {description}
          </div>
        )}
      </div>
      <div
        className={cn(
          "relative w-9 h-5 rounded-full transition-colors shrink-0",
          checked ? "bg-brand-500" : "bg-bg-subtle border border-border",
        )}
      >
        <div
          className={cn(
            "absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform",
            checked ? "translate-x-4" : "translate-x-0.5",
          )}
        />
      </div>
    </button>
  );
}
