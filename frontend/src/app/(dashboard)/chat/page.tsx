import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Chat page — primary interaction surface.
 * SSE streaming + citation rendering implemented in Week 3.
 */
export default function ChatPage() {
  return (
    <div className="flex h-full flex-col items-center justify-center p-6">
      <Card className="w-full max-w-2xl">
        <CardHeader>
          <CardTitle className="text-center">Start a conversation</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-center text-sm text-muted-foreground">
            Ask questions about your documents. Responses will be grounded in
            your knowledge corpus with full citations.
          </p>
          <div className="flex items-center gap-2 rounded-lg border p-3">
            <input
              type="text"
              placeholder="Type your question..."
              className="flex-1 bg-transparent outline-none placeholder:text-muted-foreground"
              disabled
            />
            <Button size="sm" disabled>
              Send
            </Button>
          </div>
          <p className="text-center text-xs text-muted-foreground">
            Chat functionality will be available after the RAG pipeline is
            connected (Week 3).
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
