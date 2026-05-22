"use client";

import { useState } from "react";
import {
  FileText,
  Trash2,
  Loader2,
  CheckCircle2,
  XCircle,
  RotateCw,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { deleteDocument } from "@/lib/api";
import { useDocumentsPolling } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import { Tooltip } from "./ui/tooltip";

export function DocumentList() {
  const { documents, refresh } = useDocumentsPolling();
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const handleDelete = async (id: string, filename: string) => {
    setDeletingId(id);
    try {
      await deleteDocument(id);
      toast.success(`Deleted ${filename}`);
      await refresh();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error("Delete failed", { description: msg });
    } finally {
      setDeletingId(null);
    }
  };

  const anyProcessing = documents.some((d) => d.status === "processing");

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-slate-300 uppercase tracking-wide">
            Uploaded Papers
          </span>
          {documents.length > 0 && (
            <span className="text-[10px] text-slate-500 bg-bg-elevated px-1.5 py-0.5 rounded font-mono">
              {documents.length}
            </span>
          )}
          {anyProcessing && (
            <span className="inline-flex items-center gap-1 text-[10px] text-accent-amber bg-accent-amber/10 border border-accent-amber/30 rounded-full px-2 py-0.5">
              <Loader2 className="w-3 h-3 animate-spin" />
              ingesting
            </span>
          )}
        </div>
        <Tooltip content="Refresh document list" side="left">
          <button
            onClick={() => refresh()}
            className="btn-ghost !px-1.5 !py-1"
            aria-label="Refresh"
          >
            <RotateCw className="w-3.5 h-3.5" />
          </button>
        </Tooltip>
      </div>

      {documents.length === 0 ? (
        <div className="glass rounded-lg p-5 text-center">
          <div className="w-10 h-10 mx-auto rounded-lg bg-bg-elevated flex items-center justify-center mb-2">
            <FileText className="w-5 h-5 text-slate-500" />
          </div>
          <p className="text-xs text-slate-400 font-medium">
            No papers uploaded yet
          </p>
          <p className="text-[10px] text-slate-500 mt-0.5">
            Drop a PDF above to begin
          </p>
        </div>
      ) : (
        <ul className="space-y-1.5">
          <AnimatePresence initial={false}>
            {documents.map((doc) => (
              <motion.li
                key={doc.id + doc.filename}
                layout
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, x: -10 }}
                className={cn(
                  "group flex items-start gap-2.5 p-2.5 rounded-lg border transition-all",
                  doc.status === "completed"
                    ? "glass border-border hover:border-brand-500/40"
                    : doc.status === "processing"
                      ? "bg-accent-amber/5 border-accent-amber/20"
                      : "bg-red-500/5 border-red-500/20",
                )}
              >
                <div
                  className={cn(
                    "w-7 h-7 rounded-md shrink-0 flex items-center justify-center",
                    doc.status === "completed"
                      ? "bg-brand-500/15 text-brand-300"
                      : doc.status === "processing"
                        ? "bg-accent-amber/15 text-accent-amber"
                        : "bg-red-500/15 text-red-400",
                  )}
                >
                  {doc.status === "completed" ? (
                    <CheckCircle2 className="w-4 h-4" />
                  ) : doc.status === "processing" ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <XCircle className="w-4 h-4" />
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <p
                    className="text-xs font-medium text-slate-200 truncate"
                    title={doc.filename}
                  >
                    {doc.filename}
                  </p>
                  <p className="text-[10px] text-slate-500 flex items-center gap-2 mt-0.5">
                    <FileText className="w-3 h-3" />
                    {doc.total_pages} pages · {doc.total_chunks} chunks
                  </p>
                  {doc.status === "processing" && (
                    <>
                      {doc.progress && (
                        <p className="text-xs text-muted-foreground mt-0.5">{doc.progress}</p>
                      )}
                      <div className="mt-1 h-1 rounded-full bg-bg-elevated overflow-hidden">
                        <div className="h-full w-1/2 bg-accent-amber/60 shimmer" />
                      </div>
                    </>
                  )}
                </div>
                {doc.status !== "processing" && (
                  <Tooltip content="Delete paper" side="left">
                    <button
                      onClick={() => handleDelete(doc.id, doc.filename)}
                      disabled={deletingId === doc.id}
                      className="btn-ghost !p-1.5 opacity-0 group-hover:opacity-100 transition-opacity text-red-400 hover:!bg-red-500/10"
                      aria-label={`Delete ${doc.filename}`}
                    >
                      {deletingId === doc.id ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Trash2 className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </Tooltip>
                )}
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      )}
    </div>
  );
}

export function DocumentStats() {
  const { documents } = useDocumentsPolling();
  const totalDocs = documents.length;
  const totalChunks = documents.reduce((a, d) => a + (d.total_chunks ?? 0), 0);
  const totalPages = documents.reduce((a, d) => a + (d.total_pages ?? 0), 0);
  const stats: { value: number; label: string; hint: string }[] = [
    { value: totalDocs, label: "Papers", hint: "Number of uploaded documents" },
    { value: totalPages, label: "Pages", hint: "Total pages across all papers" },
    {
      value: totalChunks,
      label: "Chunks",
      hint: "Semantic chunks indexed in ChromaDB",
    },
  ];
  return (
    <div className="grid grid-cols-3 gap-2">
      {stats.map((s) => (
        <Tooltip key={s.label} content={s.hint} side="top">
          <div className="glass rounded-lg px-2 py-2.5 text-center border border-border hover:border-brand-500/40 transition-colors w-full">
            <div className="text-lg font-bold gradient-text tabular-nums">
              {s.value}
            </div>
            <div className="text-[10px] text-slate-500 uppercase tracking-wide mt-0.5">
              {s.label}
            </div>
          </div>
        </Tooltip>
      ))}
    </div>
  );
}
