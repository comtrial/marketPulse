"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from "@/components/ui/collapsible";
import type {
  OrchestratorResult,
  OrchestratorStep,
  ExtractResult,
} from "@/lib/api";
import { ChevronRight, Loader2 } from "lucide-react";

// ── Types ──

type Mode = "intelligence" | "extract";

interface TracePanelProps {
  mode: Mode;
  result: OrchestratorResult | null;
  extractResult: ExtractResult | null;
  isLoading: boolean;
}

// ── MCP Server color config ──

const SERVER_STYLES: Record<
  string,
  { border: string; bg: string; text: string; label: string }
> = {
  order: {
    border: "border-l-blue-500",
    bg: "bg-blue-50",
    text: "text-blue-600",
    label: "PostgreSQL",
  },
  kg: {
    border: "border-l-emerald-500",
    bg: "bg-emerald-50",
    text: "text-emerald-600",
    label: "Neo4j",
  },
  vector: {
    border: "border-l-violet-500",
    bg: "bg-violet-50",
    text: "text-violet-600",
    label: "ChromaDB",
  },
  llm: {
    border: "border-l-orange-500",
    bg: "bg-orange-50",
    text: "text-orange-600",
    label: "Claude",
  },
};

function inferServer(tool: string): string {
  if (
    tool.includes("trend") ||
    tool.includes("heatmap") ||
    tool.includes("attribute")
  )
    return "order";
  if (
    tool.includes("causal") ||
    tool.includes("chain") ||
    tool.includes("ingredient")
  )
    return "kg";
  if (tool.includes("synerg") || tool.includes("similar")) return "vector";
  return "llm";
}

function getServerStyle(server?: string, tool?: string) {
  const key = server ?? (tool ? inferServer(tool) : "llm");
  return SERVER_STYLES[key] ?? SERVER_STYLES.llm;
}

// ── Collapsible JSON block ──

function JsonBlock({ data }: { data: Record<string, unknown> }) {
  const [open, setOpen] = useState(false);

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger
        className="flex items-center gap-1 text-[10px] font-medium text-gray-400 hover:text-gray-600 transition-colors"
      >
        <ChevronRight
          className={`size-3 transition-transform ${open ? "rotate-90" : ""}`}
        />
        Input JSON
      </CollapsibleTrigger>
      <CollapsibleContent>
        <pre className="mt-1.5 max-h-40 overflow-auto rounded-md bg-gray-50 p-2 font-mono text-[11px] leading-relaxed text-gray-600 border border-gray-100">
          {JSON.stringify(data, null, 2)}
        </pre>
      </CollapsibleContent>
    </Collapsible>
  );
}

// ── Tool Call Step ──

function ToolCallStep({
  step,
  isLast,
}: {
  step: OrchestratorStep;
  isLast: boolean;
}) {
  const style = getServerStyle(step.mcp_server, step.tool);

  return (
    <div className="relative">
      {/* Connector line */}
      {!isLast && (
        <div className="absolute left-3 top-full h-4 w-px bg-gray-200" />
      )}

      <div className={`rounded-lg border border-gray-200 border-l-2 ${style.border} bg-white`}>
        {/* Reasoning */}
        {step.reasoning && (
          <div className="border-b border-gray-100 bg-gray-50/50 px-3 py-2">
            <p className="text-xs italic text-gray-500 leading-relaxed">
              <span className="not-italic">💭</span> {step.reasoning}
            </p>
          </div>
        )}

        {/* Tool info */}
        <div className="px-3 py-2.5">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-semibold text-gray-900">
              {step.tool}
            </span>
            <span
              className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium ${style.bg} ${style.text}`}
            >
              {step.mcp_server ?? inferServer(step.tool ?? "")}
            </span>
            {step.success === false && (
              <span className="rounded bg-red-50 px-1.5 py-0.5 text-[10px] font-medium text-red-500">
                failed
              </span>
            )}
          </div>

          {/* Input JSON */}
          {step.tool_input && Object.keys(step.tool_input).length > 0 && (
            <div className="mt-2">
              <JsonBlock data={step.tool_input} />
            </div>
          )}

          {/* Output summary */}
          {step.tool_output_summary && (
            <p className="mt-2 text-xs text-gray-600 leading-relaxed">
              {step.tool_output_summary}
            </p>
          )}

          {/* Latency */}
          {step.latency_ms != null && (
            <div className="mt-2 flex justify-end">
              <span className="font-mono text-[10px] text-gray-400">
                {step.latency_ms.toFixed(0)}ms
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Connector arrow */}
      {!isLast && (
        <div className="flex justify-center py-1">
          <span className="text-[10px] text-gray-300">│</span>
        </div>
      )}
    </div>
  );
}

// ── Final Answer Step ──

function FinalAnswerStep({ step }: { step: OrchestratorStep }) {
  return (
    <div className="rounded-lg border border-gray-200 border-l-2 border-l-gray-400 bg-white">
      {/* Reasoning */}
      {step.reasoning && (
        <div className="border-b border-gray-100 bg-gray-50/50 px-3 py-2">
          <p className="text-xs italic text-gray-500 leading-relaxed">
            <span className="not-italic">💭</span> {step.reasoning}
          </p>
        </div>
      )}

      <div className="px-3 py-2.5">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-gray-900">
            📝 최종 답변
          </span>
        </div>
        {step.answer && (
          <p className="mt-2 text-xs text-gray-700 leading-relaxed whitespace-pre-wrap">
            {step.answer.length > 200
              ? step.answer.slice(0, 200) + "..."
              : step.answer}
          </p>
        )}
      </div>
    </div>
  );
}

// ── Trace Summary ──

function TraceSummary({ result }: { result: OrchestratorResult }) {
  const toolSteps = result.steps.filter((s) => s.type === "tool_call");
  const serverCounts: Record<string, number> = {};
  for (const s of toolSteps) {
    const key = s.mcp_server ?? inferServer(s.tool ?? "");
    serverCounts[key] = (serverCounts[key] ?? 0) + 1;
  }
  const totalTime = toolSteps.reduce(
    (sum, s) => sum + (s.latency_ms ?? 0),
    0
  );

  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2.5">
      <p className="text-[10px] font-medium uppercase tracking-wider text-gray-400 mb-2">
        Summary
      </p>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
        <div className="flex items-center gap-1">
          <span className="text-gray-400">Steps</span>
          <span className="font-mono font-medium text-gray-700">
            {result.total_steps}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-gray-400">Cost</span>
          <span className="font-mono font-medium text-gray-700">
            ${result.total_cost_usd.toFixed(4)}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-gray-400">Time</span>
          <span className="font-mono font-medium text-gray-700">
            {totalTime.toFixed(0)}ms
          </span>
        </div>
      </div>
      {/* Tool distribution */}
      <div className="mt-2 flex gap-1.5">
        {Object.entries(serverCounts).map(([server, count]) => {
          const style = SERVER_STYLES[server] ?? SERVER_STYLES.llm;
          return (
            <span
              key={server}
              className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium ${style.bg} ${style.text}`}
            >
              {server} x{count}
            </span>
          );
        })}
      </div>
    </div>
  );
}

// ── Intelligence Trace ──

function IntelligenceTrace({ result }: { result: OrchestratorResult }) {
  return (
    <div className="flex flex-col gap-2 p-3">
      {/* Header */}
      <div className="mb-1">
        <p className="text-[10px] font-medium uppercase tracking-wider text-gray-400">
          Trace
        </p>
        <p className="mt-0.5 font-mono text-[11px] text-gray-500 truncate">
          {result.trace_id}
        </p>
      </div>

      <Separator />

      {/* Steps */}
      <div className="flex flex-col gap-1">
        {result.steps.map((step, idx) => {
          if (step.type === "tool_call") {
            return (
              <ToolCallStep
                key={step.step}
                step={step}
                isLast={idx === result.steps.length - 1}
              />
            );
          }
          if (step.type === "final_answer") {
            return <FinalAnswerStep key={step.step} step={step} />;
          }
          return null;
        })}
      </div>

      <Separator />

      {/* Summary */}
      <TraceSummary result={result} />
    </div>
  );
}

// ── Extract Trace ──

interface ExtractStepDef {
  label: string;
  server: string;
  description: (r: ExtractResult) => string;
}

const EXTRACT_STEPS: ExtractStepDef[] = [
  {
    label: "Vector Search",
    server: "vector",
    description: (r) =>
      `${r.examples_used.length}건의 유사 제품 검색 (avg similarity: ${(r.avg_similarity * 100).toFixed(1)}%)`,
  },
  {
    label: "LLM Extraction",
    server: "llm",
    description: (r) =>
      `${Object.keys(r.attributes).length}개 속성 추출 ($${r.cost_usd.toFixed(4)})`,
  },
  {
    label: "Validation",
    server: "validation",
    description: (r) =>
      r.validation_passed
        ? `검증 통과 (경고 ${r.warnings.length}건)`
        : `검증 실패: ${r.errors.join(", ")}`,
  },
  {
    label: "Graph Sync",
    server: "kg",
    description: (r) =>
      r.graph_synced ? "Neo4j 동기화 완료" : "Neo4j 미동기화",
  },
];

function ExtractTrace({ result }: { result: ExtractResult }) {
  const validationStyle = {
    border: "border-l-gray-400",
    bg: "bg-gray-50",
    text: "text-gray-600",
  };

  return (
    <div className="flex flex-col gap-2 p-3">
      <div className="mb-1">
        <p className="text-[10px] font-medium uppercase tracking-wider text-gray-400">
          Extract Trace
        </p>
      </div>

      <Separator />

      <div className="flex flex-col gap-1">
        {EXTRACT_STEPS.map((stepDef, idx) => {
          const isValidation = stepDef.server === "validation";
          const style = isValidation
            ? validationStyle
            : SERVER_STYLES[stepDef.server] ?? SERVER_STYLES.llm;
          const isLast = idx === EXTRACT_STEPS.length - 1;

          return (
            <div key={stepDef.label} className="relative">
              <div
                className={`rounded-lg border border-gray-200 border-l-2 ${style.border} bg-white`}
              >
                <div className="px-3 py-2.5">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-gray-900">
                      {stepDef.label}
                    </span>
                    <span
                      className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium ${style.bg} ${style.text}`}
                    >
                      {stepDef.server}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-gray-600">
                    {stepDef.description(result)}
                  </p>
                </div>
              </div>
              {!isLast && (
                <div className="flex justify-center py-1">
                  <span className="text-[10px] text-gray-300">│</span>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <Separator />

      {/* Summary */}
      <div className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2.5">
        <p className="text-[10px] font-medium uppercase tracking-wider text-gray-400 mb-2">
          Summary
        </p>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
          <div className="flex items-center gap-1">
            <span className="text-gray-400">Latency</span>
            <span className="font-mono font-medium text-gray-700">
              {result.latency_ms.toFixed(0)}ms
            </span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-gray-400">Cost</span>
            <span className="font-mono font-medium text-gray-700">
              ${result.cost_usd.toFixed(4)}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-gray-400">Attributes</span>
            <span className="font-mono font-medium text-gray-700">
              {Object.keys(result.attributes).length}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Loading Pulse ──

function TraceSkeleton() {
  return (
    <div className="flex flex-col gap-3 p-3">
      <div className="mb-1">
        <div className="h-2.5 w-12 animate-pulse rounded bg-gray-200" />
        <div className="mt-1.5 h-3 w-40 animate-pulse rounded bg-gray-100" />
      </div>
      <Separator />
      {[1, 2, 3].map((i) => (
        <div key={i} className="flex flex-col gap-2">
          <div className="rounded-lg border border-gray-200 border-l-2 border-l-gray-200 p-3">
            <div className="h-2.5 w-24 animate-pulse rounded bg-gray-200" />
            <div className="mt-2 h-2 w-full animate-pulse rounded bg-gray-100" />
            <div className="mt-1 h-2 w-3/4 animate-pulse rounded bg-gray-100" />
          </div>
          {i < 3 && (
            <div className="flex justify-center">
              <span className="text-[10px] text-gray-200">│</span>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Empty State ──

function EmptyTrace() {
  return (
    <div className="flex flex-1 items-center justify-center p-6">
      <div className="text-center">
        <p className="text-xs text-gray-400">
          질문을 실행하면 LLM의 사고 과정이
          <br />
          이곳에 표시됩니다.
        </p>
      </div>
    </div>
  );
}

// ── Main Component ──

export function TracePanel({
  mode,
  result,
  extractResult,
  isLoading,
}: TracePanelProps) {
  return (
    <div className="flex h-full flex-col border-l border-gray-200 bg-white">
      {/* Panel header */}
      <div className="flex-none border-b border-gray-200 px-3 py-2.5">
        <p className="text-xs font-semibold text-gray-900">Trace</p>
        <p className="text-[10px] text-gray-400">LLM Decision Process</p>
      </div>

      {/* Content */}
      <ScrollArea className="flex-1">
        {isLoading ? (
          <TraceSkeleton />
        ) : mode === "intelligence" && result ? (
          <IntelligenceTrace result={result} />
        ) : mode === "extract" && extractResult ? (
          <ExtractTrace result={extractResult} />
        ) : (
          <EmptyTrace />
        )}
      </ScrollArea>
    </div>
  );
}
