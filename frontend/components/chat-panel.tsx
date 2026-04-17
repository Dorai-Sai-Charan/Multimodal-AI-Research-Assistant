"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  SendHorizonal,
  Bot,
  User,
  Trash2,
  Sparkles,
  Layers3,
  Globe,
  Copy,
  Check,
  BookOpenCheck,
  Gauge,
  Network,
  Quote,
  Cpu,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { Toggle } from "./ui/toggle";
import { Select } from "./ui/select";
import { Button } from "./ui/button";
import { ThinkingDots } from "./ui/spinner";
import { Tooltip } from "./ui/tooltip";
import { Kbd } from "./ui/kbd";
import { Markdown } from "./markdown";
import { Citations } from "./citations";
import { ReasoningSteps } from "./reasoning-steps";
import { ExamplePrompts, type ExamplePrompt } from "./example-prompts";
import { useAppStore } from "@/lib/store";
import { useDocumentsPolling, useTunablePayload } from "@/lib/hooks";
import { agentQuery, multiDocQuery, query } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";
import { cn } from "@/lib/utils";

const EXAMPLE_PROMPTS: ExamplePrompt[] = [
  {
    icon: BookOpenCheck,
    title: "Explain the core idea",
    prompt: "Explain the core idea and main contributions of this paper in simple terms.",
  },
  {
    icon: Gauge,
    title: "Summarise results",
    prompt: "Summarise the experimental results and key performance numbers reported in the paper.",
  },
  {
    icon: Network,
    title: "Methodology",
    prompt: "Walk me through the methodology: architecture, datasets, training setup, and evaluation.",
  },
  {
    icon: Quote,
    title: "Limitations & future work",
    prompt: "What limitations does the paper acknowledge and what future directions does it suggest?",
  },
];

export function ChatPanel() {
  const messages = useAppStore((s) => s.messages);
  const pushMessage = useAppStore((s) => s.pushMessage);
  const clearMessages = useAppStore((s) => s.clearMessages);
  const agentMode = useAppStore((s) => s.agentMode);
  const setAgentMode = useAppStore((s) => s.setAgentMode);
  const multiDocMode = useAppStore((s) => s.multiDocMode);
  const setMultiDocMode = useAppStore((s) => s.setMultiDocMode);
  const settings = useAppStore((s) => s.settings);
  const catalogue = useAppStore((s) => s.catalogue);

  const tunable = useTunablePayload();
  const { documents } = useDocumentsPolling();

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingStage, setLoadingStage] = useState("");
  const [filter, setFilter] = useState<string>("__all__");
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const completedDocs = documents.filter((d) => d.status === "completed");
  const activeModel = catalogue.models.find((m) => m.id === settings.model);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages.length, loading, loadingStage]);

  useEffect(() => {
    if (!textareaRef.current) return;
    const ta = textareaRef.current;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`;
  }, [input]);

  useEffect(() => {
    if (!loading) {
      setLoadingStage("");
      return;
    }
    const stages = agentMode
      ? [
          "Planning reasoning steps…",
          "Retrieving document chunks…",
          "Reasoning over evidence…",
          "Synthesising final answer…",
        ]
      : multiDocMode
        ? [
            "Searching across all papers…",
            "Ranking relevant passages…",
            "Synthesising cross-paper answer…",
          ]
        : [
            "Embedding your question…",
            "Retrieving top chunks…",
            "Generating answer with citations…",
          ];
    let i = 0;
    setLoadingStage(stages[0]);
    const id = setInterval(() => {
      i = Math.min(i + 1, stages.length - 1);
      setLoadingStage(stages[i]);
    }, 1400);
    return () => clearInterval(id);
  }, [loading, agentMode, multiDocMode]);

  const onToggleAgent = (v: boolean) => {
    setAgentMode(v);
    if (v) setMultiDocMode(false);
  };
  const onToggleMulti = (v: boolean) => {
    setMultiDocMode(v);
    if (v) setAgentMode(false);
  };

  const sendQuestion = async (questionText: string) => {
    const q = questionText.trim();
    if (!q || loading) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: q,
    };
    pushMessage(userMsg);

    setLoading(true);
    try {
      const history = [...messages, userMsg]
        .slice(0, -1)
        .map((m) => ({ role: m.role, content: m.content }));

      let content = "";
      let citations: ChatMessage["citations"] = [];
      let reasoning: ChatMessage["reasoning_steps"] | undefined;
      let chunks_used = 0;
      let total_steps: number | undefined;
      let mode: ChatMessage["mode"] = "rag";

      if (agentMode) {
        mode = "agent";
        const resp = await agentQuery({
          ...tunable,
          question: q,
          chat_history: history,
        });
        content = resp.answer;
        citations = resp.citations;
        reasoning = resp.reasoning_steps;
        chunks_used = resp.chunks_used;
        total_steps = resp.total_steps;
      } else if (multiDocMode) {
        mode = "multi-doc";
        const resp = await multiDocQuery({ ...tunable, question: q });
        content = resp.answer;
        citations = resp.citations;
        chunks_used = resp.chunks_used;
      } else {
        const resp = await query({
          ...tunable,
          question: q,
          top_k: settings.top_k,
          filter_source: filter === "__all__" ? null : filter,
        });
        content = resp.answer;
        citations = resp.citations;
        chunks_used = resp.chunks_used;
      }

      pushMessage({
        id: crypto.randomUUID(),
        role: "assistant",
        content,
        citations,
        reasoning_steps: reasoning,
        chunks_used,
        total_steps,
        mode,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      pushMessage({
        id: crypto.randomUUID(),
        role: "assistant",
        content: `**Error:** ${msg}`,
        error: true,
      });
      toast.error("Request failed", { description: msg });
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = input.trim();
    if (!q || loading) return;
    setInput("");
    await sendQuestion(q);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as React.FormEvent);
    }
  };

  const copyMessage = async (id: string, content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 1500);
    } catch {
      toast.error("Clipboard access denied");
    }
  };

  const handleClear = () => {
    clearMessages();
    toast.success("Conversation cleared");
  };

  const modeBanner = useMemo(() => {
    if (agentMode)
      return {
        label: "Agent · Multi-hop ReAct",
        color: "text-brand-300 bg-brand-500/10 border-brand-500/30",
      };
    if (multiDocMode)
      return {
        label: "Multi-doc · Cross-paper reasoning",
        color: "text-accent-cyan bg-accent-cyan/10 border-accent-cyan/30",
      };
    return {
      label: "RAG · Single-shot retrieval",
      color: "text-slate-300 bg-bg-elevated border-border",
    };
  }, [agentMode, multiDocMode]);

  return (
    <div className="flex flex-col h-[calc(100vh-7rem)] gap-4">
      {/* Controls */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <Toggle
          checked={agentMode}
          onChange={onToggleAgent}
          label="Agent Mode"
          description="Multi-hop ReAct reasoning"
          icon={<Sparkles className="w-4 h-4" />}
        />
        <Toggle
          checked={multiDocMode}
          onChange={onToggleMulti}
          label="Multi-doc reasoning"
          description="Synthesize across papers"
          icon={<Layers3 className="w-4 h-4" />}
        />
        <div className="glass rounded-lg p-2.5 flex items-center gap-2">
          <div className="w-8 h-8 rounded-md bg-bg-subtle flex items-center justify-center text-slate-400 shrink-0">
            <Globe className="w-4 h-4" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[10px] text-slate-500 uppercase tracking-wide">
              Filter to paper
            </div>
            <Select
              value={filter}
              onChange={setFilter}
              options={[
                { value: "__all__", label: "All papers" },
                ...completedDocs.map((d) => ({
                  value: d.filename,
                  label: d.filename,
                })),
              ]}
              className="-mx-1"
            />
          </div>
        </div>
      </div>

      {/* Mode + model chip */}
      <div className="flex flex-wrap items-center gap-2 px-1">
        <span
          className={cn(
            "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium border",
            modeBanner.color,
          )}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
          {modeBanner.label}
        </span>
        {activeModel && (
          <Tooltip content={activeModel.best_for} side="bottom">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] text-slate-300 bg-bg-elevated border border-border">
              <Cpu className="w-3 h-3 text-brand-400" />
              {activeModel.label.split(" — ")[0]}
            </span>
          </Tooltip>
        )}
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] text-slate-400 bg-bg-elevated/60 border border-border">
          temp {settings.temperature.toFixed(2)} · top-k {settings.top_k}
        </span>
      </div>

      {/* Messages */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto glass rounded-2xl p-6 space-y-5 shadow-xl shadow-black/20"
      >
        {messages.length === 0 && !loading && (
          <WelcomeHero
            onPick={(p) => {
              setInput(p);
              setTimeout(() => textareaRef.current?.focus(), 50);
            }}
            completedCount={completedDocs.length}
          />
        )}

        <AnimatePresence initial={false}>
          {messages.map((m) => (
            <motion.div
              key={m.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className={cn(
                "flex gap-3",
                m.role === "user" ? "flex-row-reverse" : "flex-row",
              )}
            >
              <div
                className={cn(
                  "w-9 h-9 rounded-xl shrink-0 flex items-center justify-center",
                  m.role === "user"
                    ? "bg-brand-500/20 border border-brand-500/30 text-brand-300"
                    : "bg-gradient-brand text-white shadow-lg shadow-brand-600/30",
                )}
              >
                {m.role === "user" ? (
                  <User className="w-4 h-4" />
                ) : (
                  <Bot className="w-4 h-4" />
                )}
              </div>
              <div
                className={cn(
                  "group/msg relative min-w-0 flex-1 rounded-2xl px-4 py-3",
                  m.role === "user"
                    ? "bg-brand-500/10 border border-brand-500/30 max-w-[80%] ml-auto"
                    : m.error
                      ? "bg-red-500/5 border border-red-500/30"
                      : "bg-bg-subtle border border-border",
                )}
              >
                <Markdown content={m.content} />
                {m.role === "assistant" && (
                  <>
                    <Citations citations={m.citations ?? []} />
                    {m.reasoning_steps && (
                      <ReasoningSteps steps={m.reasoning_steps} />
                    )}
                    {(m.mode || m.chunks_used != null) && !m.error && (
                      <div className="mt-3 flex flex-wrap items-center gap-2 text-[10px] text-slate-500">
                        {m.mode && (
                          <span className="chip !text-[10px]">
                            {m.mode === "agent"
                              ? "Agent · multi-hop"
                              : m.mode === "multi-doc"
                                ? "Multi-doc"
                                : "RAG"}
                          </span>
                        )}
                        {m.chunks_used != null && (
                          <span>{m.chunks_used} chunks</span>
                        )}
                        {m.total_steps != null && (
                          <span>· {m.total_steps} steps</span>
                        )}
                      </div>
                    )}
                    <Tooltip content="Copy answer" side="left">
                      <button
                        onClick={() => copyMessage(m.id, m.content)}
                        className="absolute top-2 right-2 opacity-0 group-hover/msg:opacity-100 btn-ghost !p-1.5 transition-opacity"
                        aria-label="Copy"
                      >
                        {copiedId === m.id ? (
                          <Check className="w-3.5 h-3.5 text-accent-green" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </Tooltip>
                  </>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {loading && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex gap-3"
          >
            <div className="w-9 h-9 rounded-xl bg-gradient-brand flex items-center justify-center shadow-lg shadow-brand-600/30">
              <Bot className="w-4 h-4 text-white" />
            </div>
            <div className="px-4 py-3 rounded-2xl bg-bg-subtle border border-border flex items-center gap-3 min-w-[260px]">
              <ThinkingDots />
              <span className="text-xs text-slate-400">{loadingStage}</span>
            </div>
          </motion.div>
        )}
      </div>

      {/* Input */}
      <form
        onSubmit={handleSubmit}
        className="glass rounded-2xl p-2 flex gap-2 items-end shadow-lg shadow-black/20 focus-within:border-brand-500/50 focus-within:ring-2 focus-within:ring-brand-500/20 transition-all border border-border"
      >
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            agentMode
              ? "Ask a complex multi-hop question…"
              : multiDocMode
                ? "Ask a question spanning multiple papers…"
                : "Ask a question about your research papers…"
          }
          disabled={loading}
          rows={1}
          className="flex-1 bg-transparent border-0 focus:outline-none px-3 py-2.5 text-sm text-slate-100 placeholder:text-slate-500 resize-none min-h-[40px] max-h-[160px]"
        />
        <div className="flex items-center gap-1 pr-1">
          {messages.length > 0 && (
            <Tooltip content="Clear conversation" side="top">
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={handleClear}
                aria-label="Clear conversation"
              >
                <Trash2 className="w-4 h-4" />
              </Button>
            </Tooltip>
          )}
          <Button
            type="submit"
            variant="primary"
            size="md"
            disabled={!input.trim() || loading}
          >
            <SendHorizonal className="w-4 h-4" />
            Send
          </Button>
        </div>
      </form>

      <div className="flex items-center justify-between px-2 -mt-1 text-[10px] text-slate-500">
        <span>
          Press <Kbd>Enter</Kbd> to send · <Kbd>Shift</Kbd>+<Kbd>Enter</Kbd> for
          newline
        </span>
        <span>
          {messages.length > 0 &&
            `${messages.length} message${messages.length === 1 ? "" : "s"}`}
        </span>
      </div>
    </div>
  );
}

function WelcomeHero({
  onPick,
  completedCount,
}: {
  onPick: (prompt: string) => void;
  completedCount: number;
}) {
  const ready = completedCount > 0;
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="h-full flex flex-col items-center justify-center text-center gap-5 py-8"
    >
      <div className="relative">
        <div className="absolute inset-0 bg-gradient-brand blur-3xl opacity-30 rounded-full" />
        <div className="relative w-16 h-16 rounded-2xl bg-gradient-brand flex items-center justify-center shadow-2xl shadow-brand-600/40">
          <Bot className="w-8 h-8 text-white" />
        </div>
      </div>
      <div className="max-w-xl">
        <h2 className="text-2xl font-bold gradient-text">
          Welcome to your research assistant
        </h2>
        <p className="text-sm text-slate-400 mt-2 leading-relaxed">
          Ask grounded questions about your uploaded papers, or flip on{" "}
          <span className="text-brand-300 font-medium">Agent Mode</span> for
          multi-hop reasoning across tables, figures, equations, and text.
        </p>
      </div>

      {!ready && (
        <div className="max-w-md p-4 rounded-xl bg-accent-amber/5 border border-accent-amber/30 text-left flex gap-3">
          <span className="text-2xl leading-none">📄</span>
          <div>
            <div className="text-sm font-semibold text-accent-amber">
              No papers yet
            </div>
            <p className="text-xs text-slate-300 mt-0.5">
              Upload a PDF in the sidebar to get started. You can still explore
              the UI — answers will just have no sources.
            </p>
          </div>
        </div>
      )}

      <div className="w-full max-w-2xl">
        <ExamplePrompts
          prompts={EXAMPLE_PROMPTS}
          onPick={onPick}
          heading="Try an example"
        />
      </div>
    </motion.div>
  );
}
