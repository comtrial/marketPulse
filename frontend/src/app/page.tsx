"use client";

import { useState, useCallback } from "react";
import { QueryPanel } from "@/components/query-panel";
import { ResultPanel } from "@/components/result-panel";
import { TracePanel } from "@/components/trace-panel";
import { BottomBar } from "@/components/bottom-bar";
import { HistoryPanel } from "@/components/history-panel";
import { api } from "@/lib/api";
import type { OrchestratorResult, ExtractResult } from "@/lib/api";

type Mode = "intelligence" | "extract";

export default function DashboardPage() {
  const [mode, setMode] = useState<Mode>("intelligence");
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<OrchestratorResult | null>(null);
  const [extractResult, setExtractResult] = useState<ExtractResult | null>(
    null
  );
  const [isLoading, setIsLoading] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);

  const handleSubmit = useCallback(
    async (q: string) => {
      setQuery(q);
      setIsCollapsed(true);
      setIsLoading(true);

      try {
        if (mode === "intelligence") {
          const res = await api.ask(q);
          setResult(res);
          setExtractResult(null);
        } else {
          const res = await api.extract(q);
          setExtractResult(res);
          setResult(null);
        }
      } catch (err) {
        console.error("API call failed:", err);
      } finally {
        setIsLoading(false);
      }
    },
    [mode]
  );

  const handleReset = useCallback(() => {
    setQuery("");
    setResult(null);
    setExtractResult(null);
    setIsCollapsed(false);
    setIsLoading(false);
  }, []);

  const handleModeChange = useCallback((newMode: Mode) => {
    setMode(newMode);
    setResult(null);
    setExtractResult(null);
    setQuery("");
    setIsCollapsed(false);
  }, []);

  const handleHistorySelect = useCallback(async (traceId: string) => {
    setIsLoading(true);
    setIsCollapsed(true);
    setMode("intelligence");

    try {
      const res = await api.getResult(traceId);
      setResult(res);
      setExtractResult(null);
      setQuery(res.user_query ?? `[이력] ${traceId.slice(0, 8)}...`);
    } catch (err) {
      console.error("Failed to load result:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  return (
    <div className="flex h-screen flex-col bg-white">
      {/* TopBar */}
      <header className="flex-none border-b border-gray-200 bg-white px-4 py-2.5">
        <div className="flex items-center gap-3">
          <h1 className="text-sm font-semibold text-gray-900 tracking-tight">
            MarketPulse
          </h1>
          <span className="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-[10px] text-gray-500">
            v0.1
          </span>
          <div className="ml-auto flex items-center gap-3">
            <HistoryPanel
              onSelect={handleHistorySelect}
              currentTraceId={result?.trace_id}
            />
            <div className="flex items-center gap-2 text-[10px] text-gray-400">
              <span className="flex items-center gap-1">
                <span className="inline-block size-1.5 rounded-full bg-blue-500" />
                order
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block size-1.5 rounded-full bg-emerald-500" />
                kg
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block size-1.5 rounded-full bg-violet-500" />
                vector
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block size-1.5 rounded-full bg-orange-500" />
                llm
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Column */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* Zone A — Query Panel */}
          <QueryPanel
            mode={mode}
            onModeChange={handleModeChange}
            onSubmit={handleSubmit}
            currentQuery={query}
            isCollapsed={isCollapsed}
            onToggleCollapse={() => setIsCollapsed((c) => !c)}
            onReset={handleReset}
          />

          {/* Zone B — Result Panel */}
          <div className="flex flex-1 flex-col overflow-hidden">
            <ResultPanel
              mode={mode}
              result={result}
              extractResult={extractResult}
              isLoading={isLoading}
            />
          </div>
        </div>

        {/* Zone C — Trace Panel */}
        <div className="w-[400px] flex-none overflow-hidden">
          <TracePanel
            mode={mode}
            result={result}
            extractResult={extractResult}
            isLoading={isLoading}
          />
        </div>
      </div>

      {/* BottomBar */}
      <BottomBar />
    </div>
  );
}
