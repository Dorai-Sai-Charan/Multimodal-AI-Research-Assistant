"use client";

import { useEffect, useState } from "react";
import {
  HelpCircle,
  Keyboard,
  Upload,
  MessageSquare,
  Sparkles,
  GitCompareArrows,
} from "lucide-react";
import { Dialog } from "./ui/dialog";
import { Kbd } from "./ui/kbd";
import { Tooltip } from "./ui/tooltip";

const STEPS = [
  {
    icon: Upload,
    title: "Upload a research PDF",
    body: "Use the sidebar drop zone. Ingestion runs in the background — status turns green when ready.",
  },
  {
    icon: MessageSquare,
    title: "Ask questions in Chat",
    body: "Factual questions use single-shot RAG with citations. Flip on Agent Mode for multi-hop reasoning.",
  },
  {
    icon: Sparkles,
    title: "Tune the model",
    body: "Open Model Settings in the sidebar to pick a model, adjust temperature, top-k retrieval, and reasoning effort.",
  },
  {
    icon: GitCompareArrows,
    title: "Explore specialized tools",
    body: "Compare two papers, generate literature surveys, surface research gaps, or get recommendations — each tab targets a specific workflow.",
  },
];

export function HelpButton() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "?" && !isEditable(e.target)) {
        e.preventDefault();
        setOpen(true);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return (
    <>
      <Tooltip content={<span>Help & shortcuts · press <Kbd>?</Kbd></span>} side="bottom">
        <button
          onClick={() => setOpen(true)}
          className="btn-ghost !p-1.5"
          aria-label="Help"
        >
          <HelpCircle className="w-4 h-4" />
        </button>
      </Tooltip>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title="Quick start & shortcuts"
        subtitle="Everything you can do with the research assistant"
        icon={<HelpCircle className="w-5 h-5 text-white" />}
        maxWidth="max-w-2xl"
      >
        <div className="space-y-5">
          <section>
            <h4 className="label mb-2">Workflow</h4>
            <ol className="space-y-2">
              {STEPS.map((s, i) => {
                const Icon = s.icon;
                return (
                  <li
                    key={i}
                    className="flex gap-3 p-3 rounded-lg bg-bg-subtle border border-border"
                  >
                    <div className="w-8 h-8 rounded-lg bg-brand-500/15 border border-brand-500/30 text-brand-300 flex items-center justify-center shrink-0">
                      <Icon className="w-4 h-4" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm font-semibold text-slate-200">
                        {i + 1}. {s.title}
                      </div>
                      <div className="text-xs text-slate-400 mt-0.5 leading-relaxed">
                        {s.body}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ol>
          </section>

          <section>
            <h4 className="label mb-2 flex items-center gap-1.5">
              <Keyboard className="w-3.5 h-3.5" />
              Keyboard shortcuts
            </h4>
            <ul className="grid grid-cols-2 gap-2">
              {[
                { keys: ["Enter"], desc: "Send message" },
                { keys: ["Shift", "Enter"], desc: "Insert newline" },
                { keys: ["?"], desc: "Open this dialog" },
                { keys: ["Esc"], desc: "Close dialog" },
              ].map((s, i) => (
                <li
                  key={i}
                  className="flex items-center justify-between p-2.5 rounded-lg bg-bg-subtle border border-border"
                >
                  <span className="text-xs text-slate-300">{s.desc}</span>
                  <span className="flex gap-1">
                    {s.keys.map((k, j) => (
                      <Kbd key={j}>{k}</Kbd>
                    ))}
                  </span>
                </li>
              ))}
            </ul>
          </section>

          <section className="p-3 rounded-lg bg-brand-500/5 border border-brand-500/20">
            <p className="text-xs text-slate-300 leading-relaxed">
              <span className="text-brand-300 font-semibold">Pro tip:</span>{" "}
              Agent Mode is slower but handles multi-hop questions (&ldquo;What
              does paper A claim that contradicts paper B?&rdquo;). For quick
              factual lookups, keep it off.
            </p>
          </section>
        </div>
      </Dialog>
    </>
  );
}

function isEditable(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  const tag = el.tagName.toLowerCase();
  return (
    tag === "input" ||
    tag === "textarea" ||
    tag === "select" ||
    el.isContentEditable
  );
}
