"use client";

import { FileText, Quote } from "lucide-react";
import { Collapsible } from "./ui/collapsible";
import type { Citation } from "@/lib/types";
import { formatPercent } from "@/lib/utils";

interface CitationsProps {
  citations: Citation[];
}

export function Citations({ citations }: CitationsProps) {
  if (!citations || citations.length === 0) return null;
  return (
    <Collapsible
      title={`Sources & Citations (${citations.length})`}
      icon={<Quote className="w-3.5 h-3.5" />}
      className="mt-3"
    >
      <ul className="space-y-2 pt-1">
        {citations.map((c, i) => (
          <li
            key={i}
            className="flex items-start gap-3 p-3 rounded-lg bg-bg-subtle border-l-4 border-brand-500/70 border-y border-r border-border"
          >
            <FileText className="w-4 h-4 text-brand-400 shrink-0 mt-0.5" />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                <span className="text-sm font-medium text-slate-200 truncate">
                  {c.source_file}
                </span>
                <span className="text-xs text-slate-500">
                  · Page {c.page_number}
                </span>
                {c.section && (
                  <span className="text-xs text-slate-500">· {c.section}</span>
                )}
              </div>
              <div className="mt-1 flex items-center gap-2">
                <div className="h-1 flex-1 max-w-[160px] bg-bg-elevated rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-brand"
                    style={{ width: `${Math.round(c.relevance_score * 100)}%` }}
                  />
                </div>
                <span className="text-[10px] font-mono text-brand-300 tabular-nums">
                  {formatPercent(c.relevance_score)}
                </span>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </Collapsible>
  );
}
