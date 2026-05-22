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
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<{ current: number; total: number } | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const handleUpload = useCallback(async () => {
    if (selectedFiles.length === 0) return;
    
    setUploading(true);
    const count = selectedFiles.length;
    const toastId = toast.loading(
      count === 1 ? `Uploading ${selectedFiles[0].name}…` : `Uploading ${count} files…`
    );
    setUploadProgress({ current: 0, total: count });

    let successCount = 0;
    let failCount = 0;

    try {
      // Process files sequentially to avoid overwhelming the frontend UI/toasts,
      // but the backend handles them in background threads anyway.
      for (let i = 0; i < selectedFiles.length; i++) {
        const file = selectedFiles[i];
        setUploadProgress({ current: i + 1, total: count });
        try {
          await uploadDocument(file);
          successCount++;
        } catch (e: unknown) {
          console.error(`Failed to upload ${file.name}:`, e);
          failCount++;
        }
      }

      if (failCount === 0) {
        toast.success(
          count === 1 
            ? `${selectedFiles[0].name} queued for ingestion` 
            : `All ${count} files queued successfully`,
          { id: toastId }
        );
      } else {
        toast.error(`Completed with errors: ${successCount} success, ${failCount} failed`, {
          id: toastId,
        });
      }

      setSelectedFiles([]);
      if (fileRef.current) fileRef.current.value = "";
      refresh();
    } catch (e: unknown) {
      toast.error("An unexpected error occurred during batch upload", { id: toastId });
    } finally {
      setUploading(false);
      setUploadProgress(null);
    }
  }, [selectedFiles, refresh]);

  const validateAndAddFiles = (incoming: FileList | File[]) => {
    const list = Array.from(incoming);
    const pdfs = list.filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    const others = list.length - pdfs.length;

    if (others > 0) {
      toast.warning(`Skipped ${others} non-PDF files.`);
    }

    if (pdfs.length > 0) {
      setSelectedFiles((prev) => {
        // Avoid duplicates by name (simple check)
        const existingNames = new Set(prev.map(f => f.name));
        const newFiles = pdfs.filter(f => !existingNames.has(f.name));
        return [...prev, ...newFiles];
      });
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    validateAndAddFiles(e.dataTransfer.files);
  };

  const removeFile = (name: string) => {
    setSelectedFiles((prev) => prev.filter((f) => f.name !== name));
    if (selectedFiles.length === 1 && fileRef.current) {
        fileRef.current.value = "";
    }
  };

  const sizeLabel = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  const hasFiles = selectedFiles.length > 0;

  return (
    <div className="space-y-2.5">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => !uploading && fileRef.current?.click()}
        className={cn(
          "group relative rounded-xl border-2 border-dashed p-5 transition-all outline-none",
          "flex flex-col items-center justify-center text-center gap-2",
          !uploading && "cursor-pointer",
          dragOver
            ? "border-brand-500 bg-brand-500/10 scale-[1.01]"
            : "border-border hover:border-brand-500/50 hover:bg-bg-elevated/40",
            hasFiles && "border-brand-500/30 bg-brand-500/5"
        )}
      >
        <div
          className={cn(
            "w-11 h-11 rounded-full flex items-center justify-center transition-all",
            dragOver
              ? "bg-brand-500/20 text-brand-300 scale-110"
              : "bg-bg-elevated text-slate-400 group-hover:text-brand-300",
              hasFiles && "bg-brand-500/10 text-brand-400"
          )}
        >
          <FileUp className={cn("w-5 h-5", uploading && "animate-bounce")} />
        </div>
        
        {!hasFiles ? (
          <div>
            <p className="text-sm font-medium text-slate-200">
              Drop PDFs or click to browse
            </p>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Select multiple papers — up to 50 MB each
            </p>
          </div>
        ) : (
          <div className="w-full">
            <p className="text-xs font-semibold text-brand-400 mb-2">
              {selectedFiles.length} file{selectedFiles.length > 1 ? 's' : ''} ready
            </p>
            <div className="max-h-[100px] overflow-y-auto space-y-1 pr-1 custom-scrollbar">
                {selectedFiles.map(file => (
                  <div key={file.name} className="flex items-center gap-2 bg-bg-elevated/60 rounded-md px-2 py-1.5 border border-border/40">
                    <span className="text-[11px] font-medium text-slate-200 truncate flex-1 text-left">
                      {file.name}
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        removeFile(file.name);
                      }}
                      className="text-slate-500 hover:text-red-400 p-0.5 transition-colors"
                      title="Remove"
                      disabled={uploading}
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                ))}
            </div>
            {selectedFiles.length > 3 && (
                <p className="text-[10px] text-slate-500 mt-1 italic">
                    Scroll to see all
                </p>
            )}
          </div>
        )}
        <input
          ref={fileRef}
          type="file"
          accept=".pdf"
          multiple
          onChange={(e) => validateAndAddFiles(e.target.files ?? [])}
          className="hidden"
          disabled={uploading}
        />
      </div>

      {hasFiles && !uploading && (
        <div className="flex gap-2">
            <button
                onClick={() => setSelectedFiles([])}
                className="btn-ghost flex-1 text-[11px]"
            >
                Clear all
            </button>
            <button
                onClick={handleUpload}
                className="btn-primary flex-[2]"
            >
                <Upload className="w-4 h-4" />
                Process {selectedFiles.length > 1 ? 'all' : ''}
            </button>
        </div>
      )}

      {uploading && (
        <div className="space-y-1.5">
          {uploadProgress && uploadProgress.total > 1 && (
            <p className="text-[11px] text-slate-400 text-center">
              Uploading {uploadProgress.current} of {uploadProgress.total} files…
            </p>
          )}
          <div className="h-1.5 w-full rounded-full bg-bg-elevated overflow-hidden">
            {uploadProgress && uploadProgress.total > 1 ? (
              <div
                className="h-full bg-gradient-brand transition-all duration-300"
                style={{ width: `${(uploadProgress.current / uploadProgress.total) * 100}%` }}
              />
            ) : (
              <div className="h-full w-full bg-gradient-brand animate-[shimmer_1.2s_linear_infinite]" />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
