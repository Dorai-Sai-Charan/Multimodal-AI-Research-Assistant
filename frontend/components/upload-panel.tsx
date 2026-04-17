"use client";

import { useCallback, useRef, useState } from "react";
import { FileUp, Upload, X } from "lucide-react";
import { toast } from "sonner";
import { uploadDocument } from "@/lib/api";
import { useDocumentsPolling } from "@/lib/hooks";
import { cn } from "@/lib/utils";

export function UploadPanel() {
  const { refresh } = useDocumentsPolling();
  const fileRef = useRef<HTMLInputElement>(null);
  const [selected, setSelected] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const handleUpload = useCallback(
    async (file: File) => {
      setUploading(true);
      const toastId = toast.loading(`Uploading ${file.name}…`);
      try {
        await uploadDocument(file);
        toast.success(`${file.name} queued for ingestion`, {
          id: toastId,
          description: "Status updates automatically as it processes.",
        });
        setSelected(null);
        if (fileRef.current) fileRef.current.value = "";
        refresh();
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        toast.error("Upload failed", { id: toastId, description: msg });
      } finally {
        setUploading(false);
      }
    },
    [refresh],
  );

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (!f) return;
    if (!f.name.toLowerCase().endsWith(".pdf")) {
      toast.error("Only PDF files are supported");
      return;
    }
    setSelected(f);
  };

  const sizeLabel = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  return (
    <div className="space-y-2.5">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => !selected && fileRef.current?.click()}
        className={cn(
          "group relative rounded-xl border-2 border-dashed p-5 transition-all",
          "flex flex-col items-center justify-center text-center gap-2",
          !selected && "cursor-pointer",
          dragOver
            ? "border-brand-500 bg-brand-500/10 scale-[1.01]"
            : "border-border hover:border-brand-500/50 hover:bg-bg-elevated/40",
        )}
      >
        <div
          className={cn(
            "w-11 h-11 rounded-full flex items-center justify-center transition-all",
            dragOver
              ? "bg-brand-500/20 text-brand-300 scale-110"
              : "bg-bg-elevated text-slate-400 group-hover:text-brand-300",
          )}
        >
          <FileUp className="w-5 h-5" />
        </div>
        {selected ? (
          <div className="w-full">
            <div className="flex items-center gap-2 justify-center">
              <span className="text-sm font-medium text-slate-200 truncate max-w-[180px]">
                {selected.name}
              </span>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setSelected(null);
                  if (fileRef.current) fileRef.current.value = "";
                }}
                className="btn-ghost !p-1"
                title="Clear"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
            <p className="text-[10px] text-slate-500 mt-0.5">
              {sizeLabel(selected.size)}
            </p>
          </div>
        ) : (
          <div>
            <p className="text-sm font-medium text-slate-200">
              Drop PDF or click to browse
            </p>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Research papers — up to 50 MB
            </p>
          </div>
        )}
        <input
          ref={fileRef}
          type="file"
          accept=".pdf"
          onChange={(e) => setSelected(e.target.files?.[0] ?? null)}
          className="hidden"
        />
      </div>

      {selected && !uploading && (
        <button
          onClick={() => handleUpload(selected)}
          className="btn-primary w-full"
        >
          <Upload className="w-4 h-4" />
          Process document
        </button>
      )}

      {uploading && (
        <div className="h-1.5 w-full rounded-full bg-bg-elevated overflow-hidden">
          <div className="h-full w-1/3 bg-gradient-brand animate-[shimmer_1.2s_linear_infinite]" />
        </div>
      )}
    </div>
  );
}
