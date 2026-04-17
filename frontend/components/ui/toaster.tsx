"use client";

import { Toaster as SonnerToaster } from "sonner";

export function Toaster() {
  return (
    <SonnerToaster
      position="bottom-right"
      theme="dark"
      toastOptions={{
        style: {
          background: "rgba(26, 26, 46, 0.95)",
          border: "1px solid rgba(139, 92, 246, 0.3)",
          backdropFilter: "blur(12px)",
          color: "#e2e8f0",
          fontSize: "13px",
        },
        className: "font-sans",
      }}
    />
  );
}
