"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  INTELLIGENCE_PRESETS,
  EXTRACT_PRESETS,
  type PresetCategory,
} from "@/lib/presets";
import { ChevronDown, ChevronUp, X, Send, Search } from "lucide-react";

// ── Types ──

type Mode = "intelligence" | "extract";

interface QueryPanelProps {
  mode: Mode;
  onModeChange: (mode: Mode) => void;
  onSubmit: (query: string) => void;
  currentQuery: string;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  onReset: () => void;
}

// ── Tool badge color mapping ──

const TOOL_COLORS: Record<string, { bg: string; text: string }> = {
  order: { bg: "bg-blue-50", text: "text-blue-600" },
  kg: { bg: "bg-emerald-50", text: "text-emerald-600" },
  vector: { bg: "bg-violet-50", text: "text-violet-600" },
  llm: { bg: "bg-orange-50", text: "text-orange-600" },
};

function ToolBadge({ tool }: { tool: string }) {
  const colors = TOOL_COLORS[tool] ?? { bg: "bg-gray-50", text: "text-gray-600" };
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium ${colors.bg} ${colors.text}`}
    >
      {tool}
    </span>
  );
}

// ── Preset Card ──

function PresetCard({
  label,
  tools,
  onClick,
}: {
  label: string;
  tools: string[];
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex flex-col gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-left transition-colors hover:bg-gray-50 active:bg-gray-100"
    >
      <span className="text-sm font-medium text-gray-900">{label}</span>
      <div className="flex gap-1">
        {tools.map((t) => (
          <ToolBadge key={t} tool={t} />
        ))}
      </div>
    </button>
  );
}

// ── Category Tabs + Preset Grid ──

function IntelligencePanel({
  onSubmit,
}: {
  onSubmit: (query: string) => void;
}) {
  const [activeCategory, setActiveCategory] = useState(
    INTELLIGENCE_PRESETS[0].id
  );

  const currentCategory = INTELLIGENCE_PRESETS.find(
    (c) => c.id === activeCategory
  );

  return (
    <div className="flex flex-col gap-3">
      {/* Category tabs */}
      <div className="flex gap-1 overflow-x-auto">
        {INTELLIGENCE_PRESETS.map((cat) => (
          <button
            key={cat.id}
            onClick={() => setActiveCategory(cat.id)}
            className={`shrink-0 rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
              activeCategory === cat.id
                ? "bg-gray-900 text-white"
                : "text-gray-500 hover:bg-gray-100 hover:text-gray-700"
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Preset grid */}
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-3">
        {currentCategory?.presets.map((preset) => (
          <PresetCard
            key={preset.id}
            label={preset.label}
            tools={preset.tools}
            onClick={() => onSubmit(preset.query)}
          />
        ))}
      </div>
    </div>
  );
}

function ExtractPanel({
  onSubmit,
}: {
  onSubmit: (query: string) => void;
}) {
  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-gray-500">
        제품명을 선택하거나 직접 입력하세요
      </p>
      <div className="flex flex-col gap-1.5">
        {EXTRACT_PRESETS.map((name) => (
          <button
            key={name}
            onClick={() => onSubmit(name)}
            className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-left text-sm text-gray-800 transition-colors hover:bg-gray-50 active:bg-gray-100"
          >
            {name}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Main Component ──

export function QueryPanel({
  mode,
  onModeChange,
  onSubmit,
  currentQuery,
  isCollapsed,
  onToggleCollapse,
  onReset,
}: QueryPanelProps) {
  const [customInput, setCustomInput] = useState("");

  const handleCustomSubmit = () => {
    const trimmed = customInput.trim();
    if (!trimmed) return;
    onSubmit(trimmed);
    setCustomInput("");
  };

  // ── Collapsed state ──
  if (isCollapsed) {
    return (
      <div className="flex-none border-b border-gray-200 bg-white">
        <div className="flex h-12 items-center gap-2 px-4">
          <Search className="size-3.5 text-gray-400" />
          <span className="flex-1 truncate text-sm text-gray-600">
            {currentQuery}
          </span>
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={onToggleCollapse}
          >
            <ChevronDown className="size-3.5" />
          </Button>
          <Button variant="ghost" size="icon-xs" onClick={onReset}>
            <X className="size-3.5" />
          </Button>
        </div>
      </div>
    );
  }

  // ── Expanded state ──
  return (
    <div className="flex-none border-b border-gray-200 bg-white">
      <div className="p-4">
        {/* Mode selector */}
        <div className="mb-4 flex items-center gap-2">
          <div className="inline-flex rounded-lg bg-gray-100 p-0.5">
            <button
              onClick={() => onModeChange("intelligence")}
              className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                mode === "intelligence"
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              인텔리전스
            </button>
            <button
              onClick={() => onModeChange("extract")}
              className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                mode === "extract"
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              추출
            </button>
          </div>
          {currentQuery && (
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={onToggleCollapse}
              className="ml-auto"
            >
              <ChevronUp className="size-3.5" />
            </Button>
          )}
        </div>

        {/* Presets */}
        {mode === "intelligence" ? (
          <IntelligencePanel onSubmit={onSubmit} />
        ) : (
          <ExtractPanel onSubmit={onSubmit} />
        )}

        {/* Custom input */}
        <div className="mt-4 flex gap-2">
          <input
            type="text"
            value={customInput}
            onChange={(e) => setCustomInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleCustomSubmit()}
            placeholder={
              mode === "intelligence"
                ? "자유 질문을 입력하세요..."
                : "제품명을 입력하세요..."
            }
            className="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 outline-none transition-colors focus:border-gray-400"
          />
          <Button
            variant="outline"
            size="default"
            onClick={handleCustomSubmit}
          >
            <Send className="size-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
}
