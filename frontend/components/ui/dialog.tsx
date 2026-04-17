"use client";

import { X } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { useEffect } from "react";
import { cn } from "@/lib/utils";

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  icon?: React.ReactNode;
  children: React.ReactNode;
  maxWidth?: string;
}

export function Dialog({
  open,
  onClose,
  title,
  subtitle,
  icon,
  children,
  maxWidth = "max-w-lg",
}: DialogProps) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", handler);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          onClick={onClose}
        >
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
          <motion.div
            initial={{ opacity: 0, y: 12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.98 }}
            transition={{ duration: 0.2 }}
            className={cn(
              "relative glass-strong rounded-2xl w-full shadow-2xl shadow-black/60",
              maxWidth,
            )}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start gap-3 p-5 border-b border-border">
              {icon && (
                <div className="w-10 h-10 rounded-lg bg-gradient-brand flex items-center justify-center shrink-0 shadow-lg shadow-brand-600/30">
                  {icon}
                </div>
              )}
              <div className="flex-1 min-w-0">
                <h3 className="text-base font-semibold text-slate-100">
                  {title}
                </h3>
                {subtitle && (
                  <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>
                )}
              </div>
              <button
                onClick={onClose}
                className="btn-ghost !p-1.5"
                aria-label="Close"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-5">{children}</div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
