/**
 * Fetch wrapper for the AI Gateway API.
 *
 * The JWT is kept in a module-level variable (updated via setToken) rather
 * than localStorage to avoid XSS token-theft risk on a demo app.
 * AuthContext calls setToken() whenever the user logs in or out.
 */

const BASE_URL = ""; // empty = same origin (works via Vite proxy in dev, same origin in prod)

let _token: string | null = null;

export function setToken(t: string | null): void {
  _token = t;
}

export function getToken(): string | null {
  return _token;
}

type FetchOptions = Omit<RequestInit, "headers"> & {
  headers?: Record<string, string>;
};

export async function apiFetch(path: string, init: FetchOptions = {}): Promise<Response> {
  const headers: Record<string, string> = {
    ...init.headers,
  };

  // Don't set Content-Type for FormData — browser sets it with the boundary
  if (!(init.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  if (_token) {
    headers["Authorization"] = `Bearer ${_token}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, { ...init, headers });
  return res;
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await apiFetch(path);
  if (!res.ok) {
    const text = await res.text();
    throw new ApiError(res.status, text);
  }
  return res.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await apiFetch(path, {
    method: "POST",
    body: body instanceof FormData ? body : JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new ApiError(res.status, text);
  }
  return res.json() as Promise<T>;
}

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

// ── Typed API calls ──────────────────────────────────────────────────────────

export interface OverviewData {
  // traffic
  total_requests: number;
  total_savings_usd: number;
  cache_hit_rate: number;
  avg_latency_ms: number;
  total_tokens: number;
  total_cost_usd: number;
  // gateway health
  blocked_requests: number;
  redacted_requests: number;
  fallback_requests: number;
  error_requests: number;
  // routing breakdown
  simple_requests: number;
  complex_requests: number;
}

export interface RequestEntry {
  id: string;
  created_at: string;
  model_used: string | null;
  routing_tier: string | null;
  was_cached: boolean;
  was_fallback: boolean;
  prompt_tokens: number;
  completion_tokens: number;
  estimated_cost_usd: number;
  total_savings_usd: number | null;
  total_latency_ms: number | null;
  input_guardrail_action: string | null;
  output_guardrail_action: string | null;
  guardrail_reason: string | null;
}

export interface SavingsDay {
  date: string;
  compression_savings_usd: number;
  routing_savings_usd: number;
}

export interface GuardrailDay {
  date: string;
  blocked: number;
  redacted: number;
  passed: number;
}

export interface ModelStat {
  model: string;
  requests: number;
  cost_usd: number;
}

export interface GuardrailEvent {
  id: string;
  created_at: string;
  action: string;
  reason: string | null;
  model_used: string | null;
}

export interface ApiKeyEntry {
  id: string;
  key_prefix: string;
  label: string | null;
  raw_key?: string;           // only present in create response
  created_at?: string;
  last_used_at?: string | null;
}

export interface EvalCase {
  id: string;
  category: string;
  category_label: string;
  label: string;
  input_preview: string;
  expected: string;
}

export interface EvalResult {
  id: string;
  category: string;
  label: string;
  passed: boolean;
  expected: string;
  actual: string;
  input: string;
  output: string | null;
  model: string | null;
  reason: string | null;
  redacted_types: string[];
  duration_ms: number;
}

export type SandboxMode = "routing" | "guardrail_input" | "guardrail_output";

export interface SandboxResult {
  mode: SandboxMode;
  input: string;
  action: string;
  model: string | null;
  reason: string | null;
  output: string | null;
  redacted_types: string[];
  duration_ms: number;
}

export interface ChatApiMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface ChatApiResult {
  id: string;
  model: string;
  choices: Array<{
    message: { role: string; content: string };
    finish_reason: string | null;
  }>;
  usage: { prompt_tokens: number; completion_tokens: number; total_tokens: number };
  gateway_cached: boolean;
  gateway_fallback: boolean;
}

export const api = {
  overview: (): Promise<OverviewData> => apiGet("/v1/analytics/overview"),
  requests: (limit = 20): Promise<RequestEntry[]> =>
    apiGet(`/v1/analytics/requests?limit=${limit}`),
  savingsTimeseries: (days = 7): Promise<SavingsDay[]> =>
    apiGet(`/v1/analytics/savings-timeseries?days=${days}`),
  guardrailsTimeseries: (days = 7): Promise<GuardrailDay[]> =>
    apiGet(`/v1/analytics/guardrails-timeseries?days=${days}`),
  models: (): Promise<ModelStat[]> => apiGet("/v1/analytics/models"),
  guardrailEvents: (limit = 50): Promise<GuardrailEvent[]> =>
    apiGet(`/v1/analytics/guardrail-events?limit=${limit}`),
  login: (email: string, password: string) =>
    apiPost<{ access_token: string; token_type: string }>("/auth/login", {
      email,
      password,
    }),
  register: (email: string, password: string) =>
    apiPost<{ id: string; email: string; tier: string }>("/auth/register", {
      email,
      password,
    }),
  chat: (messages: ChatApiMessage[], model = "gpt-oss-120b"): Promise<ChatApiResult> =>
    apiPost("/v1/chat/completions", { model, messages }),
  listKeys: (): Promise<ApiKeyEntry[]> => apiGet("/auth/keys"),
  createKey: (label?: string): Promise<ApiKeyEntry> =>
    apiPost("/auth/keys", { label: label ?? null }),
  evalCases: (): Promise<EvalCase[]> => apiGet("/v1/evals/cases"),
  runEvalCase: (id: string): Promise<EvalResult> =>
    apiPost("/v1/evals/run-case", { id }),
  runSandbox: (mode: SandboxMode, text: string): Promise<SandboxResult> =>
    apiPost("/v1/evals/sandbox", { mode, text }),
};
