"use client";

import { useState } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Markdown } from "@/components/ui/markdown";
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
import { ChevronRight } from "lucide-react";

// ── Types ──

type Mode = "intelligence" | "extract";

interface TracePanelProps {
  mode: Mode;
  result: OrchestratorResult | null;
  extractResult: ExtractResult | null;
  isLoading: boolean;
}

// ── MCP Server config ──

const SERVER_STYLES: Record<
  string,
  { border: string; bg: string; text: string; label: string; dot: string }
> = {
  order: {
    border: "border-l-blue-500",
    bg: "bg-blue-50",
    text: "text-blue-600",
    label: "PostgreSQL",
    dot: "bg-blue-500",
  },
  kg: {
    border: "border-l-emerald-500",
    bg: "bg-emerald-50",
    text: "text-emerald-600",
    label: "Neo4j",
    dot: "bg-emerald-500",
  },
  vector: {
    border: "border-l-violet-500",
    bg: "bg-violet-50",
    text: "text-violet-600",
    label: "ChromaDB",
    dot: "bg-violet-500",
  },
  llm: {
    border: "border-l-orange-500",
    bg: "bg-orange-50",
    text: "text-orange-600",
    label: "Claude",
    dot: "bg-orange-500",
  },
};

function inferServer(tool: string): string {
  if (tool.includes("trend") || tool.includes("heatmap") || tool.includes("attribute")) return "order";
  if (tool.includes("causal") || tool.includes("chain") || tool.includes("ingredient")) return "kg";
  if (tool.includes("synerg") || tool.includes("similar")) return "vector";
  return "llm";
}

function getServerStyle(server?: string, tool?: string) {
  const key = server ?? (tool ? inferServer(tool) : "llm");
  return SERVER_STYLES[key] ?? SERVER_STYLES.llm;
}

// ── Collapsible JSON blocks ──

function JsonBlock({ data, label, dark }: { data: Record<string, unknown> | unknown[]; label: string; dark?: boolean }) {
  const [open, setOpen] = useState(false);

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className="flex items-center gap-1 text-[10px] font-medium text-gray-400 hover:text-gray-600 transition-colors">
        <ChevronRight
          className={`size-3 transition-transform duration-150 ${open ? "rotate-90" : ""}`}
        />
        {label}
      </CollapsibleTrigger>
      <CollapsibleContent>
        <pre
          className={`mt-1.5 max-h-48 overflow-auto rounded-md p-2 font-mono text-[11px] leading-relaxed border ${
            dark
              ? "bg-gray-900 text-emerald-400 border-gray-800"
              : "bg-gray-50 text-gray-600 border-gray-100"
          }`}
        >
          {JSON.stringify(data, null, 2)}
        </pre>
      </CollapsibleContent>
    </Collapsible>
  );
}

// ── Highlighted summary — numbers pop out ──

function HighlightedSummary({ text }: { text: string }) {
  const parts = text.split(/(\d+\.?\d*%?)/g);
  return (
    <p className="font-mono text-xs text-gray-700 leading-relaxed">
      {parts.map((part, i) =>
        /\d/.test(part) ? (
          <span key={i} className="font-semibold text-gray-900">
            {part}
          </span>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </p>
  );
}

// ── Latency bar (waterfall-style) ──

function LatencyBar({ ms, totalMs }: { ms: number; totalMs: number }) {
  const pct = totalMs > 0 ? Math.min((ms / totalMs) * 100, 100) : 0;

  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 flex-1 rounded-full bg-gray-100 overflow-hidden">
        <div
          className="h-full rounded-full bg-gray-300 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="shrink-0 font-mono text-[10px] text-gray-400 tabular-nums">
        {ms.toFixed(0)}ms
      </span>
    </div>
  );
}

// ── ReAct Step — Think / Act / Observe ──

function ReActStep({
  step,
  isLast,
  totalLatency,
  index,
}: {
  step: OrchestratorStep;
  isLast: boolean;
  totalLatency: number;
  index: number;
}) {
  const style = getServerStyle(step.mcp_server, step.tool);

  return (
    <div
      className="relative pl-6 animate-step-reveal"
      style={{ animationDelay: `${index * 150}ms` }}
    >
      {/* Timeline vertical line */}
      {!isLast && (
        <div className="absolute left-[9px] top-6 bottom-0 w-px bg-gray-200" />
      )}

      {/* Timeline dot */}
      <div className={`absolute left-1 top-1.5 size-[10px] rounded-full ring-2 ring-white ${style.dot}`} />

      <div className="pb-4">
        {/* Step header */}
        <div className="flex items-center gap-2 mb-2">
          <span className="font-mono text-[10px] font-bold text-gray-400">
            STEP {step.step}
          </span>
          <span
            className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium ${style.bg} ${style.text}`}
          >
            <span className={`inline-block size-1.5 rounded-full ${style.dot}`} />
            {style.label}
          </span>
          {step.success === false && (
            <span className="rounded bg-red-50 px-1.5 py-0.5 text-[10px] font-medium text-red-500">
              FAILED
            </span>
          )}
        </div>

        {/* Phase 1: Think */}
        {step.reasoning && (
          <div className="mb-2 rounded-md border border-amber-100 bg-gradient-to-r from-amber-50/60 to-transparent px-2.5 py-2">
            <div className="mb-1 flex items-center gap-1.5">
              <div className="flex size-4 items-center justify-center rounded bg-amber-100">
                <span className="text-[9px] font-bold text-amber-700">T</span>
              </div>
              <span className="text-[10px] font-semibold uppercase tracking-wider text-amber-600">
                Think
              </span>
            </div>
            <div className="text-xs text-gray-600 leading-relaxed">
              <Markdown content={step.reasoning} />
            </div>
          </div>
        )}

        {/* Phase 2: Act */}
        <div className={`mb-2 rounded-md border px-2.5 py-2 ${style.border} border-gray-100`}>
          <div className="mb-1.5 flex items-center gap-1.5">
            <div className="flex size-4 items-center justify-center rounded bg-gray-100">
              <span className="text-[9px] font-bold text-gray-600">A</span>
            </div>
            <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-500">
              Act
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-semibold text-gray-900">
              {step.tool}
            </span>
          </div>
          {step.tool_input && Object.keys(step.tool_input).length > 0 && (
            <div className="mt-1.5">
              <JsonBlock data={step.tool_input} label="Parameters" />
            </div>
          )}
        </div>

        {/* Phase 3: Observe */}
        {step.tool_output_summary && (
          <div className="mb-2 rounded-md border border-sky-100 bg-gradient-to-r from-sky-50/60 to-transparent px-2.5 py-2">
            <div className="mb-1 flex items-center gap-1.5">
              <div className="flex size-4 items-center justify-center rounded bg-sky-100">
                <span className="text-[9px] font-bold text-sky-700">O</span>
              </div>
              <span className="text-[10px] font-semibold uppercase tracking-wider text-sky-600">
                Observe
              </span>
            </div>
            <HighlightedSummary text={step.tool_output_summary} />
            {step.tool_output != null && typeof step.tool_output === "object" ? (
              <div className="mt-1.5">
                <JsonBlock data={step.tool_output as Record<string, unknown>} label="Full Response" dark />
              </div>
            ) : null}
          </div>
        )}

        {/* Latency waterfall */}
        {step.latency_ms != null && (
          <LatencyBar ms={step.latency_ms} totalMs={totalLatency} />
        )}
      </div>
    </div>
  );
}

// ── Final Answer Step ──

function FinalAnswerStep({ step, index }: { step: OrchestratorStep; index: number }) {
  return (
    <div
      className="relative pl-6 animate-step-reveal"
      style={{ animationDelay: `${index * 150}ms` }}
    >
      {/* Timeline dot — gray for final */}
      <div className="absolute left-1 top-1.5 size-[10px] rounded-full bg-gray-400 ring-2 ring-white" />

      <div className="pb-2">
        <div className="flex items-center gap-2 mb-2">
          <span className="font-mono text-[10px] font-bold text-gray-400">
            STEP {step.step}
          </span>
          <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-500">
            Final Answer
          </span>
        </div>

        {/* Reasoning before final answer */}
        {step.reasoning && step.reasoning !== step.answer && (
          <div className="mb-2 rounded-md border border-amber-100 bg-gradient-to-r from-amber-50/60 to-transparent px-2.5 py-2">
            <div className="mb-1 flex items-center gap-1.5">
              <div className="flex size-4 items-center justify-center rounded bg-amber-100">
                <span className="text-[9px] font-bold text-amber-700">T</span>
              </div>
              <span className="text-[10px] font-semibold uppercase tracking-wider text-amber-600">
                Think
              </span>
            </div>
            <p className="text-xs text-gray-600 leading-relaxed line-clamp-4">
              {step.reasoning.length > 300
                ? step.reasoning.slice(0, 300) + "..."
                : step.reasoning}
            </p>
          </div>
        )}

        <div className="rounded-md border border-gray-200 bg-gray-50 px-2.5 py-2">
          <div className="mb-1 flex items-center gap-1.5">
            <div className="flex size-4 items-center justify-center rounded bg-gray-200">
              <span className="text-[9px] font-bold text-gray-600">S</span>
            </div>
            <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-500">
              Synthesize
            </span>
          </div>
          <p className="text-xs text-gray-500 italic">
            See full answer in result panel
          </p>
        </div>
      </div>
    </div>
  );
}

// ── Trace Summary — Enhanced with token grid + server waterfall ──

function TraceSummary({ result }: { result: OrchestratorResult }) {
  const toolSteps = result.steps.filter((s) => s.type === "tool_call");
  const serverCounts: Record<string, number> = {};
  const serverLatency: Record<string, number> = {};
  for (const s of toolSteps) {
    const key = s.mcp_server ?? inferServer(s.tool ?? "");
    serverCounts[key] = (serverCounts[key] ?? 0) + 1;
    serverLatency[key] = (serverLatency[key] ?? 0) + (s.latency_ms ?? 0);
  }
  const totalTime = toolSteps.reduce((sum, s) => sum + (s.latency_ms ?? 0), 0);
  const totalTokens = (result.total_input_tokens ?? 0) + (result.total_output_tokens ?? 0);

  return (
    <div
      className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2.5 animate-step-reveal"
      style={{ animationDelay: `${result.steps.length * 150 + 100}ms` }}
    >
      <p className="text-[10px] font-medium uppercase tracking-wider text-gray-400 mb-2">
        Execution Summary
      </p>

      {/* Token usage grid */}
      {totalTokens > 0 && (
        <div className="mb-3 grid grid-cols-3 gap-1.5 text-[10px]">
          <div className="rounded bg-white p-1.5 text-center border border-gray-100">
            <div className="text-gray-400">Input</div>
            <div className="font-mono font-medium text-gray-700">
              {(result.total_input_tokens ?? 0).toLocaleString()}
            </div>
          </div>
          <div className="rounded bg-white p-1.5 text-center border border-gray-100">
            <div className="text-gray-400">Output</div>
            <div className="font-mono font-medium text-gray-700">
              {(result.total_output_tokens ?? 0).toLocaleString()}
            </div>
          </div>
          <div className="rounded bg-white p-1.5 text-center border border-gray-100">
            <div className="text-gray-400">Cost</div>
            <div className="font-mono font-medium text-gray-700">
              ${result.total_cost_usd.toFixed(4)}
            </div>
          </div>
        </div>
      )}

      {/* Key metrics */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs mb-3">
        <div className="flex items-center gap-1">
          <span className="text-gray-400">Steps</span>
          <span className="font-mono font-medium text-gray-700">{result.total_steps}</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-gray-400">Tools</span>
          <span className="font-mono font-medium text-gray-700">{toolSteps.length}</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-gray-400">Time</span>
          <span className="font-mono font-medium text-gray-700">{totalTime.toFixed(0)}ms</span>
        </div>
      </div>

      {/* Server distribution with latency breakdown (stacked waterfall) */}
      {Object.keys(serverCounts).length > 0 && (
        <>
          {/* Stacked bar */}
          <div className="mb-2 flex h-2 w-full overflow-hidden rounded-full">
            {Object.entries(serverCounts).map(([server, count]) => {
              const total = Object.values(serverCounts).reduce((a, b) => a + b, 0);
              const style = SERVER_STYLES[server] ?? SERVER_STYLES.llm;
              return (
                <div
                  key={server}
                  className={`${style.dot} transition-all duration-500`}
                  style={{ width: `${(count / total) * 100}%` }}
                  title={`${style.label}: ${count} calls`}
                />
              );
            })}
          </div>

          {/* Per-server details */}
          <div className="flex flex-col gap-1.5">
            {Object.entries(serverCounts).map(([server, count]) => {
              const style = SERVER_STYLES[server] ?? SERVER_STYLES.llm;
              const latency = serverLatency[server] ?? 0;
              const pct = totalTime > 0 ? (latency / totalTime) * 100 : 0;

              return (
                <div key={server} className="flex items-center gap-2">
                  <span className={`inline-block size-2 rounded-full ${style.dot}`} />
                  <span className="w-14 text-[10px] font-medium text-gray-600">{style.label}</span>
                  <span className="text-[10px] text-gray-400">x{count}</span>
                  <div className="h-1.5 flex-1 rounded-full bg-gray-100 overflow-hidden">
                    <div
                      className={`h-full rounded-full ${style.dot} opacity-60`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="font-mono text-[10px] text-gray-400 tabular-nums">
                    {latency.toFixed(0)}ms
                  </span>
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* ReAct pattern legend */}
      <div className="mt-3 pt-2 border-t border-gray-200">
        <div className="flex items-center gap-3 text-[10px]">
          <div className="flex items-center gap-1">
            <span className="inline-block size-2 rounded-sm bg-amber-200" />
            <span className="text-gray-400">Think</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="inline-block size-2 rounded-sm bg-gray-200" />
            <span className="text-gray-400">Act</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="inline-block size-2 rounded-sm bg-sky-200" />
            <span className="text-gray-400">Observe</span>
          </div>
          <span className="text-gray-300">|</span>
          <span className="font-medium text-gray-400">ReAct Loop</span>
        </div>
      </div>
    </div>
  );
}

// ── Intelligence Trace ──

function IntelligenceTrace({ result }: { result: OrchestratorResult }) {
  const totalLatency = result.steps
    .filter((s) => s.type === "tool_call")
    .reduce((sum, s) => sum + (s.latency_ms ?? 0), 0);

  return (
    <div className="flex flex-col gap-2 p-3">
      {/* Header with trace ID + model badge */}
      <div className="mb-1 animate-step-reveal" style={{ animationDelay: "0ms" }}>
        <div className="flex items-center gap-2">
          <p className="text-[10px] font-medium uppercase tracking-wider text-gray-400">
            Decision Trace
          </p>
          <span className="rounded bg-orange-50 px-1.5 py-0.5 text-[10px] font-medium text-orange-500">
            ReAct
          </span>
          <span className="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-[9px] text-gray-400">
            Claude Sonnet
          </span>
        </div>
        <p className="mt-0.5 font-mono text-[10px] text-gray-400 truncate">
          {result.trace_id}
        </p>
      </div>

      <Separator />

      {/* Timeline steps */}
      <div className="flex flex-col">
        {result.steps.map((step, idx) => {
          if (step.type === "tool_call") {
            return (
              <ReActStep
                key={step.step}
                step={step}
                isLast={idx === result.steps.length - 1}
                totalLatency={totalLatency}
                index={idx}
              />
            );
          }
          if (step.type === "final_answer") {
            return <FinalAnswerStep key={step.step} step={step} index={idx} />;
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

function ExtractTrace({ result }: { result: ExtractResult }) {
  const trace = result.trace;

  return (
    <div className="flex flex-col gap-2 p-3">
      <div className="mb-1 animate-step-reveal" style={{ animationDelay: "0ms" }}>
        <div className="flex items-center gap-2">
          <p className="text-[10px] font-medium uppercase tracking-wider text-gray-400">
            Extract Pipeline
          </p>
          <span className="rounded bg-violet-50 px-1.5 py-0.5 text-[10px] font-medium text-violet-500">
            Few-Shot + Tool Use
          </span>
          {trace?.llm_response?.model && (
            <span className="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-[9px] text-gray-400">
              {trace.llm_response.model.split("-").slice(0, 2).join(" ")}
            </span>
          )}
        </div>
      </div>

      <Separator />

      {/* ── Step 1: Vector Search ── */}
      <div className="relative pl-6 animate-step-reveal" style={{ animationDelay: "0ms" }}>
        <div className="absolute left-[9px] top-6 bottom-0 w-px bg-gray-200" />
        <div className="absolute left-1 top-1.5 size-[10px] rounded-full ring-2 ring-white bg-violet-500" />
        <div className="pb-4">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="font-mono text-[10px] font-bold text-gray-400">1</span>
            <span className="text-xs font-semibold text-gray-900">Vector Search</span>
            <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium bg-violet-50 text-violet-600">
              <span className="inline-block size-1.5 rounded-full bg-violet-500" />
              ChromaDB
            </span>
          </div>
          <HighlightedSummary
            text={`${result.examples_used.length}건의 유사 제품 검색 (avg similarity: ${(result.avg_similarity * 100).toFixed(1)}%)`}
          />
          {/* 각 예시별 상세 */}
          {trace?.vector_search && trace.vector_search.length > 0 && (
            <div className="mt-2 flex flex-col gap-1.5">
              {trace.vector_search.map((ex) => (
                <div key={ex.gold_id} className="rounded-md border border-violet-100 bg-violet-50/30 px-2.5 py-2">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-mono text-[10px] font-semibold text-violet-600">{ex.gold_id}</span>
                    <span className="font-mono text-[10px] text-gray-400">
                      sim: {(ex.similarity * 100).toFixed(1)}%
                    </span>
                    <span className="font-mono text-[10px] text-gray-400">
                      score: {(ex.combined_score * 100).toFixed(1)}
                    </span>
                  </div>
                  <p className="text-[11px] text-gray-600 truncate">{ex.raw_input}</p>
                  <div className="mt-1">
                    <JsonBlock
                      data={ex.extracted_output as Record<string, unknown>}
                      label="Extracted Output"
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Step 2: LLM Extraction ── */}
      <div className="relative pl-6 animate-step-reveal" style={{ animationDelay: "150ms" }}>
        <div className="absolute left-[9px] top-6 bottom-0 w-px bg-gray-200" />
        <div className="absolute left-1 top-1.5 size-[10px] rounded-full ring-2 ring-white bg-orange-500" />
        <div className="pb-4">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="font-mono text-[10px] font-bold text-gray-400">2</span>
            <span className="text-xs font-semibold text-gray-900">LLM Extraction</span>
            <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium bg-orange-50 text-orange-600">
              <span className="inline-block size-1.5 rounded-full bg-orange-500" />
              Claude
            </span>
          </div>
          <HighlightedSummary
            text={`${Object.keys(result.attributes).length}개 속성 추출 ($${result.cost_usd.toFixed(4)})`}
          />
          {/* Token usage */}
          {trace?.llm_response && (
            <div className="mt-2 grid grid-cols-2 gap-1.5 text-[10px]">
              <div className="rounded bg-white p-1.5 text-center border border-gray-100">
                <div className="text-gray-400">Input</div>
                <div className="font-mono font-medium text-gray-700">
                  {trace.llm_response.input_tokens?.toLocaleString()}
                </div>
              </div>
              <div className="rounded bg-white p-1.5 text-center border border-gray-100">
                <div className="text-gray-400">Output</div>
                <div className="font-mono font-medium text-gray-700">
                  {trace.llm_response.output_tokens?.toLocaleString()}
                </div>
              </div>
            </div>
          )}
          {/* Few-shot prompt */}
          {trace?.few_shot_prompt && (
            <div className="mt-2">
              <JsonBlock
                data={{ few_shot_examples: trace.few_shot_prompt } as Record<string, unknown>}
                label="Few-Shot Prompt (injected)"
              />
            </div>
          )}
        </div>
      </div>

      {/* ── Step 3: Validation ── */}
      <div className="relative pl-6 animate-step-reveal" style={{ animationDelay: "300ms" }}>
        <div className="absolute left-[9px] top-6 bottom-0 w-px bg-gray-200" />
        <div className="absolute left-1 top-1.5 size-[10px] rounded-full ring-2 ring-white bg-gray-400" />
        <div className="pb-4">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="font-mono text-[10px] font-bold text-gray-400">3</span>
            <span className="text-xs font-semibold text-gray-900">Validation</span>
            <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium bg-gray-50 text-gray-600">
              <span className="inline-block size-1.5 rounded-full bg-gray-400" />
              Rules
            </span>
            <span className={`text-[10px] font-medium ${result.validation_passed ? "text-emerald-600" : "text-red-500"}`}>
              {result.validation_passed ? "PASS" : "FAIL"}
            </span>
          </div>
          <HighlightedSummary
            text={result.validation_passed
              ? `검증 통과 (경고 ${result.warnings.length}건)`
              : `검증 실패: ${result.errors.join(", ")}`}
          />
          {/* Errors & Warnings detail */}
          {(result.errors.length > 0 || result.warnings.length > 0) && (
            <div className="mt-2 flex flex-col gap-1">
              {result.errors.map((e, i) => (
                <p key={`e${i}`} className="text-[10px] text-red-500">error: {e}</p>
              ))}
              {result.warnings.map((w, i) => (
                <p key={`w${i}`} className="text-[10px] text-orange-500">warn: {w}</p>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Step 4: Graph Sync ── */}
      <div className="relative pl-6 animate-step-reveal" style={{ animationDelay: "450ms" }}>
        <div className="absolute left-1 top-1.5 size-[10px] rounded-full ring-2 ring-white bg-emerald-500" />
        <div className="pb-2">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="font-mono text-[10px] font-bold text-gray-400">4</span>
            <span className="text-xs font-semibold text-gray-900">Graph Sync</span>
            <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium bg-emerald-50 text-emerald-600">
              <span className="inline-block size-1.5 rounded-full bg-emerald-500" />
              Neo4j
            </span>
            <span className={`text-[10px] font-medium ${result.graph_synced ? "text-emerald-600" : "text-gray-400"}`}>
              {result.graph_synced ? "SYNCED" : "SKIP"}
            </span>
          </div>
          <HighlightedSummary
            text={result.graph_synced ? "Neo4j 동기화 완료" : "Neo4j 미동기화 (단건 추출 모드)"}
          />
        </div>
      </div>

      <Separator />

      {/* Summary */}
      <div
        className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2.5 animate-step-reveal"
        style={{ animationDelay: "700ms" }}
      >
        <p className="text-[10px] font-medium uppercase tracking-wider text-gray-400 mb-2">
          Pipeline Summary
        </p>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
          <div className="flex items-center gap-1">
            <span className="text-gray-400">Latency</span>
            <span className="font-mono font-medium text-gray-700">{result.latency_ms.toFixed(0)}ms</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-gray-400">Cost</span>
            <span className="font-mono font-medium text-gray-700">${result.cost_usd.toFixed(4)}</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-gray-400">Attrs</span>
            <span className="font-mono font-medium text-gray-700">{Object.keys(result.attributes).length}</span>
          </div>
          {trace?.llm_response && (
            <div className="flex items-center gap-1">
              <span className="text-gray-400">Tokens</span>
              <span className="font-mono font-medium text-gray-700">
                {((trace.llm_response.input_tokens ?? 0) + (trace.llm_response.output_tokens ?? 0)).toLocaleString()}
              </span>
            </div>
          )}
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
        <div className="h-2.5 w-20 animate-pulse rounded bg-gray-200" />
        <div className="mt-1.5 h-3 w-40 animate-pulse rounded bg-gray-100" />
      </div>
      <Separator />
      {[1, 2, 3].map((i) => (
        <div key={i} className="relative pl-6">
          <div className="absolute left-1 top-1.5 size-[10px] animate-pulse rounded-full bg-gray-200 ring-2 ring-white" />
          {i < 3 && <div className="absolute left-[9px] top-6 bottom-0 w-px bg-gray-100" />}
          <div className="pb-4">
            <div className="mb-2 flex items-center gap-2">
              <div className="h-2.5 w-12 animate-pulse rounded bg-gray-200" />
              <div className="h-3 w-16 animate-pulse rounded bg-gray-100" />
            </div>
            {/* Think skeleton */}
            <div className="mb-2 rounded-md border border-amber-50 bg-amber-50/30 p-2.5">
              <div className="h-2 w-8 animate-pulse rounded bg-amber-100 mb-1.5" />
              <div className="h-2 w-full animate-pulse rounded bg-amber-50" />
              <div className="mt-1 h-2 w-3/4 animate-pulse rounded bg-amber-50" />
            </div>
            {/* Act skeleton */}
            <div className="mb-2 rounded-md border border-gray-100 p-2.5">
              <div className="h-2 w-6 animate-pulse rounded bg-gray-100 mb-1.5" />
              <div className="h-2.5 w-32 animate-pulse rounded bg-gray-200" />
            </div>
            {/* Observe skeleton */}
            <div className="rounded-md border border-sky-50 bg-sky-50/30 p-2.5">
              <div className="h-2 w-12 animate-pulse rounded bg-sky-100 mb-1.5" />
              <div className="h-2 w-full animate-pulse rounded bg-sky-50" />
            </div>
          </div>
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
        <div className="mb-3 flex justify-center gap-2 text-[10px]">
          <div className="flex flex-col items-center gap-1">
            <div className="flex size-6 items-center justify-center rounded bg-amber-50">
              <span className="text-[9px] font-bold text-amber-700">T</span>
            </div>
            <span className="text-amber-600">Think</span>
          </div>
          <span className="self-center text-gray-300">→</span>
          <div className="flex flex-col items-center gap-1">
            <div className="flex size-6 items-center justify-center rounded bg-gray-100">
              <span className="text-[9px] font-bold text-gray-600">A</span>
            </div>
            <span className="text-gray-500">Act</span>
          </div>
          <span className="self-center text-gray-300">→</span>
          <div className="flex flex-col items-center gap-1">
            <div className="flex size-6 items-center justify-center rounded bg-sky-50">
              <span className="text-[9px] font-bold text-sky-700">O</span>
            </div>
            <span className="text-sky-600">Observe</span>
          </div>
        </div>
        <p className="text-xs text-gray-400">
          질문을 실행하면 LLM의
          <br />
          ReAct 사고 과정이 표시됩니다.
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
        <p className="text-xs font-semibold text-gray-900">Decision Trace</p>
        <p className="text-[10px] text-gray-400">LLM ReAct Reasoning Process</p>
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
