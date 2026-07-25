import { useState, DragEvent, useRef, ChangeEvent } from "react";
import { apiFetch, ApiError } from "../api/client";

interface IngestResponse {
  markdown: string;
  original_bytes: number;
  filename: string;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function Documents() {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<IngestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function upload(file: File) {
    setUploading(true);
    setError(null);
    setResult(null);

    const form = new FormData();
    form.append("file", file);

    try {
      const res = await apiFetch("/v1/documents/ingest", {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        const text = await res.text();
        throw new ApiError(res.status, text);
      }
      const data = (await res.json()) as IngestResponse;
      setResult(data);
    } catch (err) {
      if (err instanceof ApiError) {
        try {
          const parsed = JSON.parse(err.message);
          setError(parsed.detail ?? err.message);
        } catch {
          setError(err.message);
        }
      } else {
        setError("Upload failed — is the gateway running?");
      }
    } finally {
      setUploading(false);
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) void upload(file);
  }

  function onFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) void upload(file);
    e.target.value = "";
  }

  return (
    <div className="space-y-8">
      <div>
        <p className="section-label mb-2">Ingestion</p>
        <h2 className="text-3xl font-bold tracking-tight text-ink">Documents</h2>
        <p className="mt-1 text-sm text-muted">
          Upload a file — PDF, DOCX, PPTX, HTML, CSV, and more
        </p>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-8 py-16 transition-colors ${
          dragging
            ? "border-green/50 bg-green-soft"
            : "border-line hover:border-muted/40 hover:bg-subtle/60"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          onChange={onFileChange}
          accept=".pdf,.docx,.pptx,.html,.htm,.csv,.json,.xml,.txt,.md"
        />
        {uploading ? (
          <div className="flex items-center gap-2 text-sm text-muted">
            <svg className="h-5 w-5 animate-spin text-green" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Converting to Markdown…
          </div>
        ) : (
          <>
            <svg
              className="mb-3 h-10 w-10 text-muted/50"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
              />
            </svg>
            <p className="text-sm font-semibold text-ink">
              Drag &amp; drop a file, or click to browse
            </p>
            <p className="mt-1 text-xs text-muted">PDF · DOCX · PPTX · HTML · CSV · …</p>
          </>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-danger/20 bg-danger/10 px-4 py-3 text-sm text-danger">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-3">
          <div className="flex items-center justify-between rounded-xl border border-line bg-surface px-4 py-3">
            <div className="flex items-center gap-3">
              <span className="rounded border border-green/20 bg-green-soft px-2 py-0.5 text-xs font-medium text-green">
                {result.filename.split(".").pop()?.toUpperCase() ?? "FILE"}
              </span>
              <span className="text-sm font-medium text-ink">{result.filename}</span>
            </div>
            <span className="text-xs text-muted">{formatBytes(result.original_bytes)}</span>
          </div>

          <div className="overflow-hidden rounded-xl border border-line bg-surface">
            <div className="border-b border-line px-4 py-2">
              <span className="section-label">Markdown preview</span>
            </div>
            <pre className="max-h-[500px] overflow-auto whitespace-pre-wrap break-words px-4 py-4 font-mono text-xs leading-relaxed text-ink/80">
              {result.markdown}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
