"use client";

import { Layers, Download } from "lucide-react";
import { toast } from "sonner";
import { Markdown } from "./markdown";
import { Citations } from "./citations";
import { VisualCitations } from "./visual-citations";
import { ReasoningSteps } from "./reasoning-steps";
import { exportResults } from "@/lib/api";
import type { AgentQueryResponse, QueryResponse } from "@/lib/types";

interface ResultViewProps {
  data: QueryResponse | AgentQueryResponse;
  modeLabel?: string;
}

export function ResultView({ data, modeLabel }: ResultViewProps) {
  const isAgent = "reasoning_steps" in data;

  const handleExport = async () => {
    try {
      await exportResults({
        title: data.query || "Results",
        answer: data.answer,
        question: data.query,
        citations: data.citations ?? [],
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error("Export failed", { description: msg });
    }
  };

  return (
    <div className="glass rounded-xl p-6">
      {data.answer && (
        <div className="flex justify-end mb-3">
          <button
            onClick={handleExport}
            className="inline-flex items-center gap-1.5 text-sm px-3 py-1 rounded border border-border hover:bg-bg-elevated text-slate-300 hover:text-slate-100 transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            Export .md
          </button>
        </div>
      )}
      <Markdown content={data.answer} />
      <VisualCitations citations={data.citations ?? []} />
      <Citations citations={data.citations ?? []} />
      {isAgent && (
        <ReasoningSteps
          steps={(data as AgentQueryResponse).reasoning_steps}
        />
      )}
      <div className="mt-4 flex items-center gap-3 text-[11px] text-slate-500">
        {modeLabel && (
          <span className="chip !text-[10px]">
            Mode: <span className="text-slate-200 ml-1">{modeLabel}</span>
          </span>
        )}
        <span className="flex items-center gap-1.5">
          <Layers className="w-3 h-3" />
          {data.chunks_used} chunks used
        </span>
        {isAgent && (
          <span>
            {(data as AgentQueryResponse).total_steps} reasoning steps
          </span>
        )}
      </div>
    </div>
  );
}
