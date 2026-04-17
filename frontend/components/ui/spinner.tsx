import { cn } from "@/lib/utils";

export function Spinner({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "inline-block w-4 h-4 border-2 border-brand-400/30 border-t-brand-400 rounded-full animate-spin",
        className,
      )}
    />
  );
}

export function ThinkingDots() {
  return (
    <div className="inline-flex gap-1 items-center">
      <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-bounce [animation-delay:-0.3s]" />
      <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-bounce [animation-delay:-0.15s]" />
      <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-bounce" />
    </div>
  );
}
