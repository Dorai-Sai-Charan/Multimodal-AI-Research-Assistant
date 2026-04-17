"use client";

import { Layers } from "lucide-react";
import { Markdown } from "./markdown";
import { Citations } from "./citations";
import { ReasoningSteps } from "./reasoning-steps";
import type { AgentQueryResponse, QueryResponse } from "@/lib/types";

interface ResultViewProps {
  data: QueryResponse | AgentQueryResponse;
  modeLabel?: string;
}

export function ResultView({ data, modeLabel }: ResultViewProps) {
  const isAgent = "reasoning_steps" in data;
  return (
    <div className="glass rounded-xl p-6">
      <Markdown content={data.answer} />
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
