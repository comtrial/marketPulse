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

export interface ExtractTraceDetail {
  vector_search: {
    gold_id: string;
    raw_input: string;
    similarity: number;
    combined_score: number;
    extracted_output: Record<string, unknown>;
  }[];
  few_shot_prompt: string;
  llm_response: {
    model: string;
    input_tokens: number;
    output_tokens: number;
  };
  validation_details: {
    passed: boolean;
    errors: string[];
    warnings: string[];
  };
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
  trace?: ExtractTraceDetail;
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

// ── Eval Types ──

export interface EvalSessionHistory {
  trace_id: string;
  used_discovered: boolean;
}

export interface EvalCoverageCell {
  causal: boolean;
  data: boolean;
  diversity: boolean;
  full: boolean;
  data_count: number;
  attr_diversity: number;
  gaps: string[];
}

export interface EvalEfficiencySession {
  trace_id: string;
  user_query: string;
  created_at: string;
  analyst_cost: number;
  scout_cost: number;
  total_cost: number;
  used_discovered: boolean;
}

export interface EvalEfficiencySummary {
  total_sessions: number;
  avg_analyst_cost: number;
  avg_scout_cost: number;
  avg_total_cost: number;
  scout_cost_ratio: number;
  with_discovered: { count: number; avg_total_cost: number };
  without_discovered: { count: number; avg_total_cost: number };
  quality_premium: number | null;
}

export interface EvalFullResult {
  pattern_discovery: {
    total_proposed: number;
    approved: number;
    rejected: number;
    pending: number;
    approval_rate: number;
    seed_relations: number;
    discovered_relations: number;
    relation_growth: number;
    by_type: Record<string, number>;
  };
  answer_quality: {
    total_analyses: number;
    used_discovered_link: number;
    discovered_usage_rate: number;
    session_history: EvalSessionHistory[];
  };
  reasoning_coverage: {
    causal_evidence_rate: number;
    full_coverage_cells: number;
    total_cells: number;
    full_coverage_rate: number;
    matrix: Record<string, EvalCoverageCell>;
  };
  system_efficiency: {
    status: string;
    sessions: EvalEfficiencySession[];
    summary?: EvalEfficiencySummary;
  };
  before_after_pairs: BeforeAfterPair[];
}

export interface BeforeAfterPair {
  query: string;
  before_trace_id: string;
  before_answer: string;
  before_at: string;
  after_trace_id: string;
  after_answer: string;
  after_at: string;
}

export interface Proposal {
  id: number;
  source_concept: string;
  target_concept: string;
  relationship_type: string;
  evidence: Record<string, unknown>;
  reasoning: string;
  status: string;
  created_at: string;
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

  evalFull: () => fetchApi<EvalFullResult>("/eval/full"),

  evalBeforeAfter: () => fetchApi<BeforeAfterPair[]>("/eval/before-after-pairs"),

  knowledgeProposals: () => fetchApi<Proposal[]>("/knowledge/proposals"),

  getResult: (traceId: string) =>
    fetchApi<OrchestratorResult>(`/orchestrator/result/${traceId}`),

  getResults: (limit?: number) =>
    fetchApi<ResultSummary[]>(`/orchestrator/results?limit=${limit ?? 20}`),

  health: () => fetchApi<{ status: string; checks: Record<string, boolean> }>("/health"),
};
