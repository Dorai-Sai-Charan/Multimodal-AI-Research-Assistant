"use client";

import { useState } from "react";
import {
  BookOpen,
  ScrollText,
  Telescope,
  Brain,
  Layers,
  Sparkles,
  FlaskConical,
} from "lucide-react";
import { PageHeader, ResultCard } from "@/components/page-header";
import { ResultView } from "@/components/result-view";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Tabs } from "@/components/ui/tabs";
import { InfoTip } from "@/components/ui/info-tip";
import { ExamplePrompts, type ExamplePrompt } from "@/components/example-prompts";
import { useDocumentsPolling, useTunablePayload, useAsync } from "@/lib/hooks";
import { literatureSurvey, researchGaps } from "@/lib/api";

const TOPIC_EXAMPLES: ExamplePrompt[] = [
  {
    icon: Brain,
    title: "Retrieval-Augmented Generation",
    prompt: "retrieval-augmented generation for scientific documents",
  },
  {
    icon: Layers,
    title: "Multimodal document understanding",
    prompt: "multimodal document understanding with vision-language models",
  },
  {
    icon: Sparkles,
    title: "Agentic reasoning",
    prompt: "agentic reasoning and ReAct-style multi-hop agents",
  },
  {
    icon: FlaskConical,
    title: "Evaluation methodologies",
    prompt: "evaluation methodologies and benchmarks for RAG systems",
  },
];

export default function SurveyPage() {
  const [tab, setTab] = useState("survey");
  return (
    <>
      <PageHeader
        title="Literature Survey & Research Gaps"
        subtitle="Generate a structured survey or uncover limitations and future directions across your papers."
        icon={BookOpen}
      />
      <Tabs
        value={tab}
        onChange={setTab}
        variant="underline"
        tabs={[
          {
            value: "survey",
            label: "Literature Survey",
            icon: <ScrollText className="w-4 h-4" />,
          },
          {
            value: "gaps",
            label: "Research Gaps",
            icon: <Telescope className="w-4 h-4" />,
          },
        ]}
        className="mb-5"
      />

      {tab === "survey" ? <SurveyTab /> : <GapsTab />}
    </>
  );
}

function SurveyTab() {
  const tunable = useTunablePayload();
  const [topic, setTopic] = useState("");
  const [topK, setTopK] = useState(30);
  const { data, error, loading, run } = useAsync(literatureSurvey);

  return (
    <>
      <div className="glass rounded-2xl p-6 mb-5 space-y-5 shadow-xl shadow-black/20">
        <div>
          <div className="flex items-center gap-1.5 mb-1.5">
            <label className="text-sm font-medium text-slate-300">
              Topic (optional)
            </label>
            <InfoTip content="Leave blank to survey broadly across all papers. Providing a topic narrows retrieval to that theme." />
          </div>
          <Input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. multimodal retrieval-augmented generation"
          />
        </div>

        <ExamplePrompts
          prompts={TOPIC_EXAMPLES}
          onPick={setTopic}
          heading="Quick topic ideas"
          columns={2}
        />

        <Slider
          label="Chunks to retrieve"
          value={topK}
          min={10}
          max={50}
          step={1}
          onChange={setTopK}
          help="More chunks = broader coverage but longer response time."
        />
        <Button
          variant="primary"
          fullWidth
          disabled={loading}
          onClick={() => run({ ...tunable, topic, top_k: topK })}
        >
          <ScrollText className="w-4 h-4" />
          Generate literature survey
        </Button>
      </div>
      <ResultCard
        loading={loading}
        error={error}
        placeholder={
          <span>
            Pick a topic (or leave blank) and generate a structured survey with
            citations.
          </span>
        }
      >
        {data && <ResultView data={data} modeLabel="Survey" />}
      </ResultCard>
    </>
  );
}

function GapsTab() {
  const { documents } = useDocumentsPolling();
  const tunable = useTunablePayload();
  const completed = documents.filter((d) => d.status === "completed");
  const [source, setSource] = useState("__all__");
  const { data, error, loading, run } = useAsync(researchGaps);

  return (
    <>
      <div className="glass rounded-2xl p-6 mb-5 space-y-5 shadow-xl shadow-black/20">
        <div>
          <div className="flex items-center gap-1.5 mb-1.5">
            <label className="text-sm font-medium text-slate-300">
              Focus on a specific paper
            </label>
            <InfoTip content="Leave on 'All papers' to aggregate gaps across your collection. Targeted retrieval queries: limitations, future work, challenges." />
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
        <div className="p-3 rounded-lg bg-bg-subtle border border-border text-xs text-slate-400 leading-relaxed">
          <span className="text-brand-300 font-semibold">Heads up:</span> Gap
          analysis uses multi-query retrieval across <em>limitations</em>,{" "}
          <em>future work</em>, and <em>challenges</em>, deduplicated before
          synthesis.
        </div>
        <Button
          variant="primary"
          fullWidth
          disabled={loading}
          onClick={() =>
            run({
              ...tunable,
              source_file: source === "__all__" ? null : source,
            })
          }
        >
          <Telescope className="w-4 h-4" />
          Identify research gaps
        </Button>
      </div>
      <ResultCard
        loading={loading}
        error={error}
        placeholder={
          <span>
            Surface limitations, open problems, and suggested future directions
            from your papers.
          </span>
        }
      >
        {data && <ResultView data={data} modeLabel="Research Gaps" />}
      </ResultCard>
    </>
  );
}
