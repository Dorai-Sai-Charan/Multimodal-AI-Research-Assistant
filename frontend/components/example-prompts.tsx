"use client";

import type { LucideIcon } from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

export interface ExamplePrompt {
  icon: LucideIcon;
  title: string;
  prompt: string;
  color?: string;
}

interface ExamplePromptsProps {
  prompts: ExamplePrompt[];
  onPick: (prompt: string) => void;
  columns?: 2 | 3 | 4;
  heading?: string;
}

export function ExamplePrompts({
  prompts,
  onPick,
  columns = 2,
  heading,
}: ExamplePromptsProps) {
  const gridClass =
    columns === 2
      ? "grid-cols-1 sm:grid-cols-2"
      : columns === 3
        ? "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3"
        : "grid-cols-1 sm:grid-cols-2 lg:grid-cols-4";

  return (
    <div>
      {heading && (
        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-500 font-semibold mb-3">
          {heading}
        </div>
      )}
      <div className={cn("grid gap-2", gridClass)}>
        {prompts.map((p, i) => {
          const Icon = p.icon;
          const tint = p.color ?? "text-brand-300";
          return (
            <motion.button
              key={i}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04 }}
              whileHover={{ y: -2 }}
              onClick={() => onPick(p.prompt)}
              className="group relative text-left p-3 rounded-xl border border-border bg-bg-subtle/60 hover:border-brand-500/50 hover:bg-bg-elevated transition-all overflow-hidden"
            >
              <div className="flex items-start gap-2.5">
                <div
                  className={cn(
                    "w-8 h-8 rounded-lg bg-bg-elevated border border-border flex items-center justify-center shrink-0 group-hover:scale-110 transition-transform",
                    tint,
                  )}
                >
                  <Icon className="w-4 h-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-[11px] font-semibold text-slate-200 mb-0.5">
                    {p.title}
                  </div>
                  <div className="text-[11px] text-slate-400 leading-snug line-clamp-2">
                    {p.prompt}
                  </div>
                </div>
              </div>
              <div className="absolute inset-x-0 bottom-0 h-0.5 bg-gradient-brand opacity-0 group-hover:opacity-100 transition-opacity" />
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}
