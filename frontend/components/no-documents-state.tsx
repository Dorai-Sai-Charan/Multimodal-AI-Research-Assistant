"use client";

import { Upload } from "lucide-react";

interface Props {
  feature?: string;
}

export function NoDocumentsState({ feature = "this feature" }: Props) {
  return (
    <div className="flex flex-col items-center justify-center h-64 text-center gap-4 rounded-xl border border-dashed border-border p-10">
      <div className="rounded-full bg-muted p-4">
        <Upload className="h-8 w-8 text-muted-foreground" />
      </div>
      <div>
        <h3 className="text-lg font-semibold mb-1">No papers uploaded</h3>
        <p className="text-sm text-muted-foreground max-w-sm">
          Upload at least one PDF using the panel on the left before using{" "}
          {feature}.
        </p>
      </div>
    </div>
  );
}
