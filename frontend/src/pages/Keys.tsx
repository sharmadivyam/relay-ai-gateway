import { useState, useEffect, useRef, FormEvent } from "react";
import { api, ApiError, ApiKeyEntry } from "../api/client";

function formatDate(iso?: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <button
      onClick={() => void copy()}
      className="flex items-center gap-1.5 rounded-md border border-warn/30 bg-surface px-2.5 py-1.5 text-xs font-medium text-warn transition-colors hover:border-warn/60"
    >
      {copied ? (
        <>
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
          Copied
        </>
      ) : (
        <>
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
          Copy
        </>
      )}
    </button>
  );
}

export function Keys() {
  const [keys, setKeys] = useState<ApiKeyEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [label, setLabel] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [newKey, setNewKey] = useState<ApiKeyEntry | null>(null);

  const labelInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { void loadKeys(); }, []);

  useEffect(() => {
    if (showForm) setTimeout(() => labelInputRef.current?.focus(), 50);
  }, [showForm]);

  async function loadKeys() {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listKeys();
      setKeys(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load keys");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setCreating(true);
    setCreateError(null);
    try {
      const created = await api.createKey(label.trim() || undefined);
      setNewKey(created);
      setLabel("");
      setShowForm(false);
      await loadKeys();
    } catch (err) {
      let msg = "Failed to create key";
      if (err instanceof ApiError) {
        try { msg = (JSON.parse(err.message) as { detail?: string }).detail ?? err.message; }
        catch { msg = err.message; }
      }
      setCreateError(msg);
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="section-label mb-2">Access</p>
          <h2 className="text-3xl font-bold tracking-tight text-ink">API Keys</h2>
          <p className="mt-1 text-sm text-muted">
            Create and manage keys for machine-to-machine access
          </p>
        </div>
        <button
          onClick={() => { setShowForm((v) => !v); setCreateError(null); }}
          className={`rounded-md px-4 py-2 text-sm font-semibold transition-all ${
            showForm
              ? "border border-line bg-surface text-muted hover:text-ink"
              : "bg-green text-white hover:opacity-90"
          }`}
        >
          {showForm ? "Cancel" : "New key"}
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <form
          onSubmit={(e) => void handleCreate(e)}
          className="rounded-xl border border-line bg-surface p-5"
        >
          <p className="mb-3 text-sm font-semibold text-ink">Create new API key</p>
          <div className="flex gap-3">
            <input
              ref={labelInputRef}
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Label (optional)"
              className="flex-1 rounded-md border border-line bg-paper px-3 py-2 text-sm text-ink placeholder:text-muted/50 outline-none transition-colors focus:border-green/40 focus:ring-1 focus:ring-green/20"
            />
            <button
              type="submit"
              disabled={creating}
              className="rounded-md bg-green px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
            >
              {creating ? "Creating…" : "Create"}
            </button>
          </div>
          {createError && (
            <p className="mt-2 text-xs text-danger">{createError}</p>
          )}
        </form>
      )}

      {/* New key reveal banner */}
      {newKey?.raw_key && (
        <div className="rounded-xl border border-warn/20 bg-warn/5 p-4">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-sm font-semibold text-warn">
              Your new API key — copy it now
            </p>
            <button
              onClick={() => setNewKey(null)}
              className="text-muted hover:text-ink"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <p className="mb-3 text-xs text-muted">
            This key will not be shown again. Store it somewhere safe.
          </p>
          <div className="flex items-center gap-2 rounded-md border border-line bg-surface px-3 py-2">
            <code className="flex-1 select-all break-all font-mono text-xs text-ink">
              {newKey.raw_key}
            </code>
            <CopyButton text={newKey.raw_key} />
          </div>
          {newKey.label && (
            <p className="mt-2 text-xs text-muted">Label: {newKey.label}</p>
          )}
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-danger/20 bg-danger/10 px-4 py-3 text-sm text-danger">
          {error}
        </div>
      )}

      {/* Keys table */}
      {loading ? (
        <div className="space-y-2">
          {[1, 2].map((n) => (
            <div key={n} className="h-12 animate-pulse rounded-lg bg-subtle" />
          ))}
        </div>
      ) : keys.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-line py-16 text-center">
          <svg
            className="mb-3 h-8 w-8 text-muted/40"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"
            />
          </svg>
          <p className="text-sm text-muted">No API keys yet</p>
          <p className="mt-1 text-xs text-muted/70">Click "New key" to create one</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-line bg-surface">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left">
                {["Prefix", "Label", "Created (IST)", "Last used (IST)"].map((h) => (
                  <th key={h} className="section-label px-5 py-3.5 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-line/60">
              {keys.map((k) => (
                <tr key={k.id} className="hover:bg-subtle/60">
                  <td className="px-5 py-3.5 font-mono text-xs text-ink">
                    {k.key_prefix}…
                  </td>
                  <td className="px-5 py-3.5 text-ink">
                    {k.label ?? (
                      <span className="italic text-muted/60">no label</span>
                    )}
                  </td>
                  <td className="px-5 py-3.5 text-xs text-muted">
                    {formatDate(k.created_at)}
                  </td>
                  <td className="px-5 py-3.5 text-xs text-muted">
                    {formatDate(k.last_used_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
