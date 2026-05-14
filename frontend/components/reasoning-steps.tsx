"use client";

import { Brain, Lightbulb, Zap, Eye } from "lucide-react";
import { Collapsible } from "./ui/collapsible";
import type { ReasoningStep } from "@/lib/types";
import { truncate } from "@/lib/utils";

interface ReasoningStepsProps {
  steps: ReasoningStep[];
}

export function ReasoningSteps({ steps }: ReasoningStepsProps) {
  if (!steps || steps.length === 0) return null;
  return (
    <Collapsible
      title={`Agent Reasoning Trace (${steps.length} step${steps.length === 1 ? "" : "s"})`}
      icon={<Brain className="w-3.5 h-3.5" />}
      className="mt-3"
    >
      <ol className="space-y-2 pt-1">
        {steps.map((s) => (
          <li
            key={s.step}
            className="rounded-lg bg-bg-subtle border border-border p-3 space-y-2"
          >
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                Step
              </span>
              <span className="w-5 h-5 rounded-full bg-brand-500/20 border border-brand-500/40 text-brand-300 text-[10px] font-bold flex items-center justify-center">
                {s.step}
              </span>
            </div>
            <div className="space-y-1.5 text-xs">
              <div className="flex items-start gap-2">
                <Lightbulb className="w-3.5 h-3.5 text-brand-400 shrink-0 mt-0.5" />
                <div className="min-w-0">
                  <span className="text-brand-400 font-semibold">Thought: </span>
                  <span className="text-slate-300">{s.thought}</span>
                </div>
              </div>
              <div className="flex items-start gap-2">
                <Zap className="w-3.5 h-3.5 text-accent-green shrink-0 mt-0.5" />
                <div className="min-w-0">
                  <span className="text-accent-green font-semibold">
                    Action:{" "}
                  </span>
                  <code className="text-accent-green bg-accent-green/10 border border-accent-green/30 rounded px-1.5 py-0.5 text-[11px] font-mono">
                    {s.action}
                  </code>
                  {s.action_input && (
                    <span className="text-slate-400 ml-2">
                      —{" "}
                      {typeof s.action_input === "object"
                        ? JSON.stringify(s.action_input)
                        : s.action_input}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex items-start gap-2">
                <Eye className="w-3.5 h-3.5 text-accent-blue shrink-0 mt-0.5" />
                <div className="min-w-0">
                  <span className="text-accent-blue font-semibold">
                    Observation:{" "}
                  </span>
                  <span className="text-slate-400">
                    {typeof s.observation === "object"
                      ? JSON.stringify(s.observation)
                      : truncate(s.observation, 300)}
                  </span>
                </div>
              </div>
            </div>
          </li>
        ))}
      </ol>
    </Collapsible>
  );
}
