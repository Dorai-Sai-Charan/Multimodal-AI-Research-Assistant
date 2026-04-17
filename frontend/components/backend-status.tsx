"use client";

import { useEffect, useState } from "react";
import { Tooltip } from "./ui/tooltip";
import { cn } from "@/lib/utils";

type Status = "checking" | "online" | "offline";

export function BackendStatus({ compact = false }: { compact?: boolean }) {
  const [status, setStatus] = useState<Status>("checking");
  const [lastPing, setLastPing] = useState<number | null>(null);

  useEffect(() => {
    let mounted = true;
    const check = async () => {
      const t0 = performance.now();
      try {
        const res = await fetch("/api/health", { cache: "no-store" });
        if (!mounted) return;
        setStatus(res.ok ? "online" : "offline");
        setLastPing(Math.round(performance.now() - t0));
      } catch {
        if (mounted) setStatus("offline");
      }
    };
    check();
    const id = setInterval(check, 15000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, []);

  const color =
    status === "online"
      ? "bg-accent-green shadow-[0_0_8px_rgba(52,211,153,0.6)]"
      : status === "offline"
        ? "bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.6)]"
        : "bg-accent-amber shadow-[0_0_8px_rgba(251,191,36,0.5)]";

  const label =
    status === "online"
      ? `Backend online · ${lastPing}ms`
      : status === "offline"
        ? "Backend offline — run `python -m src.main`"
        : "Checking backend…";

  if (compact) {
    return (
      <Tooltip content={label} side="bottom">
        <span className={cn("w-2 h-2 rounded-full shrink-0", color)} />
      </Tooltip>
    );
  }

  return (
    <Tooltip content={label} side="bottom">
      <div className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-bg-elevated/60 border border-border">
        <span className={cn("w-1.5 h-1.5 rounded-full", color)} />
        <span className="text-[10px] uppercase tracking-wide text-slate-400 font-medium">
          {status}
        </span>
      </div>
    </Tooltip>
  );
}
