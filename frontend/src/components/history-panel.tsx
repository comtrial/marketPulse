"use client";

import { useState, useEffect, useCallback } from "react";
import { api, type ResultSummary } from "@/lib/api";
import { Clock, ChevronDown, Loader2 } from "lucide-react";

interface HistoryPanelProps {
  onSelect: (traceId: string) => void;
  currentTraceId?: string;
}

export function HistoryPanel({ onSelect, currentTraceId }: HistoryPanelProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [results, setResults] = useState<ResultSummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const fetchHistory = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await api.getResults(20);
      setResults(data);
    } catch {
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Fetch on open
  useEffect(() => {
    if (isOpen) {
      fetchHistory();
    }
  }, [isOpen, fetchHistory]);

  const handleSelect = (traceId: string) => {
    onSelect(traceId);
    setIsOpen(false);
  };

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return "방금";
    if (diffMin < 60) return `${diffMin}분 전`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr}시간 전`;
    return `${Math.floor(diffHr / 24)}일 전`;
  };

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen((o) => !o)}
        className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700"
      >
        <Clock className="size-3" />
        <span>이력</span>
        <ChevronDown className={`size-3 transition-transform ${isOpen ? "rotate-180" : ""}`} />
      </button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />

          {/* Dropdown */}
          <div className="absolute right-0 top-full z-50 mt-1 w-80 rounded-lg border border-gray-200 bg-white shadow-lg">
            <div className="border-b border-gray-100 px-3 py-2">
              <p className="text-xs font-semibold text-gray-900">분석 이력</p>
              <p className="text-[10px] text-gray-400">이전 결과를 다시 조회합니다</p>
            </div>

            <div className="max-h-64 overflow-y-auto">
              {isLoading ? (
                <div className="flex items-center justify-center py-6">
                  <Loader2 className="size-4 animate-spin text-gray-400" />
                </div>
              ) : results.length === 0 ? (
                <div className="py-6 text-center text-xs text-gray-400">
                  아직 분석 이력이 없습니다
                </div>
              ) : (
                results.map((r) => (
                  <button
                    key={r.trace_id}
                    onClick={() => handleSelect(r.trace_id)}
                    className={`flex w-full flex-col gap-0.5 border-b border-gray-50 px-3 py-2.5 text-left transition-colors hover:bg-gray-50 ${
                      r.trace_id === currentTraceId ? "bg-blue-50" : ""
                    }`}
                  >
                    <span className="text-xs text-gray-800 line-clamp-1">
                      {r.user_query}
                    </span>
                    <div className="flex items-center gap-2 text-[10px] text-gray-400">
                      <span>{formatTime(r.created_at)}</span>
                      <span>steps: {r.total_steps}</span>
                      <span>${r.total_cost_usd.toFixed(4)}</span>
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
