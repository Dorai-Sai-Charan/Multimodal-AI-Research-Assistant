import type { Metadata } from "next";
import { Sidebar } from "@/components/sidebar";
import { ModelsBootstrap } from "@/components/models-bootstrap";
import { Toaster } from "@/components/ui/toaster";
import { ErrorBoundary } from "@/components/error-boundary";
import { ThemeProvider } from "@/components/theme-provider";
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
    <html lang="en">
      <head>
        {/* Prevent flash of light mode — apply saved theme before first paint */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var s=JSON.parse(localStorage.getItem('research-assistant-state')||'{}');var t=(s.state&&s.state.theme)||'dark';if(t==='dark')document.documentElement.classList.add('dark');}catch(e){document.documentElement.classList.add('dark');}})();`,
          }}
        />
      </head>
      <body>
        <ThemeProvider>
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
        </ThemeProvider>
      </body>
    </html>
  );
}
