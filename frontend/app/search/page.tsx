"use client";

import { useState } from "react";
import {
  Search,
  Lightbulb,
  Binary,
  Table2,
  Image as ImageIcon,
  Sigma,
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
import { explainConcept, query } from "@/lib/api";

const SEARCH_EXAMPLES: ExamplePrompt[] = [
  { icon: Binary, title: "Attention mechanism", prompt: "attention mechanism in transformers" },
  { icon: Search, title: "Ablation studies", prompt: "ablation studies and their findings" },
  { icon: Table2, title: "Benchmark comparisons", prompt: "benchmark comparisons and evaluation metrics" },
  { icon: Sigma, title: "Loss formulation", prompt: "loss function formulation and training objective" },
];

const EXPLAIN_EXAMPLES: ExamplePrompt[] = [
  { icon: Binary, title: "Concept", prompt: "cross-attention" },
  { icon: ImageIcon, title: "Figure", prompt: "Figure 3" },
  { icon: Table2, title: "Table", prompt: "Table 2 results" },
  { icon: Sigma, title: "Metric", prompt: "BLEU score" },
];

export default function SearchPage() {
  const [tab, setTab] = useState("search");
  return (
    <>
      <PageHeader
        title="Search & Explain"
        subtitle="Run semantic search across papers or get grounded explanations of concepts, diagrams, and tables."
        icon={Search}
      />
      <Tabs
        value={tab}
        onChange={setTab}
        variant="underline"
        tabs={[
          { value: "search", label: "Semantic Search", icon: <Search className="w-4 h-4" /> },
          { value: "explain", label: "Explain Concept / Diagram", icon: <Lightbulb className="w-4 h-4" /> },
        ]}
        className="mb-5"
      />
      {tab === "search" ? <SearchTab /> : <ExplainTab />}
    </>
  );
}

function SearchTab() {
  const { documents } = useDocumentsPolling();
  const tunable = useTunablePayload();
  const completed = documents.filter((d) => d.status === "completed");
  const [q, setQ] = useState("");
  const [source, setSource] = useState("__all__");
  const [topK, setTopK] = useState(10);
  const { data, error, loading, run } = useAsync(query);

  return (
    <>
      <div className="glass rounded-2xl p-6 mb-5 space-y-5 shadow-xl shadow-black/20">
        <div>
          <div className="flex items-center gap-1.5 mb-1.5">
            <label className="text-sm font-medium text-slate-300">
              Search query
            </label>
            <InfoTip content="Semantic dense-vector search over all indexed chunks. Use natural language — no keyword tricks needed." />
          </div>
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="e.g. attention mechanism in transformers"
          />
        </div>

        <ExamplePrompts
          prompts={SEARCH_EXAMPLES}
          onPick={setQ}
          heading="Try a search"
          columns={2}
        />

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <label className="text-xs text-slate-400 mb-1.5 block font-medium">
              Filter to paper
            </label>
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
          <Slider
            label="Results"
            value={topK}
            min={3}
            max={20}
            step={1}
            onChange={setTopK}
          />
        </div>
        <Button
          variant="primary"
          fullWidth
          disabled={loading || !q.trim()}
          onClick={() =>
            run({
              ...tunable,
              question: q,
              top_k: topK,
              filter_source: source === "__all__" ? null : source,
            })
          }
        >
          <Search className="w-4 h-4" />
          Search
        </Button>
      </div>
      <ResultCard
        loading={loading}
        error={error}
        placeholder={
          <span>
            Type a query or pick an example above to search your paper corpus.
          </span>
        }
      >
        {data && <ResultView data={data} modeLabel="Semantic Search" />}
      </ResultCard>
    </>
  );
}

function ExplainTab() {
  const { documents } = useDocumentsPolling();
  const tunable = useTunablePayload();
  const completed = documents.filter((d) => d.status === "completed");
  const [concept, setConcept] = useState("");
  const [source, setSource] = useState("__all__");
  const { data, error, loading, run } = useAsync(explainConcept);

  return (
    <>
      <div className="glass rounded-2xl p-6 mb-5 space-y-5 shadow-xl shadow-black/20">
        <div>
          <div className="flex items-center gap-1.5 mb-1.5">
            <label className="text-sm font-medium text-slate-300">
              Concept / Term / Diagram
            </label>
            <InfoTip content="Concept-targeted retrieval (top-12, 5000-char context) with a dedicated explanation prompt." />
          </div>
          <Input
            value={concept}
            onChange={(e) => setConcept(e.target.value)}
            placeholder="e.g. cross-attention, Figure 3, Table 2 results, BLEU score"
          />
        </div>

        <ExamplePrompts
          prompts={EXPLAIN_EXAMPLES}
          onPick={setConcept}
          heading="What can you ask about?"
          columns={4}
        />

        <div>
          <label className="text-xs text-slate-400 mb-1.5 block font-medium">
            Filter to paper (optional)
          </label>
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
          disabled={loading || !concept.trim()}
          onClick={() =>
            run({
              ...tunable,
              concept,
              source_file: source === "__all__" ? null : source,
            })
          }
        >
          <Lightbulb className="w-4 h-4" />
          Explain
        </Button>
      </div>
      <ResultCard
        loading={loading}
        error={error}
        placeholder={
          <span>
            Enter a concept, equation, figure name, or metric — get a grounded,
            cited explanation.
          </span>
        }
      >
        {data && <ResultView data={data} modeLabel="Explain" />}
      </ResultCard>
    </>
  );
}
