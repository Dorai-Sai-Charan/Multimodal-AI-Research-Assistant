import type { LucideIcon } from "lucide-react";

interface PageHeaderProps {
  title: string;
  subtitle: string;
  icon: LucideIcon;
  iconColor?: string;
}

export function PageHeader({ title, subtitle, icon: Icon, iconColor = "text-brand-300" }: PageHeaderProps) {
  return (
    <div className="mb-6 flex items-start gap-4">
      <div className={`w-12 h-12 rounded-xl bg-gradient-brand flex items-center justify-center shrink-0 shadow-lg shadow-brand-600/30`}>
        <Icon className={`w-6 h-6 text-white`} />
      </div>
      <div className="min-w-0">
        <h1 className="text-2xl font-bold gradient-text leading-tight">{title}</h1>
        <p className="text-sm text-slate-400 mt-1">{subtitle}</p>
      </div>
    </div>
  );
}

export function ResultCard({
  children,
  loading,
  error,
  placeholder,
}: {
  children?: React.ReactNode;
  loading?: boolean;
  error?: string | null;
  placeholder?: React.ReactNode;
}) {
  if (loading) {
    return (
      <div className="glass rounded-xl p-6">
        <div className="shimmer h-4 rounded bg-bg-elevated mb-3 w-3/4" />
        <div className="shimmer h-3 rounded bg-bg-elevated mb-2 w-full" />
        <div className="shimmer h-3 rounded bg-bg-elevated mb-2 w-11/12" />
        <div className="shimmer h-3 rounded bg-bg-elevated mb-2 w-5/6" />
        <div className="shimmer h-3 rounded bg-bg-elevated w-2/3" />
      </div>
    );
  }
  if (error) {
    return (
      <div className="glass rounded-xl p-4 border-red-500/30 bg-red-500/5 text-red-300 text-sm">
        {error}
      </div>
    );
  }
  if (children) {
    return <div className="animate-fade-in">{children}</div>;
  }
  if (placeholder) {
    return (
      <div className="glass rounded-xl p-8 text-center text-sm text-slate-500">
        {placeholder}
      </div>
    );
  }
  return null;
}
