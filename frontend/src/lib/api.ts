const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// ── Types ──

export interface OrchestratorStep {
  step: number;
  type: "tool_call" | "final_answer";
  reasoning: string;
  tool?: string;
  tool_input?: Record<string, unknown>;
  tool_output?: unknown;
  tool_output_summary?: string;
  mcp_server?: string;
  latency_ms?: number;
  success?: boolean;
  answer?: string;
}

export interface OrchestratorResult {
  answer: string;
  trace_id: string;
  user_query?: string;
  steps: OrchestratorStep[];
  total_steps: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
}

export interface ExtractResult {
  attributes: Record<string, unknown>;
  validation_passed: boolean;
  errors: string[];
  warnings: string[];
  examples_used: string[];
  avg_similarity: number;
  cost_usd: number;
  latency_ms: number;
  graph_synced: boolean;
}

export interface ExtractStats {
  total_extractions: number;
  total_cost_usd: number;
  graph_synced_count: number;
  graph_synced_ratio: number;
  error_count: number;
  error_ratio: number;
  avg_latency_ms: number;
}

export interface HeatmapData {
  productType: string;
  period: string;
  matrix: Record<string, Record<string, number>>;
  countries: string[];
}

export interface TrendData {
  attribute: string;
  type: string;
  trend: Record<string, { month: string; total: number; withAttr: number; percentage: number }[]>;
}

export interface ResultSummary {
  trace_id: string;
  user_query: string;
  total_steps: number;
  total_cost_usd: number;
  created_at: string;
}

// ── API Calls ──

export const api = {
  ask: (query: string) =>
    fetchApi<OrchestratorResult>("/orchestrator/ask", {
      method: "POST",
      body: JSON.stringify({ query }),
    }),

  extract: (productName: string) =>
    fetchApi<ExtractResult>("/extract", {
      method: "POST",
      body: JSON.stringify({ product_name: productName }),
    }),

  stats: () => fetchApi<ExtractStats>("/extract/stats"),

  heatmap: (type: string, start: string, end: string) =>
    fetchApi<HeatmapData>(`/intelligence/heatmap?type=${type}&start=${start}&end=${end}`),

  trend: (attribute: string, type: string, countries: string) =>
    fetchApi<TrendData>(`/intelligence/trend?attribute=${attribute}&type=${type}&countries=${countries}`),

  causalChain: (country: string) =>
    fetchApi<Record<string, unknown>[]>(`/kg/causal-chain/${country}`),

  getResult: (traceId: string) =>
    fetchApi<OrchestratorResult>(`/orchestrator/result/${traceId}`),

  getResults: (limit?: number) =>
    fetchApi<ResultSummary[]>(`/orchestrator/results?limit=${limit ?? 20}`),

  health: () => fetchApi<{ status: string; checks: Record<string, boolean> }>("/health"),
};
