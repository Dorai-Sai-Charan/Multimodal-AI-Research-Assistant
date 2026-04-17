"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "ghost" | "destructive";
type Size = "sm" | "md" | "lg" | "icon";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  fullWidth?: boolean;
}

const sizeClass: Record<Size, string> = {
  sm: "px-2.5 py-1 text-xs gap-1.5",
  md: "px-4 py-2 text-sm gap-2",
  lg: "px-5 py-2.5 text-base gap-2",
  icon: "h-9 w-9 text-sm",
};

const variantClass: Record<Variant, string> = {
  primary:
    "bg-gradient-brand text-white shadow-lg shadow-brand-600/20 hover:shadow-xl hover:shadow-brand-600/40 hover:scale-[1.02] active:scale-[0.98]",
  secondary:
    "bg-bg-elevated border border-border text-slate-200 hover:bg-bg-card hover:border-brand-500/50 active:scale-[0.98]",
  ghost: "text-slate-400 hover:text-slate-100 hover:bg-bg-elevated",
  destructive:
    "bg-red-500/10 border border-red-500/40 text-red-300 hover:bg-red-500/20",
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "secondary", size = "md", fullWidth, className, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center rounded-lg font-medium transition-all duration-150",
        "disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100",
        "focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:ring-offset-2 focus:ring-offset-bg",
        variantClass[variant],
        sizeClass[size],
        fullWidth && "w-full",
        className,
      )}
      {...props}
    />
  ),
);
Button.displayName = "Button";
