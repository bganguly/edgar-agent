import { useState, useRef, useEffect, FormEvent } from "react";

interface ToolCall {
  tool: string;
  input: Record<string, string>;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  toolCalls?: ToolCall[];
}

const TOOL_LABELS: Record<string, string> = {
  search_edgar: "🔍 Searching EDGAR...",
  fetch_filing: "📄 Fetching filing...",
};

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [activeTools, setActiveTools] = useState<ToolCall[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, activeTools]);

  async function sendMessage(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    setInput("");
    setLoading(true);
    setActiveTools([]);

    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setMessages((prev) => [...prev, { role: "assistant", content: "", toolCalls: [] }]);

    try {
      const resp = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: text }),
      });

      const reader = resp.body!.getReader();
      const decoder = new TextDecoder();
      const collectedTools: ToolCall[] = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const raw = decoder.decode(value);
        const lines = raw.split("\n").filter((l) => l.startsWith("data:"));

        for (const line of lines) {
          const jsonStr = line.replace(/^data:\s*/, "").trim();
          if (!jsonStr) continue;
          try {
            const event = JSON.parse(jsonStr);

            if (event.type === "token") {
              setMessages((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                if (last.role === "assistant") {
                  next[next.length - 1] = { ...last, content: last.content + event.text };
                }
                return next;
              });
            } else if (event.type === "tool_call") {
              const tc: ToolCall = { tool: event.tool, input: event.input };
              collectedTools.push(tc);
              setActiveTools((prev) => [...prev, tc]);
            } else if (event.type === "session_id") {
              setSessionId(event.session_id);
            } else if (event.type === "done") {
              setMessages((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                if (last.role === "assistant") {
                  next[next.length - 1] = { ...last, toolCalls: collectedTools };
                }
                return next;
              });
              setActiveTools([]);
            }
          } catch {
            // skip malformed
          }
        }
      }
    } catch (err) {
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = {
          role: "assistant",
          content: `Error: ${err instanceof Error ? err.message : "Unknown error"}`,
        };
        return next;
      });
    } finally {
      setLoading(false);
      setActiveTools([]);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
      <div style={{ flex: 1, overflowY: "auto", padding: "20px", display: "flex", flexDirection: "column", gap: "16px" }}>
        {messages.length === 0 && (
          <div style={{ textAlign: "center", color: "#718096", marginTop: "60px" }}>
            <div style={{ fontSize: "40px", marginBottom: "12px" }}>📊</div>
            <div style={{ fontSize: "16px" }}>Ask about any public company</div>
            <div style={{ fontSize: "13px", marginTop: "6px", color: "#4a5568" }}>
              e.g. "What were Apple's revenue and net income in 2023?"
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} style={{ display: "flex", justifyContent: msg.role === "user" ? "flex-end" : "flex-start" }}>
            <div style={{
              maxWidth: "75%",
              padding: "12px 16px",
              borderRadius: msg.role === "user" ? "18px 18px 4px 18px" : "18px 18px 18px 4px",
              background: msg.role === "user" ? "#3182ce" : "#2d3748",
              color: "#e2e8f0",
              fontSize: "14px",
              lineHeight: "1.6",
              whiteSpace: "pre-wrap",
            }}>
              {msg.toolCalls && msg.toolCalls.length > 0 && (
                <div style={{ marginBottom: "8px", display: "flex", flexDirection: "column", gap: "4px" }}>
                  {msg.toolCalls.map((tc, j) => (
                    <span key={j} style={{
                      fontSize: "11px",
                      color: "#90cdf4",
                      background: "#1a365d",
                      padding: "2px 8px",
                      borderRadius: "12px",
                      display: "inline-block",
                      width: "fit-content",
                    }}>
                      {TOOL_LABELS[tc.tool] ?? tc.tool}
                      {tc.tool === "search_edgar" && tc.input.company_name && ` "${tc.input.company_name}"`}
                    </span>
                  ))}
                </div>
              )}
              {msg.content || (msg.role === "assistant" && loading && i === messages.length - 1 ? (
                <span style={{ color: "#718096" }}>▌</span>
              ) : null)}
            </div>
          </div>
        ))}

        {activeTools.length > 0 && (
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", paddingLeft: "8px" }}>
            {activeTools.map((tc, i) => (
              <span key={i} style={{
                fontSize: "12px",
                color: "#90cdf4",
                background: "#1a365d",
                padding: "4px 10px",
                borderRadius: "12px",
                animation: "pulse 1.5s infinite",
              }}>
                {TOOL_LABELS[tc.tool] ?? tc.tool}
                {tc.tool === "search_edgar" && tc.input.company_name && ` "${tc.input.company_name}"`}
              </span>
            ))}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <form onSubmit={sendMessage} style={{
        padding: "16px 20px",
        borderTop: "1px solid #2d3748",
        background: "#1a202c",
        display: "flex",
        gap: "10px",
      }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about a company's 10-K filing..."
          disabled={loading}
          style={{
            flex: 1,
            padding: "10px 16px",
            borderRadius: "24px",
            border: "1px solid #4a5568",
            background: "#2d3748",
            color: "#e2e8f0",
            fontSize: "14px",
            outline: "none",
          }}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          style={{
            padding: "10px 20px",
            borderRadius: "24px",
            border: "none",
            background: loading ? "#4a5568" : "#3182ce",
            color: "white",
            cursor: loading ? "not-allowed" : "pointer",
            fontSize: "14px",
            fontWeight: 600,
          }}
        >
          {loading ? "..." : "Send"}
        </button>
      </form>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  );
}
