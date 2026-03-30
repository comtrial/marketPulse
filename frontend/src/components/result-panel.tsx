"use client";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Markdown } from "@/components/ui/markdown";
import {
  determineVisualizations,
  VisualizationRenderer,
} from "@/components/visualizations";
import type { OrchestratorResult, ExtractResult } from "@/lib/api";
import { Loader2 } from "lucide-react";

// ── Types ──

type Mode = "intelligence" | "extract";

interface ResultPanelProps {
  mode: Mode;
  result: OrchestratorResult | null;
  extractResult: ExtractResult | null;
  isLoading: boolean;
}

// ── Architecture Overview (initial state) ──

function ArchitectureOverview() {
  const dataSources = [
    { name: "Neo4j", role: "왜?", desc: "인과 체인 · 성분 시너지", color: "border-emerald-300 bg-emerald-50", dot: "bg-emerald-500", tools: ["query_causal_chain", "find_trending_ingredients", "find_ingredient_synergies", "get_product_graph"] },
    { name: "PostgreSQL", role: "얼마나?", desc: "월별 트렌드 · 속성 히트맵", color: "border-blue-300 bg-blue-50", dot: "bg-blue-500", tools: ["get_attribute_trend", "get_country_attribute_heatmap"] },
    { name: "ChromaDB", role: "비슷한?", desc: "Few-Shot 유사 사례 검색", color: "border-violet-300 bg-violet-50", dot: "bg-violet-500", tools: ["vector_search (내부)"] },
  ];

  return (
    <div className="flex flex-1 items-center justify-center p-6">
      <div className="w-full max-w-xl">
        {/* Title */}
        <div className="mb-6 text-center">
          <h2 className="text-lg font-bold text-gray-900 tracking-tight">
            MarketPulse
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            K-Beauty Cross-Border Intelligence Engine
          </p>
        </div>

        {/* Data Sources */}
        <div className="grid grid-cols-3 gap-3 mb-5">
          {dataSources.map((ds) => (
            <div key={ds.name} className={`rounded-lg border p-3 ${ds.color}`}>
              <div className="flex items-center gap-1.5 mb-1.5">
                <span className={`inline-block size-2 rounded-full ${ds.dot}`} />
                <span className="text-xs font-bold text-gray-900">{ds.name}</span>
              </div>
              <p className="text-[10px] font-medium text-gray-600 mb-1">&ldquo;{ds.role}&rdquo;</p>
              <p className="text-[10px] text-gray-500 leading-relaxed">{ds.desc}</p>
              <div className="mt-2 flex flex-wrap gap-1">
                {ds.tools.map((t) => (
                  <span key={t} className="rounded bg-white/60 px-1 py-0.5 font-mono text-[8px] text-gray-500">
                    {t.length > 20 ? t.slice(0, 18) + "…" : t}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Arrows down */}
        <div className="flex justify-center mb-3">
          <div className="flex items-center gap-4 text-gray-300">
            <span className="text-sm">↓</span>
            <span className="text-sm">↓</span>
            <span className="text-sm">↓</span>
          </div>
        </div>

        {/* Orchestrator */}
        <div className="rounded-xl border-2 border-gray-200 bg-white p-4 text-center shadow-sm">
          <div className="flex items-center justify-center gap-2 mb-2">
            <span className="inline-block size-2.5 rounded-full bg-orange-500" />
            <span className="text-sm font-bold text-gray-900">LLM Orchestrator</span>
            <span className="rounded bg-orange-50 px-1.5 py-0.5 text-[10px] font-medium text-orange-600">
              ReAct Loop
            </span>
          </div>
          <p className="text-xs text-gray-500 mb-3">
            질문에 따라 도구를 자율 선택 · 실행 · 종합
          </p>
          <div className="flex justify-center gap-2">
            <div className="rounded-md border border-amber-100 bg-amber-50 px-2 py-1 text-[10px] font-medium text-amber-700">
              Think
            </div>
            <span className="self-center text-xs text-gray-300">→</span>
            <div className="rounded-md border border-gray-200 bg-gray-50 px-2 py-1 text-[10px] font-medium text-gray-600">
              Act
            </div>
            <span className="self-center text-xs text-gray-300">→</span>
            <div className="rounded-md border border-sky-100 bg-sky-50 px-2 py-1 text-[10px] font-medium text-sky-700">
              Observe
            </div>
            <span className="self-center text-xs text-gray-300">→</span>
            <span className="self-center text-[10px] text-gray-400 italic">repeat</span>
          </div>
        </div>

        {/* Bottom instruction */}
        <p className="mt-5 text-center text-xs text-gray-400">
          왼쪽에서 질문을 선택하면 LLM이 도구를 자동 선택하여 분석합니다
        </p>
      </div>
    </div>
  );
}

// ── Loading Skeleton ──

function LoadingSkeleton() {
  return (
    <div className="flex flex-1 items-center justify-center p-8">
      <div className="flex flex-col items-center gap-3">
        <Loader2 className="size-6 animate-spin text-gray-400" />
        <p className="text-sm text-gray-400">분석 중...</p>
      </div>
    </div>
  );
}

// ── Intelligence Result — Visualization-based ──

function IntelligenceResult({ result }: { result: OrchestratorResult }) {
  const visuals = determineVisualizations(result.steps);

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* Data visualizations from tool outputs */}
      {visuals.map((visual, idx) => (
        <VisualizationRenderer key={idx} visual={visual} />
      ))}

      {/* Fallback: if no visualizations rendered, show tool summaries */}
      {visuals.length === 0 && result.steps
        .filter((s) => s.type === "tool_call")
        .map((step) => (
          <Card key={step.step} size="sm" className="border-gray-200">
            <CardHeader>
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-gray-500">
                  Step {step.step}
                </span>
                <McpBadge server={step.mcp_server} tool={step.tool ?? "unknown"} />
              </div>
              <CardTitle className="text-sm">{step.tool}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-gray-600 leading-relaxed">
                {step.tool_output_summary}
              </p>
            </CardContent>
          </Card>
        ))}

      {/* LLM insight / final answer — Markdown rendered */}
      <Card className="border-gray-900/10 bg-gray-50">
        <CardHeader>
          <CardTitle className="text-sm text-gray-900">
            LLM 분석 결과
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Markdown content={result.answer} />
        </CardContent>
      </Card>
    </div>
  );
}

// ── MCP Badge ──

function McpBadge({
  server,
  tool,
}: {
  server?: string;
  tool: string;
}) {
  const colorMap: Record<string, string> = {
    order: "bg-blue-50 text-blue-600",
    kg: "bg-emerald-50 text-emerald-600",
    vector: "bg-violet-50 text-violet-600",
    llm: "bg-orange-50 text-orange-600",
  };

  const serverKey = server ?? inferServer(tool);
  const classes = colorMap[serverKey] ?? "bg-gray-50 text-gray-600";

  return (
    <span className={`inline-flex rounded px-1.5 py-0.5 text-[10px] font-medium ${classes}`}>
      {serverKey}
    </span>
  );
}

function inferServer(tool: string): string {
  if (tool.includes("trend") || tool.includes("heatmap") || tool.includes("attribute")) return "order";
  if (tool.includes("causal") || tool.includes("chain") || tool.includes("ingredient")) return "kg";
  if (tool.includes("synerg") || tool.includes("similar")) return "vector";
  return "llm";
}

// ── Extract Result ──

function ExtractResultView({ result }: { result: ExtractResult }) {
  const attrEntries = Object.entries(result.attributes);

  return (
    <div className="flex flex-col gap-4 p-4 lg:flex-row">
      {/* Attributes card */}
      <Card className="flex-1">
        <CardHeader>
          <CardTitle className="text-sm">추출 속성</CardTitle>
          <CardDescription>
            {attrEntries.length}개 속성 추출됨
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-2">
            {attrEntries.map(([key, value]) => (
              <div key={key} className="flex items-baseline gap-2">
                <span className="shrink-0 text-xs font-medium text-gray-500 w-32 truncate">
                  {key}
                </span>
                <span className="text-sm text-gray-800 font-mono">
                  {Array.isArray(value) ? value.join(", ") : String(value)}
                </span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Meta card */}
      <Card className="w-full lg:w-64">
        <CardHeader>
          <CardTitle className="text-sm">메타 정보</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-3 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-500">유사도</span>
              <span className="font-mono text-gray-800">
                {(result.avg_similarity * 100).toFixed(1)}%
              </span>
            </div>
            <Separator />
            <div className="flex justify-between">
              <span className="text-gray-500">검증</span>
              <span
                className={
                  result.validation_passed
                    ? "text-emerald-600"
                    : "text-red-500"
                }
              >
                {result.validation_passed ? "통과" : "실패"}
              </span>
            </div>
            <Separator />
            <div className="flex justify-between">
              <span className="text-gray-500">그래프 동기화</span>
              <span
                className={
                  result.graph_synced
                    ? "text-emerald-600"
                    : "text-gray-400"
                }
              >
                {result.graph_synced ? "완료" : "미완료"}
              </span>
            </div>
            <Separator />
            <div className="flex justify-between">
              <span className="text-gray-500">참조 예시</span>
              <span className="font-mono text-gray-800">
                {result.examples_used.length}건
              </span>
            </div>
            <Separator />
            <div className="flex justify-between">
              <span className="text-gray-500">비용</span>
              <span className="font-mono text-gray-800">
                ${result.cost_usd.toFixed(4)}
              </span>
            </div>
            <Separator />
            <div className="flex justify-between">
              <span className="text-gray-500">지연</span>
              <span className="font-mono text-gray-800">
                {result.latency_ms.toFixed(0)}ms
              </span>
            </div>

            {/* Errors / Warnings */}
            {result.errors.length > 0 && (
              <>
                <Separator />
                <div className="flex flex-col gap-1">
                  <span className="text-xs font-medium text-red-500">
                    오류 ({result.errors.length})
                  </span>
                  {result.errors.map((e, i) => (
                    <p key={i} className="text-xs text-red-400">
                      {e}
                    </p>
                  ))}
                </div>
              </>
            )}
            {result.warnings.length > 0 && (
              <>
                <Separator />
                <div className="flex flex-col gap-1">
                  <span className="text-xs font-medium text-orange-500">
                    경고 ({result.warnings.length})
                  </span>
                  {result.warnings.map((w, i) => (
                    <p key={i} className="text-xs text-orange-400">
                      {w}
                    </p>
                  ))}
                </div>
              </>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ── Main Component ──

export function ResultPanel({
  mode,
  result,
  extractResult,
  isLoading,
}: ResultPanelProps) {
  // Loading
  if (isLoading) {
    return <LoadingSkeleton />;
  }

  // No result yet
  if (mode === "intelligence" && !result) {
    return <ArchitectureOverview />;
  }
  if (mode === "extract" && !extractResult) {
    return <ArchitectureOverview />;
  }

  // Intelligence result
  if (mode === "intelligence" && result) {
    return (
      <ScrollArea className="flex-1">
        <IntelligenceResult result={result} />
      </ScrollArea>
    );
  }

  // Extract result
  if (mode === "extract" && extractResult) {
    return (
      <ScrollArea className="flex-1">
        <ExtractResultView result={extractResult} />
      </ScrollArea>
    );
  }

  return <ArchitectureOverview />;
}
