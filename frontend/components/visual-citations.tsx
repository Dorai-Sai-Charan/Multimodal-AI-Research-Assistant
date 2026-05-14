"use client";

import { useState } from "react";
import { ImageIcon, Table2, Sigma, FileText, ChevronDown, ChevronUp } from "lucide-react";
import type { Citation } from "@/lib/types";
import { cn } from "@/lib/utils";

interface VisualCitationsProps {
  citations: Citation[];
}

function ImageCard({ citation }: { citation: Citation }) {
  const [expanded, setExpanded] = useState(true);
  return (
    <div className="glass rounded-xl overflow-hidden border border-border">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border bg-bg-elevated">
        <div className="flex items-center gap-2">
          <ImageIcon className="w-3.5 h-3.5 text-brand-400 shrink-0" />
          <span className="text-xs font-medium text-slate-300 truncate max-w-[200px]">
            {citation.source_file}
          </span>
          <span className="text-xs text-slate-500">· Page {citation.page_number}</span>
        </div>
        <button
          onClick={() => setExpanded((p) => !p)}
          className="text-slate-500 hover:text-slate-300 transition-colors"
        >
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>
      {expanded && (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={`/api${citation.image_url}`}
            alt={citation.image_description ?? "Figure from paper"}
            className="w-full max-h-96 object-contain bg-white/5 p-2"
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = "none";
            }}
          />
          {citation.image_description && (
            <p className="px-4 py-2.5 text-xs text-slate-400 leading-relaxed border-t border-border">
              {citation.image_description}
            </p>
          )}
        </>
      )}
    </div>
  );
}

function TableCard({ citation }: { citation: Citation }) {
  const [expanded, setExpanded] = useState(true);
  const td = citation.table_data;
  const cols = td?.cols ?? [];
  const rows = td?.rows ?? [];
  const hasStructured = cols.length > 0 || rows.length > 0;

  return (
    <div className="glass rounded-xl overflow-hidden border border-border">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border bg-bg-elevated">
        <div className="flex items-center gap-2">
          <Table2 className="w-3.5 h-3.5 text-brand-400 shrink-0" />
          <span className="text-xs font-medium text-slate-300 truncate max-w-[200px]">
            {citation.source_file}
          </span>
          <span className="text-xs text-slate-500">· Page {citation.page_number}</span>
        </div>
        <button
          onClick={() => setExpanded((p) => !p)}
          className="text-slate-500 hover:text-slate-300 transition-colors"
        >
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>
      {expanded && (
        <div className="overflow-x-auto">
          {hasStructured ? (
            <table className="w-full text-xs text-slate-300 border-collapse">
              {cols.length > 0 && (
                <thead>
                  <tr className="bg-bg-elevated">
                    {cols.map((col, i) => (
                      <th
                        key={i}
                        className="px-3 py-2 text-left font-semibold text-slate-200 border-b border-border whitespace-nowrap"
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
              )}
              <tbody>
                {rows.map((row, ri) => (
                  <tr key={ri} className={cn(ri % 2 === 0 ? "" : "bg-bg-elevated/50")}>
                    {row.map((cell, ci) => (
                      <td key={ci} className="px-3 py-1.5 border-b border-border/50">
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          ) : td?.raw ? (
            <pre className="p-4 text-xs text-slate-300 overflow-x-auto whitespace-pre-wrap font-mono leading-relaxed">
              {td.raw}
            </pre>
          ) : (
            <p className="p-4 text-xs text-slate-500 italic">Table data unavailable</p>
          )}
        </div>
      )}
    </div>
  );
}

function EquationCard({ citation }: { citation: Citation }) {
  const [expanded, setExpanded] = useState(true);
  return (
    <div className="glass rounded-xl overflow-hidden border border-border">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border bg-bg-elevated">
        <div className="flex items-center gap-2">
          <Sigma className="w-3.5 h-3.5 text-brand-400 shrink-0" />
          <span className="text-xs font-medium text-slate-300 truncate max-w-[200px]">
            {citation.source_file}
          </span>
          <span className="text-xs text-slate-500">· Page {citation.page_number}</span>
        </div>
        <button
          onClick={() => setExpanded((p) => !p)}
          className="text-slate-500 hover:text-slate-300 transition-colors"
        >
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>
      {expanded && citation.latex_source && (
        <pre className="p-4 text-xs text-slate-200 font-mono overflow-x-auto bg-bg-elevated/30 leading-relaxed">
          {citation.latex_source}
        </pre>
      )}
    </div>
  );
}

export function VisualCitations({ citations }: VisualCitationsProps) {
  const visuals = citations.filter(
    (c) => c.image_url || c.table_data || c.latex_source,
  );

  if (visuals.length === 0) return null;

  return (
    <div className="mb-5">
      <div className="flex items-center gap-2 mb-3">
        <FileText className="w-4 h-4 text-brand-400" />
        <span className="text-sm font-semibold text-slate-300">
          Visual Content from Papers
        </span>
        <span className="text-xs text-slate-500">({visuals.length} found)</span>
      </div>
      <div className="grid gap-4">
        {visuals.map((c, i) => {
          if (c.image_url) return <ImageCard key={i} citation={c} />;
          if (c.table_data) return <TableCard key={i} citation={c} />;
          if (c.latex_source) return <EquationCard key={i} citation={c} />;
          return null;
        })}
      </div>
    </div>
  );
}
