import {
  useState,
  useRef,
  useEffect,
  KeyboardEvent,
  ChangeEvent,
} from "react";
import { api, apiFetch, ApiError, ChatApiMessage } from "../api/client";

interface ThreadMessage {
  role: "user" | "assistant";
  content: string;
  modelUsed?: string;
  fileName?: string;
  cached?: boolean;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function ModelBadge({ model, cached }: { model: string; cached?: boolean }) {
  if (cached) {
    return (
      <span className="mt-1.5 inline-block rounded border border-warn/20 bg-warn/10 px-2 py-0.5 text-xs font-medium text-warn">
        cached
      </span>
    );
  }
  const isSimple =
    model.includes("llama") || model.includes("mini") || model.includes("flash");
  return (
    <span
      className={`mt-1.5 inline-block rounded border px-2 py-0.5 text-xs font-medium ${
        isSimple
          ? "border-green/20 bg-green-soft text-green"
          : "border-line bg-subtle text-muted"
      }`}
    >
      {model}
    </span>
  );
}

export function Chat() {
  const [thread, setThread] = useState<ThreadMessage[]>([]);
  const [input, setInput] = useState("");
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function newChat() {
    setThread([]);
    setInput("");
    setPendingFile(null);
    setError(null);
  }

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [thread, loading]);

  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`;
  }, [input]);

  function onFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    setPendingFile(file);
    e.target.value = "";
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  }

  async function send() {
    const trimmed = input.trim();
    if (!trimmed && !pendingFile) return;
    if (loading) return;

    setLoading(true);
    setError(null);

    try {
      let userContent = trimmed;
      let fileName: string | undefined;

      if (pendingFile) {
        fileName = pendingFile.name;
        const form = new FormData();
        form.append("file", pendingFile);

        const res = await apiFetch("/v1/documents/ingest", {
          method: "POST",
          body: form,
        });
        if (!res.ok) {
          const text = await res.text();
          throw new ApiError(res.status, text);
        }
        const ingestData = (await res.json()) as {
          markdown: string;
          filename: string;
        };

        const contextBlock = `[Document: ${ingestData.filename}]\n${ingestData.markdown}`;
        userContent = trimmed ? `${contextBlock}\n\n${trimmed}` : contextBlock;
      }

      const newUserMsg: ThreadMessage = { role: "user", content: userContent, fileName };

      const historyForApi: ChatApiMessage[] = [
        ...thread.map((m) => ({ role: m.role, content: m.content })),
        { role: "user", content: userContent },
      ];

      setInput("");
      setPendingFile(null);
      setThread((prev) => [...prev, newUserMsg]);

      const result = await api.chat(historyForApi);
      const assistantContent =
        result.choices[0]?.message?.content ?? "(no response)";

      setThread((prev) => [
        ...prev,
        {
          role: "assistant",
          content: assistantContent,
          modelUsed: result.model,
          cached: result.gateway_cached,
        },
      ]);
    } catch (err) {
      let msg = "Something went wrong.";
      if (err instanceof ApiError) {
        try {
          const parsed = JSON.parse(err.message) as {
            detail?: string | { error?: string; reason?: string };
          };
          if (typeof parsed.detail === "string") {
            msg = parsed.detail;
          } else if (parsed.detail && typeof parsed.detail === "object") {
            msg = parsed.detail.reason || parsed.detail.error || "Request was blocked.";
          } else {
            msg = err.message;
          }
        } catch {
          msg = err.message;
        }
      }
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  const canSend = (input.trim().length > 0 || pendingFile !== null) && !loading;

  return (
    <div className="flex h-[calc(100vh-64px)] flex-col">
      {/* Active conversation header */}
      {thread.length > 0 && (
        <div className="flex items-center justify-between border-b border-line bg-surface px-4 py-2">
          <span className="text-xs font-medium text-muted">
            {thread.filter((m) => m.role === "user").length} message
            {thread.filter((m) => m.role === "user").length !== 1 ? "s" : ""}
          </span>
          <button
            onClick={newChat}
            className="flex items-center gap-1.5 rounded-md border border-line bg-surface px-3 py-1.5 text-xs font-medium text-muted transition-colors hover:border-green/40 hover:text-green"
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            New chat
          </button>
        </div>
      )}

      {/* Thread */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="mx-auto max-w-2xl space-y-6">
          {thread.length === 0 && (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-xl border border-line bg-surface">
                <svg
                  className="h-6 w-6 text-green"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={1.5}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-3 3v-3z"
                  />
                </svg>
              </div>
              <p className="text-sm font-semibold text-ink">Start a conversation</p>
              <p className="mt-1 text-xs text-muted">
                Relay routes your request through auth, guardrails, cache, and smart routing
              </p>
              <p className="mt-1 text-xs text-muted">
                Attach a PDF, DOCX, or PPTX to use it as context
              </p>
            </div>
          )}

          {thread.map((msg, i) =>
            msg.role === "user" ? (
              <div key={i} className="flex justify-end">
                <div className="max-w-[75%]">
                  <div className="rounded-2xl rounded-tr-sm border border-green/20 bg-green-soft px-4 py-3 text-sm text-ink">
                    {msg.fileName && (
                      <div className="mb-2 flex items-center gap-1.5 rounded-md border border-green/20 bg-surface/60 px-2 py-1 text-xs text-green">
                        <svg className="h-3.5 w-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        {msg.fileName}
                      </div>
                    )}
                    <p className="whitespace-pre-wrap break-words">
                      {msg.fileName
                        ? msg.content.includes("\n\n")
                          ? msg.content.split("\n\n").slice(1).join("\n\n") || "(file only)"
                          : "(file only)"
                        : msg.content}
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <div key={i} className="flex justify-start">
                <div className="max-w-[75%]">
                  <div className="rounded-2xl rounded-tl-sm border border-line bg-surface px-4 py-3 text-sm text-ink">
                    <p className="whitespace-pre-wrap break-words">{msg.content}</p>
                  </div>
                  {msg.modelUsed && (
                    <ModelBadge model={msg.modelUsed} cached={msg.cached} />
                  )}
                </div>
              </div>
            )
          )}

          {/* Typing indicator */}
          {loading && (
            <div className="flex justify-start">
              <div className="rounded-2xl rounded-tl-sm border border-line bg-surface px-4 py-3">
                <span className="flex gap-1">
                  {[0, 150, 300].map((delay) => (
                    <span
                      key={delay}
                      className="inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-muted"
                      style={{ animationDelay: `${delay}ms` }}
                    />
                  ))}
                </span>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="border-t border-danger/20 bg-danger/10 px-4 py-2 text-xs text-danger">
          {error}{" "}
          <button
            onClick={() => setError(null)}
            className="ml-1 font-medium underline hover:opacity-80"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Input bar */}
      <div className="border-t border-line bg-surface px-4 py-3">
        <div className="mx-auto max-w-2xl">
          {pendingFile && (
            <div className="mb-2 flex items-center gap-2">
              <span className="flex items-center gap-1.5 rounded-md border border-green/20 bg-green-soft px-2.5 py-1 text-xs font-medium text-green">
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                {pendingFile.name}
                <span className="text-green/60">· {formatBytes(pendingFile.size)}</span>
              </span>
              <button
                onClick={() => setPendingFile(null)}
                className="text-muted hover:text-ink"
                title="Remove file"
              >
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          )}

          <div className="flex items-end gap-2">
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              accept=".pdf,.docx,.pptx,.html,.htm,.csv,.json,.xml,.txt,.md"
              onChange={onFileChange}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="mb-0.5 rounded-md p-1.5 text-muted transition-colors hover:bg-subtle hover:text-ink"
              title="Attach document"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
              </svg>
            </button>

            <textarea
              ref={textareaRef}
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Message… (Enter to send, Shift+Enter for newline)"
              className="flex-1 resize-none rounded-lg border border-line bg-paper px-3 py-2 text-sm text-ink placeholder:text-muted/50 outline-none transition-colors focus:border-green/40 focus:ring-1 focus:ring-green/20"
              disabled={loading}
            />

            <button
              onClick={() => void send()}
              disabled={!canSend}
              className="mb-0.5 rounded-lg bg-green p-2.5 text-white transition-opacity hover:opacity-90 disabled:opacity-30"
              title="Send"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
