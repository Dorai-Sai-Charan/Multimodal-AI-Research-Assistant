"use client";

import { useState } from "react";
import { GitCompareArrows, Play, ArrowRight, FileText } from "lucide-react";
import { PageHeader, ResultCard } from "@/components/page-header";
import { ResultView } from "@/components/result-view";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { InfoTip } from "@/components/ui/info-tip";
import { useDocumentsPolling, useTunablePayload, useAsync } from "@/lib/hooks";
import { comparePapers } from "@/lib/api";

export default function ComparePage() {
  const { documents } = useDocumentsPolling();
  const tunable = useTunablePayload();
  const completed = documents
    .filter((d) => d.status === "completed")
    .map((d) => d.filename);

  const [paper1, setPaper1] = useState<string>("");
  const [paper2, setPaper2] = useState<string>("");
  const { data, error, loading, run } = useAsync(comparePapers);

  if (completed.length < 2) {
    return (
      <>
        <PageHeader
          title="Compare Research Papers"
          subtitle="Pick any two uploaded papers to get a structured side-by-side comparison."
          icon={GitCompareArrows}
        />
        <div className="glass rounded-2xl p-10 text-center shadow-xl shadow-black/20">
          <div className="w-14 h-14 mx-auto rounded-2xl bg-brand-500/10 border border-brand-500/30 flex items-center justify-center mb-4">
            <FileText className="w-7 h-7 text-brand-300" />
          </div>
          <h3 className="text-base font-semibold text-slate-200">
            You need at least two papers
          </h3>
          <p className="text-sm text-slate-400 mt-2 max-w-md mx-auto leading-relaxed">
            Upload two or more PDFs in the sidebar. Once both show{" "}
            <span className="text-accent-green">completed</span>, come back to
            compare them across methodology, datasets, results, and limitations.
          </p>
          <div className="mt-4 text-xs text-slate-500">
            Currently uploaded: <span className="text-brand-300 font-mono">{completed.length}</span> / 2
          </div>
        </div>
      </>
    );
  }

  const p1 = paper1 || completed[0];
  const p2 = paper2 || completed.find((p) => p !== p1) || completed[1];

  return (
    <>
      <PageHeader
        title="Compare Research Papers"
        subtitle="Structured side-by-side analysis across methods, datasets, results, and limitations."
        icon={GitCompareArrows}
      />

      <div className="glass rounded-2xl p-6 mb-5 shadow-xl shadow-black/20">
        <div className="flex items-center gap-1.5 mb-4">
          <span className="label">Pick two papers to compare</span>
          <InfoTip content="Each paper is retrieved independently (top-15 chunks each) and fed into a structured side-by-side prompt." />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-4 items-end">
          <div>
            <label className="text-xs text-slate-400 mb-1.5 block font-medium">
              Paper 1
            </label>
            <Select
              value={p1}
              onChange={setPaper1}
              options={completed.map((c) => ({ value: c, label: c }))}
            />
          </div>
          <div className="hidden md:flex items-center justify-center w-10 h-10 rounded-full bg-gradient-brand text-white mb-1 shadow-lg shadow-brand-600/30">
            <ArrowRight className="w-5 h-5" />
          </div>
          <div>
            <label className="text-xs text-slate-400 mb-1.5 block font-medium">
              Paper 2
            </label>
            <Select
              value={p2}
              onChange={setPaper2}
              options={completed
                .filter((c) => c !== p1)
                .map((c) => ({ value: c, label: c }))}
            />
          </div>
        </div>
        <Button
          variant="primary"
          fullWidth
          className="mt-5"
          disabled={loading || p1 === p2}
          onClick={() => run({ ...tunable, paper1: p1, paper2: p2 })}
        >
          <Play className="w-4 h-4" />
          Compare papers
        </Button>
        <p className="text-[11px] text-slate-500 mt-3 text-center">
          Typical run: 20–45 seconds depending on model and paper length.
        </p>
      </div>

      <ResultCard
        loading={loading}
        error={error}
        placeholder={
          <span>
            Pick two papers and hit{" "}
            <span className="text-brand-300 font-medium">Compare</span> to see
            the structured analysis.
          </span>
        }
      >
        {data && <ResultView data={data} modeLabel="Compare" />}
      </ResultCard>
    </>
  );
}
