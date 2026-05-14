"use client";

import { useState } from "react";
import { Sparkles, ScanText, Copy, Check } from "lucide-react";
import { PageHeader, ResultCard } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { useAsync } from "@/lib/hooks";
import { detectAI, humanizeText } from "@/lib/api";
import type { AIDetectionResponse, HumanizationResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

function ScoreBadge({ score }: { score: number }) {
  const isHuman = score < 30;
  const isMixed = score < 70;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-semibold",
        isHuman
          ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
          : isMixed
            ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
            : "bg-red-500/20 text-red-300 border border-red-500/30",
      )}
    >
      <span
        className={cn(
          "w-2 h-2 rounded-full",
          isHuman ? "bg-emerald-400" : isMixed ? "bg-amber-400" : "bg-red-400",
        )}
      />
      {isHuman ? "Human" : isMixed ? "Mixed" : "AI-Generated"}
    </span>
  );
}

function MetricCard({
  label,
  value,
  suffix = "%",
}: {
  label: string;
  value: number;
  suffix?: string;
}) {
  return (
    <div className="glass rounded-xl p-4 text-center">
      <div className="text-xl font-bold gradient-text">
        {value.toFixed(1)}
        {suffix}
      </div>
      <div className="text-xs text-slate-400 mt-1">{label}</div>
    </div>
  );
}

function DetectionResult({ data }: { data: AIDetectionResponse }) {
  const metrics = data.metrics ?? null;

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="glass rounded-2xl p-5 shadow-xl shadow-black/20">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-slate-200">
            AI Detection Result
          </h3>
          <ScoreBadge score={data.ai_percentage} />
        </div>

        <div
          className={cn(
            "grid gap-3 mb-4",
            data.heuristic_score != null && data.roberta_score != null
              ? "grid-cols-3"
              : "grid-cols-1",
          )}
        >
          <MetricCard label="Blended Score" value={data.ai_percentage} />
          {data.heuristic_score != null && (
            <MetricCard label="Heuristic Score" value={data.heuristic_score} />
          )}
          {data.roberta_score != null && (
            <MetricCard label="RoBERTa Score" value={data.roberta_score} />
          )}
        </div>

        <div className="mb-4">
          <div className="flex justify-between text-xs text-slate-500 mb-1.5">
            <span>Human (0%)</span>
            <span>AI (100%)</span>
          </div>
          <div className="h-2 bg-bg-elevated rounded-full overflow-hidden">
            <div
              className={cn(
                "h-full rounded-full transition-all duration-700",
                data.ai_percentage < 30
                  ? "bg-emerald-500"
                  : data.ai_percentage < 70
                    ? "bg-amber-500"
                    : "bg-red-500",
              )}
              style={{ width: `${data.ai_percentage}%` }}
            />
          </div>
        </div>

        <p className="text-sm text-slate-300 leading-relaxed">
          {data.explanation}
        </p>

        {metrics && (
          <div className="mt-4 border-t border-border pt-4">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">
              Text Metrics
            </p>
            <div className="grid grid-cols-3 gap-3">
              {metrics.burstiness != null && (
                <MetricCard
                  label="Burstiness"
                  value={metrics.burstiness}
                  suffix=""
                />
              )}
              {metrics.avg_sentence_length != null && (
                <MetricCard
                  label="Avg Sentence Length"
                  value={metrics.avg_sentence_length}
                  suffix=" words"
                />
              )}
              {metrics.ttr != null && (
                <MetricCard
                  label="Lexical Diversity"
                  value={metrics.ttr * 100}
                />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function HumanizationResult({ data }: { data: HumanizationResponse }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    await navigator.clipboard.writeText(data.humanized_text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const hasScores = data.original_score != null && data.new_score != null;

  return (
    <div className="space-y-4 animate-fade-in">
      {hasScores && (
        <div
          className={cn(
            "glass rounded-xl p-4 border flex items-start gap-3",
            data.target_reached
              ? "border-emerald-500/30 bg-emerald-500/5"
              : "border-amber-500/30 bg-amber-500/5",
          )}
        >
          <span
            className={cn(
              "text-lg font-bold mt-0.5 shrink-0",
              data.target_reached ? "text-emerald-300" : "text-amber-300",
            )}
          >
            {data.target_reached ? "✓" : "~"}
          </span>
          <div>
            <p
              className={cn(
                "text-sm font-semibold",
                data.target_reached ? "text-emerald-300" : "text-amber-300",
              )}
            >
              {data.target_reached ? "Target reached" : "Partially humanized"}
            </p>
            <p className="text-xs text-slate-400 mt-0.5">
              AI score reduced: {data.original_score!.toFixed(1)}% →{" "}
              {data.new_score!.toFixed(1)}%
              {data.passes_used != null &&
                ` · ${data.passes_used} pass${data.passes_used !== 1 ? "es" : ""} used`}
            </p>
          </div>
        </div>
      )}

      <div className="glass rounded-2xl p-5 shadow-xl shadow-black/20">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-slate-200">
            Humanized Text
          </h3>
          <button
            onClick={copy}
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors px-2.5 py-1.5 rounded-lg hover:bg-bg-elevated"
          >
            {copied ? (
              <Check className="w-3.5 h-3.5 text-emerald-400" />
            ) : (
              <Copy className="w-3.5 h-3.5" />
            )}
            {copied ? "Copied!" : "Copy"}
          </button>
        </div>
        <div className="bg-bg-elevated rounded-xl p-4 text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">
          {data.humanized_text}
        </div>
      </div>

      {hasScores && (
        <div className="glass rounded-2xl p-5 shadow-xl shadow-black/20">
          <h3 className="text-sm font-semibold text-slate-200 mb-4">
            Score Comparison
          </h3>
          <div className="grid grid-cols-2 gap-6">
            <div className="text-center">
              <div className="text-xs text-slate-400 mb-2 uppercase tracking-wide">
                Before
              </div>
              <div className="text-3xl font-bold text-red-300">
                {data.original_score!.toFixed(1)}%
              </div>
              <div className="text-xs text-slate-500 mt-1">AI score</div>
            </div>
            <div className="text-center">
              <div className="text-xs text-slate-400 mb-2 uppercase tracking-wide">
                After
              </div>
              <div
                className={cn(
                  "text-3xl font-bold",
                  data.new_score! < 30
                    ? "text-emerald-300"
                    : data.new_score! < 70
                      ? "text-amber-300"
                      : "text-red-300",
                )}
              >
                {data.new_score!.toFixed(1)}%
              </div>
              <div className="text-xs text-slate-500 mt-1">AI score</div>
            </div>
          </div>
        </div>
      )}

      {data.changes_made && (
        <div className="glass rounded-2xl p-5 shadow-xl shadow-black/20">
          <h3 className="text-sm font-semibold text-slate-200 mb-3">
            Changes Made
          </h3>
          <p className="text-sm text-slate-300 leading-relaxed">
            {data.changes_made}
          </p>
        </div>
      )}
    </div>
  );
}

export default function HumanizerPage() {
  const [text, setText] = useState("");
  const {
    data: detection,
    error: detectionError,
    loading: detecting,
    run: runDetect,
  } = useAsync(detectAI);
  const {
    data: humanized,
    error: humanizeError,
    loading: humanizing,
    run: runHumanize,
  } = useAsync(humanizeText);

  const canRun = text.trim().length > 20;

  return (
    <>
      <PageHeader
        title="Text Humanizer"
        subtitle="Detect AI-generated content and rewrite it to sound more natural and human."
        icon={Sparkles}
      />

      <div className="glass rounded-2xl p-6 mb-5 shadow-xl shadow-black/20">
        <div className="mb-4">
          <label className="text-xs text-slate-400 font-medium block mb-1.5">
            Paste your text
          </label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste the text you want to analyze or humanize…"
            rows={8}
            className="w-full bg-bg-elevated border border-border rounded-xl px-4 py-3 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-brand-500 resize-y"
          />
          <div className="text-right text-xs text-slate-500 mt-1">
            {text.length.toLocaleString()} characters
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Button
            variant="secondary"
            disabled={!canRun || detecting || humanizing}
            onClick={() => runDetect({ text })}
          >
            <ScanText className="w-4 h-4" />
            {detecting ? "Detecting…" : "Detect AI"}
          </Button>
          <Button
            variant="primary"
            disabled={!canRun || humanizing || detecting}
            onClick={() => runHumanize({ text })}
          >
            <Sparkles className="w-4 h-4" />
            {humanizing ? "Humanizing…" : "Humanize"}
          </Button>
        </div>

        {!canRun && text.length > 0 && (
          <p className="text-[11px] text-slate-500 mt-2 text-center">
            Enter at least 20 characters to continue.
          </p>
        )}
        <p className="text-[11px] text-slate-500 mt-2 text-center">
          Humanization runs up to 3 iterative passes and typically takes
          30–90 seconds.
        </p>
      </div>

      <ResultCard
        loading={detecting}
        error={detectionError}
        placeholder={
          <span>
            Paste text and click{" "}
            <span className="text-brand-300 font-medium">Detect AI</span> to
            analyze it, or{" "}
            <span className="text-brand-300 font-medium">Humanize</span> to
            rewrite it.
          </span>
        }
      >
        {detection && <DetectionResult data={detection} />}
      </ResultCard>

      {(humanized || humanizeError || humanizing) && (
        <div className="mt-4">
          <ResultCard loading={humanizing} error={humanizeError}>
            {humanized && <HumanizationResult data={humanized} />}
          </ResultCard>
        </div>
      )}
    </>
  );
}
