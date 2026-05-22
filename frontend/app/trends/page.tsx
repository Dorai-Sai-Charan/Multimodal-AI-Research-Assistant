"use client";

import { useState } from "react";
import {
  TrendingUp,
  Star,
  ClipboardList,
  Brain,
  Zap,
  FlaskConical,
  Compass,
} from "lucide-react";
import { PageHeader, ResultCard } from "@/components/page-header";
import { ResultView } from "@/components/result-view";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Tabs } from "@/components/ui/tabs";
import { InfoTip } from "@/components/ui/info-tip";
import { ExamplePrompts, type ExamplePrompt } from "@/components/example-prompts";
import { useDocumentsPolling, useTunablePayload, useAsync } from "@/lib/hooks";
import { recommendPapers, researchTrends, summarize } from "@/lib/api";
import { NoDocumentsState } from "@/components/no-documents-state";

const INTEREST_EXAMPLES: ExamplePrompt[] = [
  {
    icon: Brain,
    title: "Agentic RAG",
    prompt:
      "I'm interested in agentic retrieval-augmented generation for scientific documents with multi-hop reasoning.",
  },
  {
    icon: Zap,
    title: "Fast inference",
    prompt:
      "I'm researching efficient inference techniques and model distillation for latency-critical applications.",
  },
  {
    icon: FlaskConical,
    title: "Evaluation & benchmarks",
    prompt:
      "I'm interested in evaluation methodologies and benchmark design for multimodal QA systems.",
  },
  {
    icon: Compass,
    title: "Novel architectures",
    prompt:
      "I want to explore novel transformer architectures and attention mechanisms for long-context understanding.",
  },
];

export default function TrendsPage() {
  const [tab, setTab] = useState("trends");
  return (
    <>
      <PageHeader
        title="Trends & Recommendations"
        subtitle="Surface emerging directions across your papers, get personalised recommendations, or summarise any paper."
        icon={TrendingUp}
      />
      <Tabs
        value={tab}
        onChange={setTab}
        variant="underline"
        tabs={[
          { value: "trends", label: "Research Trends", icon: <TrendingUp className="w-4 h-4" /> },
          { value: "recommend", label: "Recommendations", icon: <Star className="w-4 h-4" /> },
          { value: "summary", label: "Summarize", icon: <ClipboardList className="w-4 h-4" /> },
        ]}
        className="mb-5"
      />
      {tab === "trends" && <TrendsTab />}
      {tab === "recommend" && <RecommendTab />}
      {tab === "summary" && <SummaryTab />}
    </>
  );
}

function TrendsTab() {
  const { documents } = useDocumentsPolling();
  const tunable = useTunablePayload();
  const completed = documents.filter((d) => d.status === "completed");
  const { data, error, loading, run } = useAsync(researchTrends);

  if (completed.length === 0) return <NoDocumentsState feature="Trends Analysis" />;

  return (
    <>
      <div className="glass rounded-2xl p-6 mb-5 shadow-xl shadow-black/20">
        <div className="flex items-center gap-1.5 mb-3">
          <span className="label">Analyse across the whole corpus</span>
          <InfoTip content="Multi-query retrieval (methodology, results, datasets) — deduplicated, 8000-char context, trend analysis prompt." />
        </div>
        <p className="text-sm text-slate-300 mb-2 leading-relaxed">
          Surface methodological evolution, performance improvements, and
          emerging directions across <strong>all</strong> uploaded papers.
        </p>
        <div className="grid grid-cols-3 gap-2 mb-5">
          {[
            { label: "Methodology", icon: Brain },
            { label: "Results", icon: TrendingUp },
            { label: "Datasets", icon: FlaskConical },
          ].map((x) => {
            const Icon = x.icon;
            return (
              <div
                key={x.label}
                className="flex flex-col items-center gap-1 p-3 rounded-lg bg-bg-subtle border border-border"
              >
                <Icon className="w-4 h-4 text-brand-300" />
                <span className="text-[11px] text-slate-300 font-medium">
                  {x.label}
                </span>
              </div>
            );
          })}
        </div>
        <Button
          variant="primary"
          fullWidth
          disabled={loading}
          onClick={() => run(tunable)}
        >
          <TrendingUp className="w-4 h-4" />
          Analyse research trends
        </Button>
      </div>
      <ResultCard
        loading={loading}
        error={error}
        placeholder={
          <span>
            Run trend analysis to see how methodologies and results are
            evolving across your collection.
          </span>
        }
      >
        {data && <ResultView data={data} modeLabel="Trends" />}
      </ResultCard>
    </>
  );
}

function RecommendTab() {
  const { documents } = useDocumentsPolling();
  const tunable = useTunablePayload();
  const completed = documents.filter((d) => d.status === "completed");
  const [interest, setInterest] = useState("");
  const { data, error, loading, run } = useAsync(recommendPapers);

  if (completed.length === 0) return <NoDocumentsState feature="Paper Recommendations" />;

  return (
    <>
      <div className="glass rounded-2xl p-6 mb-5 space-y-5 shadow-xl shadow-black/20">
        <div>
          <div className="flex items-center gap-1.5 mb-1.5">
            <label className="text-sm font-medium text-slate-300">
              Your research interest
            </label>
            <InfoTip content="Interest-based retrieval (top-20) followed by a recommendation prompt. Describe your focus in 1–3 sentences for best results." />
          </div>
          <Textarea
            value={interest}
            onChange={(e) => setInterest(e.target.value)}
            placeholder="e.g. I'm interested in retrieval-augmented generation for scientific documents"
            rows={3}
          />
        </div>

        <ExamplePrompts
          prompts={INTEREST_EXAMPLES}
          onPick={setInterest}
          heading="Starter interests"
          columns={2}
        />

        <Button
          variant="primary"
          fullWidth
          disabled={loading || !interest.trim()}
          onClick={() => run({ ...tunable, interest })}
        >
          <Star className="w-4 h-4" />
          Get recommendations
        </Button>
      </div>
      <ResultCard
        loading={loading}
        error={error}
        placeholder={
          <span>
            Describe your interest — the assistant will rank the most relevant
            uploaded papers.
          </span>
        }
      >
        {data && <ResultView data={data} modeLabel="Recommendations" />}
      </ResultCard>
    </>
  );
}

function SummaryTab() {
  const { documents } = useDocumentsPolling();
  const tunable = useTunablePayload();
  const completed = documents.filter((d) => d.status === "completed");
  if (completed.length === 0) return <NoDocumentsState feature="Paper Summarization" />;
  const [source, setSource] = useState("__all__");
  const { data, error, loading, run } = useAsync(summarize);
  return (
    <>
      <div className="glass rounded-2xl p-6 mb-5 space-y-5 shadow-xl shadow-black/20">
        <div>
          <div className="flex items-center gap-1.5 mb-1.5">
            <label className="text-sm font-medium text-slate-300">
              Paper to summarize
            </label>
            <InfoTip content="Broad retrieval (top-20) with a dedicated summarization prompt. Pick one paper for a focused summary, or all papers for a corpus overview." />
          </div>
          <Select
            value={source}
            onChange={setSource}
            options={[
              { value: "__all__", label: "All papers" },
              ...completed.map((d) => ({
                value: d.filename,
                label: d.filename,
              })),
            ]}
          />
        </div>
        <Button
          variant="primary"
          fullWidth
          disabled={loading}
          onClick={() =>
            run({
              ...tunable,
              source_file: source === "__all__" ? null : source,
              top_k: 20,
            })
          }
        >
          <ClipboardList className="w-4 h-4" />
          Summarize
        </Button>
      </div>
      <ResultCard
        loading={loading}
        error={error}
        placeholder={
          <span>
            Pick a paper (or all papers) and generate a concise structured
            summary.
          </span>
        }
      >
        {data && <ResultView data={data} modeLabel="Summary" />}
      </ResultCard>
    </>
  );
}
