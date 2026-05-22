"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  MessageSquare,
  GitCompareArrows,
  BookOpen,
  Search,
  TrendingUp,
  Microscope,
  Sparkles,
  Sun,
  Moon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { ModelSettings } from "./model-settings";
import { UploadPanel } from "./upload-panel";
import { DocumentList, DocumentStats } from "./document-list";
import { BackendStatus } from "./backend-status";
import { HelpButton } from "./help-dialog";

const NAV = [
  {
    href: "/",
    label: "Chat Assistant",
    icon: MessageSquare,
    hint: "Conversational Q&A",
  },
  {
    href: "/compare",
    label: "Compare Papers",
    icon: GitCompareArrows,
    hint: "Side-by-side analysis",
  },
  {
    href: "/survey",
    label: "Survey & Gaps",
    icon: BookOpen,
    hint: "Literature synthesis",
  },
  {
    href: "/search",
    label: "Search & Explain",
    icon: Search,
    hint: "Semantic + grounded",
  },
  {
    href: "/trends",
    label: "Trends & Recommend",
    icon: TrendingUp,
    hint: "Analytics + suggestions",
  },
  {
    href: "/humanizer",
    label: "Text Humanizer",
    icon: Sparkles,
    hint: "AI detection & humanization",
  },
];

const BADGES = ["RAG", "Agentic AI", "Multimodal", "Multi-hop", "Semantic"];

export function Sidebar() {
  const pathname = usePathname();
  const theme = useAppStore((s) => s.theme);
  const toggleTheme = useAppStore((s) => s.toggleTheme);
  return (
    <aside className="w-[240px] lg:w-[340px] shrink-0 h-screen sticky top-0 glass-strong border-r border-border flex flex-col">
      {/* Header */}
      <div className="p-5 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="absolute inset-0 bg-gradient-brand blur-xl opacity-60 rounded-xl" />
            <div className="relative w-10 h-10 rounded-xl bg-gradient-brand flex items-center justify-center shadow-lg shadow-brand-600/30">
              <Microscope className="w-5 h-5 text-white" />
            </div>
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-lg font-bold gradient-text leading-tight truncate">
              Research Assistant
            </h1>
            <p className="text-[11px] text-slate-400">
              Multimodal · Agentic · RAG
            </p>
          </div>
          <div className="flex items-center gap-1">
            <BackendStatus compact />
            <HelpButton />
            <button
              onClick={toggleTheme}
              title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
              className="p-1.5 rounded-lg hover:bg-bg-elevated text-slate-400 hover:text-slate-200 transition-colors"
              aria-label="Toggle theme"
            >
              {theme === "dark" ? (
                <Sun className="w-4 h-4" />
              ) : (
                <Moon className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-1">
          {BADGES.map((b) => (
            <span key={b} className="badge">
              {b}
            </span>
          ))}
        </div>
      </div>

      {/* Nav */}
      <nav className="px-3 py-3 border-b border-border">
        <p className="px-2 mb-1.5 text-[10px] uppercase tracking-[0.14em] text-slate-500 font-semibold">
          Workspace
        </p>
        <ul className="space-y-0.5">
          {NAV.map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    "group flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all",
                    active
                      ? "bg-gradient-brand text-white shadow-md shadow-brand-600/20 font-semibold"
                      : "text-slate-400 hover:text-slate-100 hover:bg-bg-elevated",
                  )}
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="leading-tight">{item.label}</div>
                    <div
                      className={cn(
                        "text-[10px] font-normal leading-tight",
                        active ? "text-white/80" : "text-slate-500",
                      )}
                    >
                      {item.hint}
                    </div>
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Scroll area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <ModelSettings />
        <div>
          <p className="text-xs font-semibold text-slate-300 uppercase tracking-wide mb-2">
            Upload Document
          </p>
          <UploadPanel />
        </div>
        <div className="h-px bg-border" />
        <DocumentList />
        <div className="h-px bg-border" />
        <DocumentStats />
      </div>
    </aside>
  );
}
