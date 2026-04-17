"use client";

import * as React from "react";
import { ChevronDown } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

interface CollapsibleProps {
  title: React.ReactNode;
  children: React.ReactNode;
  defaultOpen?: boolean;
  icon?: React.ReactNode;
  className?: string;
  rightSlot?: React.ReactNode;
}

export function Collapsible({
  title,
  children,
  defaultOpen,
  icon,
  className,
  rightSlot,
}: CollapsibleProps) {
  const [open, setOpen] = React.useState(!!defaultOpen);
  return (
    <div className={cn("glass rounded-xl overflow-hidden", className)}>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-bg-elevated/50 transition-colors"
      >
        {icon && (
          <span className="w-7 h-7 rounded-md bg-brand-500/15 border border-brand-500/30 flex items-center justify-center text-brand-300 shrink-0">
            {icon}
          </span>
        )}
        <span className="flex-1 text-sm font-medium text-slate-200">{title}</span>
        {rightSlot}
        <ChevronDown
          className={cn(
            "w-4 h-4 text-slate-400 transition-transform",
            open && "rotate-180",
          )}
        />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 pt-1 border-t border-border/50">
              {children}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
