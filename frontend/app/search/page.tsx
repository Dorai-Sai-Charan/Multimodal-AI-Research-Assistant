"use client";

import { useEffect, useState } from "react";
import {
  Search,
  Lightbulb,
  Binary,
  Table2,
  Image as ImageIcon,
  Sigma,
  X,
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
import { VisualCitations } from "@/components/visual-citations";
import { useDocumentsPolling, useTunablePayload, useAsync } from "@/lib/hooks";
import {
  explainConcept,
  explainVisual,
  query,
  listDocumentVisuals,
  type VisualItem,
} from "@/lib/api";
import { cn } from "@/lib/utils";

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

// Unified explain function — picks the right backend endpoint based on whether
// a visual is selected. If yes, uses Gemini Vision (/explain-visual). Otherwise,
// falls back to text-only concept retrieval (/explain).
async function unifiedExplain(input: {
  selectedVisualId?: string | null;
  concept: string;
  source_file: string | null;
  tunable: Record<string, unknown>;
}) {
  if (input.selectedVisualId) {
    return explainVisual({
      chunk_id: input.selectedVisualId,
      user_question: input.concept,
    });
  }
  return explainConcept({
    ...input.tunable,
    concept: input.concept,
    source_file: input.source_file,
  });
}

function ExplainTab() {
  const { documents } = useDocumentsPolling();
  const tunable = useTunablePayload();
  const completed = documents.filter((d) => d.status === "completed");
  const [concept, setConcept] = useState("");
  const [source, setSource] = useState("__all__");
  const [selectedVisual, setSelectedVisual] = useState<VisualItem | null>(null);
  // Snapshot of which visual was the basis for the current explanation
  // — used to keep showing it after the gallery is hidden.
  const [explainedVisual, setExplainedVisual] = useState<VisualItem | null>(null);
  const { data, error, loading, run, reset } = useAsync(unifiedExplain);

  const visualsAsync = useAsync(listDocumentVisuals);

  // Load visuals when a specific paper is selected
  useEffect(() => {
    setSelectedVisual(null);
    setExplainedVisual(null);
    reset();
    if (source && source !== "__all__") {
      visualsAsync.run(source);
    } else {
      visualsAsync.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source]);

  // When a visual is selected, auto-fill the concept field
  const pickVisual = (v: VisualItem) => {
    setSelectedVisual(v);
    const labelMap = { figure: "Figure", table: "Table", equation: "Equation" };
    const label = labelMap[v.element_type] ?? "Item";
    const hint = v.image_description
      ? v.image_description.slice(0, 80)
      : v.section_heading || `on page ${v.page_number}`;
    setConcept(`${label} on page ${v.page_number}: ${hint}`);
  };

  const handleExplain = () => {
    // Snapshot the visual we're explaining, so we can keep showing only it
    setExplainedVisual(selectedVisual);
    run({
      selectedVisualId: selectedVisual?.id ?? null,
      concept,
      source_file: source === "__all__" ? null : source,
      tunable: tunable as Record<string, unknown>,
    });
  };

  const handleNewExplain = () => {
    reset();
    setExplainedVisual(null);
    setSelectedVisual(null);
    setConcept("");
  };

  // Hide the input form/gallery once an explanation is available
  const showInputForm = !data && !loading;

  return (
    <>
      {showInputForm && (
        <div className="glass rounded-2xl p-6 mb-5 space-y-5 shadow-xl shadow-black/20">
          <div>
            <label className="text-xs text-slate-400 mb-1.5 block font-medium">
              Filter to paper (recommended — unlocks the visual gallery)
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

          {/* Visual gallery — only shown when a specific paper is selected */}
          {source !== "__all__" && (
            <VisualGallery
              loading={visualsAsync.loading}
              error={visualsAsync.error}
              visuals={visualsAsync.data?.visuals ?? []}
              selectedId={selectedVisual?.id ?? null}
              onPick={pickVisual}
            />
          )}

          <div>
            <div className="flex items-center gap-1.5 mb-1.5">
              <label className="text-sm font-medium text-slate-300">
                Concept / Term / Diagram
              </label>
              <InfoTip content="Pick a visual above to auto-fill, or type a concept (e.g. cross-attention, Figure 3, BLEU score)." />
            </div>
            <div className="relative">
              <Input
                value={concept}
                onChange={(e) => setConcept(e.target.value)}
                placeholder="e.g. cross-attention, Figure 3, Table 2 results, BLEU score"
              />
              {selectedVisual && (
                <button
                  onClick={() => {
                    setSelectedVisual(null);
                    setConcept("");
                  }}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-md text-slate-500 hover:text-slate-200 hover:bg-bg-elevated transition-colors"
                  aria-label="Clear selection"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>

          <ExamplePrompts
            prompts={EXPLAIN_EXAMPLES}
            onPick={setConcept}
            heading="Or try one of these"
            columns={4}
          />

          <Button
            variant="primary"
            fullWidth
            disabled={loading || !concept.trim()}
            onClick={handleExplain}
          >
            <Lightbulb className="w-4 h-4" />
            Explain
          </Button>
        </div>
      )}

      <ResultCard
        loading={loading}
        error={error}
        placeholder={
          <span>
            Pick a paper to browse its figures, tables, and equations — then
            select one to ask about. Or just type a concept.
          </span>
        }
      >
        {data && (
          <>
            {/* New explanation button */}
            <div className="mb-4 flex items-center justify-between gap-3">
              <p className="text-xs text-slate-500 font-mono uppercase tracking-wider">
                Explanation
              </p>
              <button
                onClick={handleNewExplain}
                className="text-xs px-3 py-1.5 rounded-lg border border-border text-slate-400 hover:text-slate-100 hover:border-brand-500/40 transition-colors"
              >
                ← New explanation
              </button>
            </div>

            {/* Show ONLY the selected visual at the top (if any) */}
            {explainedVisual ? (
              <SelectedVisualCard visual={explainedVisual} />
            ) : (
              /* Fall back to showing visual citations if no specific visual was selected */
              <VisualCitations citations={data.citations ?? []} />
            )}

            <ResultView data={data} modeLabel="Explain" />
          </>
        )}
      </ResultCard>
    </>
  );
}

// ============================================================================
// Selected Visual Card — shows just the one visual the user asked about
// ============================================================================

function SelectedVisualCard({ visual }: { visual: VisualItem }) {
  const iconMap = {
    figure: <ImageIcon className="w-4 h-4" />,
    table: <Table2 className="w-4 h-4" />,
    equation: <Sigma className="w-4 h-4" />,
  };
  const label = visual.element_type.charAt(0).toUpperCase() + visual.element_type.slice(1);

  return (
    <div className="mb-5 glass rounded-xl overflow-hidden border border-brand-500/40 shadow-lg shadow-brand-500/10">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border bg-bg-elevated">
        <div className="flex items-center gap-2 text-brand-300">
          {iconMap[visual.element_type]}
          <span className="text-sm font-semibold">
            {label} · Page {visual.page_number}
          </span>
        </div>
        <span className="text-[10px] uppercase tracking-wider font-mono text-brand-300 bg-brand-500/15 border border-brand-500/30 px-2 py-0.5 rounded-md">
          Selected
        </span>
      </div>

      <div className="bg-white/5">
        {visual.image_url ? (
          /* eslint-disable-next-line @next/next/no-img-element */
          <img
            src={`/api${visual.image_url}`}
            alt={visual.image_description ?? `${label} on page ${visual.page_number}`}
            className="w-full max-h-[500px] object-contain p-3"
            onError={(e) => {
              (e.currentTarget as HTMLImageElement).style.display = "none";
            }}
          />
        ) : visual.table_data ? (
          <pre className="p-4 text-xs text-slate-300 overflow-x-auto whitespace-pre-wrap font-mono leading-relaxed">
            {renderTablePreview(visual.table_data)}
          </pre>
        ) : visual.latex_source ? (
          <pre className="p-4 text-sm text-slate-200 font-mono overflow-x-auto leading-relaxed">
            {visual.latex_source}
          </pre>
        ) : (
          <div className="p-6 text-center text-slate-500 text-sm">
            {label} content unavailable for preview
          </div>
        )}
      </div>

      {visual.image_description && (
        <p className="px-4 py-3 text-xs text-slate-400 leading-relaxed border-t border-border bg-bg-elevated">
          <span className="font-semibold text-slate-300">Description: </span>
          {visual.image_description}
        </p>
      )}
    </div>
  );
}

// ============================================================================
// Visual Gallery — displays all figures/tables/equations from a paper
// ============================================================================

function VisualGallery({
  loading,
  error,
  visuals,
  selectedId,
  onPick,
}: {
  loading: boolean;
  error: string | null;
  visuals: VisualItem[];
  selectedId: string | null;
  onPick: (v: VisualItem) => void;
}) {
  const [filter, setFilter] = useState<"all" | "figure" | "table" | "equation">("all");

  if (loading) {
    return (
      <div className="rounded-xl bg-bg-elevated border border-border p-4">
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <div className="w-3 h-3 rounded-full border-2 border-brand-500/30 border-t-brand-500 animate-spin" />
          Loading visuals from paper…
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl bg-red-500/5 border border-red-500/30 p-3 text-xs text-red-300">
        Couldn't load visuals: {error}
      </div>
    );
  }

  if (visuals.length === 0) {
    return (
      <div className="rounded-xl bg-bg-elevated border border-border p-4 text-xs text-slate-500 text-center">
        No figures, tables, or equations found in this paper.
      </div>
    );
  }

  const filtered = filter === "all" ? visuals : visuals.filter((v) => v.element_type === filter);
  const counts = {
    all: visuals.length,
    figure: visuals.filter((v) => v.element_type === "figure").length,
    table: visuals.filter((v) => v.element_type === "table").length,
    equation: visuals.filter((v) => v.element_type === "equation").length,
  };

  return (
    <div className="rounded-xl bg-bg-elevated border border-border p-4">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs uppercase tracking-wider text-slate-400 font-mono font-semibold">
          📷 Visual elements ({visuals.length})
        </p>
        <div className="flex gap-1">
          {(["all", "figure", "table", "equation"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              disabled={counts[f] === 0}
              className={cn(
                "text-[10px] px-2 py-1 rounded-md transition-colors uppercase tracking-wider font-semibold disabled:opacity-30 disabled:cursor-not-allowed",
                filter === f
                  ? "bg-brand-500/20 text-brand-300 border border-brand-500/50"
                  : "bg-bg-card border border-border text-slate-400 hover:text-slate-100",
              )}
            >
              {f === "all" ? "All" : f.charAt(0).toUpperCase() + f.slice(1) + "s"}{" "}
              <span className="opacity-60">({counts[f]})</span>
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 max-h-[400px] overflow-y-auto pr-1">
        {filtered.map((v) => (
          <VisualThumbnail
            key={v.id}
            visual={v}
            selected={v.id === selectedId}
            onClick={() => onPick(v)}
          />
        ))}
      </div>

      {filtered.length === 0 && (
        <p className="text-xs text-slate-500 text-center py-4">
          No {filter}s found in this paper.
        </p>
      )}
    </div>
  );
}

// Renders a small preview of a table — handles many possible shapes from the backend
function renderTablePreview(td: unknown): string {
  if (td == null) return "Table";
  if (typeof td === "string") return td.slice(0, 120);

  if (typeof td === "object") {
    const obj = td as Record<string, unknown>;

    // Case 1: cols is an array of column names
    if (Array.isArray(obj.cols) && obj.cols.length > 0) {
      return obj.cols.map((c) => String(c ?? "")).join(" | ");
    }

    // Case 2: raw is a 2D array of cells
    if (Array.isArray(obj.raw)) {
      const flat = (obj.raw as unknown[])
        .slice(0, 3)
        .map((row) =>
          Array.isArray(row)
            ? row.map((c) => String(c ?? "").trim()).filter(Boolean).join(" | ")
            : String(row ?? ""),
        )
        .filter(Boolean)
        .join("\n");
      if (flat) return flat.slice(0, 120);
    }

    // Case 3: raw is a string
    if (typeof obj.raw === "string") return obj.raw.slice(0, 120);

    // Case 4: cols/rows are integer counts
    if (typeof obj.cols === "number" || typeof obj.rows === "number") {
      const r = obj.rows ?? "?";
      const c = obj.cols ?? "?";
      return `Table · ${r} rows × ${c} cols`;
    }
  }

  return "Table";
}

function VisualThumbnail({
  visual,
  selected,
  onClick,
}: {
  visual: VisualItem;
  selected: boolean;
  onClick: () => void;
}) {
  const iconMap = {
    figure: <ImageIcon className="w-3 h-3" />,
    table: <Table2 className="w-3 h-3" />,
    equation: <Sigma className="w-3 h-3" />,
  };
  const label = visual.element_type.charAt(0).toUpperCase() + visual.element_type.slice(1);

  return (
    <button
      onClick={onClick}
      className={cn(
        "group relative rounded-lg overflow-hidden border-2 transition-all text-left",
        selected
          ? "border-brand-500 shadow-lg shadow-brand-500/30 scale-[1.02]"
          : "border-border hover:border-brand-500/50 hover:scale-[1.01]",
      )}
    >
      <div className="aspect-video bg-white/5 flex items-center justify-center overflow-hidden">
        {visual.image_url ? (
          /* eslint-disable-next-line @next/next/no-img-element */
          <img
            src={`/api${visual.image_url}`}
            alt={visual.image_description ?? `${label} on page ${visual.page_number}`}
            className="w-full h-full object-contain"
            onError={(e) => {
              (e.currentTarget as HTMLImageElement).style.display = "none";
            }}
          />
        ) : visual.table_data ? (
          <div className="p-2 text-[9px] text-slate-400 font-mono overflow-hidden line-clamp-6 w-full">
            {renderTablePreview(visual.table_data)}
          </div>
        ) : visual.latex_source ? (
          <div className="p-2 text-[10px] text-slate-300 font-mono text-center line-clamp-4">
            {visual.latex_source.slice(0, 100)}
          </div>
        ) : (
          <div className="text-xs text-slate-500">{label}</div>
        )}
      </div>
      <div className="bg-bg-card px-2 py-1.5 flex items-center gap-1.5">
        <span
          className={cn(
            "flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider",
            selected ? "text-brand-300" : "text-slate-400",
          )}
        >
          {iconMap[visual.element_type]}
          {label}
        </span>
        <span className="text-[10px] text-slate-500 ml-auto">
          p{visual.page_number}
        </span>
      </div>
      {selected && (
        <div className="absolute top-1 right-1 bg-brand-500 text-white text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-md">
          Selected
        </div>
      )}
    </button>
  );
}
