"use client";

import { Info } from "lucide-react";
import { Tooltip } from "./tooltip";

export function InfoTip({
  content,
  side = "top",
}: {
  content: React.ReactNode;
  side?: "top" | "bottom" | "left" | "right";
}) {
  return (
    <Tooltip content={content} side={side}>
      <Info className="w-3.5 h-3.5 text-slate-500 hover:text-brand-300 transition-colors cursor-help" />
    </Tooltip>
  );
}
