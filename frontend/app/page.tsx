import { MessageSquare } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { ChatPanel } from "@/components/chat-panel";

export default function Page() {
  return (
    <>
      <PageHeader
        title="Conversational Research Assistant"
        subtitle="Ask anything about your uploaded papers — flip Agent Mode on for multi-hop questions."
        icon={MessageSquare}
      />
      <ChatPanel />
    </>
  );
}
