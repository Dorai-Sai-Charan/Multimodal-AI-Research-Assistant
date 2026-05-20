import type { Metadata } from "next";
import { Sidebar } from "@/components/sidebar";
import { ModelsBootstrap } from "@/components/models-bootstrap";
import { Toaster } from "@/components/ui/toaster";
import { ErrorBoundary } from "@/components/error-boundary";
import "./globals.css";

export const metadata: Metadata = {
  title: "Multimodal AI Research Assistant",
  description:
    "Research paper analysis powered by multimodal RAG and agentic reasoning.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body>
        <ModelsBootstrap />
        <Toaster />
        <div className="flex">
          <Sidebar />
          <ErrorBoundary>
            <main className="flex-1 min-w-0 px-8 py-8">
              <div className="max-w-5xl mx-auto">{children}</div>
            </main>
          </ErrorBoundary>
        </div>
      </body>
    </html>
  );
}
