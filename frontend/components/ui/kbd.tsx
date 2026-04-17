import { cn } from "@/lib/utils";

export function Kbd({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <kbd
      className={cn(
        "inline-flex items-center justify-center min-w-[20px] px-1.5 py-0.5 rounded",
        "bg-bg-elevated border border-border text-[10px] font-mono text-slate-300",
        "shadow-[0_1px_0_0_rgba(0,0,0,0.3)]",
        className,
      )}
    >
      {children}
    </kbd>
  );
}
