"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  BarChart,
  Bar,
  ResponsiveContainer,
  Cell,
} from "recharts";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import type { OrchestratorStep } from "@/lib/api";

// ── Color palette ──

const COUNTRY_COLORS: Record<string, string> = {
  JP: "#3b82f6",
  SG: "#10b981",
  KR: "#f59e0b",
};

const SERVER_COLORS: Record<string, string> = {
  order: "#3b82f6",
  kg: "#10b981",
  vector: "#8b5cf6",
  llm: "#f97316",
};

// ── Type guards ──

interface TrendMonth {
  month: string;
  total: number;
  withAttr: number;
  percentage: number;
}

interface TrendOutput {
  attribute: string;
  type: string;
  trend: Record<string, TrendMonth[]>;
}

interface HeatmapOutput {
  productType: string;
  period: string;
  matrix: Record<string, Record<string, number>>;
  countries: string[];
}

interface CausalChain {
  climate: string;
  skinConcern: string;
  triggerStrength: number;
  season: string;
  mechanism: string;
  function: string;
  demandStrength: number;
  chainStrength: number;
}

interface TrendingIngredient {
  ingredient: string;
  inci: string;
  productCount: number;
  exampleProducts: string[];
}

interface Synergy {
  partner: string;
  mechanism: string;
  source: "explicit_synergy" | "co_occurrence";
}

// ── determineVisualizations ──

interface Visualization {
  type: string;
  data: unknown;
  tool: string;
  mcp_server: string;
}

export function determineVisualizations(
  steps: OrchestratorStep[]
): Visualization[] {
  const visuals: Visualization[] = [];

  for (const step of steps) {
    if (step.type !== "tool_call" || !step.tool_output) continue;

    const tool = step.tool ?? "unknown";
    const server = step.mcp_server ?? "unknown";

    switch (tool) {
      case "get_attribute_trend":
        visuals.push({ type: "trend_chart", data: step.tool_output, tool, mcp_server: server });
        break;
      case "get_country_attribute_heatmap":
        visuals.push({ type: "heatmap", data: step.tool_output, tool, mcp_server: server });
        break;
      case "query_causal_chain":
        visuals.push({ type: "causal_chain", data: step.tool_output, tool, mcp_server: server });
        break;
      case "find_trending_ingredients":
        visuals.push({ type: "ingredient_bar", data: step.tool_output, tool, mcp_server: server });
        break;
      case "find_ingredient_synergies":
        visuals.push({ type: "synergy_list", data: step.tool_output, tool, mcp_server: server });
        break;
    }
  }

  return visuals;
}

// ── TrendChartView ──

function TrendChartView({ data }: { data: unknown }) {
  const output = data as TrendOutput;
  if (!output?.trend) return null;

  const countries = Object.keys(output.trend);
  if (countries.length === 0) return null;

  // Recharts needs flat array: [{month, JP, SG, ...}]
  const firstCountry = countries[0];
  const chartData = (output.trend[firstCountry] ?? []).map((m) => {
    const point: Record<string, string | number> = { month: m.month.slice(5) }; // "2025-10" → "10"
    for (const country of countries) {
      const entry = output.trend[country]?.find((e) => e.month === m.month);
      point[country] = entry ? Math.round(entry.percentage * 10) / 10 : 0;
    }
    return point;
  });

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <CardTitle className="text-sm">속성 트렌드</CardTitle>
          <span className="rounded bg-blue-50 px-1.5 py-0.5 text-[10px] font-medium text-blue-600">
            order
          </span>
        </div>
        <CardDescription>
          「{output.attribute}」 ({output.type}) — 월별 비율 변화
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: -8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis
              dataKey="month"
              tick={{ fontSize: 11, fill: "#9ca3af" }}
              axisLine={{ stroke: "#e5e7eb" }}
            />
            <YAxis
              tick={{ fontSize: 11, fill: "#9ca3af" }}
              axisLine={{ stroke: "#e5e7eb" }}
              tickFormatter={(v: number) => `${v}%`}
            />
            <Tooltip
              contentStyle={{
                fontSize: 12,
                borderRadius: 8,
                border: "1px solid #e5e7eb",
                boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
              }}
              formatter={(value) => [`${value}%`, ""]}
            />
            <Legend
              wrapperStyle={{ fontSize: 11 }}
              iconType="circle"
              iconSize={8}
            />
            {countries.map((country) => (
              <Line
                key={country}
                type="monotone"
                dataKey={country}
                name={country}
                stroke={COUNTRY_COLORS[country] ?? "#6b7280"}
                strokeWidth={2}
                dot={{ r: 3, fill: COUNTRY_COLORS[country] ?? "#6b7280" }}
                activeDot={{ r: 5 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

// ── HeatmapView ──

function HeatmapView({ data }: { data: unknown }) {
  const output = data as HeatmapOutput;
  if (!output?.matrix) return null;

  const countries = Object.keys(output.matrix);
  // Collect all attributes across countries
  const allAttrs = new Set<string>();
  for (const c of countries) {
    for (const attr of Object.keys(output.matrix[c])) {
      allAttrs.add(attr);
    }
  }
  const attrs = Array.from(allAttrs);

  function getCellColor(value: number): string {
    if (value >= 60) return "bg-blue-600 text-white";
    if (value >= 40) return "bg-blue-400 text-white";
    if (value >= 20) return "bg-blue-200 text-gray-800";
    if (value > 0) return "bg-blue-50 text-gray-600";
    return "bg-gray-50 text-gray-300";
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <CardTitle className="text-sm">국가별 속성 히트맵</CardTitle>
          <span className="rounded bg-blue-50 px-1.5 py-0.5 text-[10px] font-medium text-blue-600">
            order
          </span>
        </div>
        <CardDescription>
          {output.productType} — {output.period}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr>
                <th className="px-2 py-1.5 text-left font-medium text-gray-500">국가</th>
                {attrs.map((attr) => (
                  <th key={attr} className="px-2 py-1.5 text-center font-medium text-gray-500">
                    {attr}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {countries.map((country) => (
                <tr key={country} className="border-t border-gray-100">
                  <td className="px-2 py-1.5 font-medium text-gray-700">{country}</td>
                  {attrs.map((attr) => {
                    const val = output.matrix[country]?.[attr] ?? 0;
                    return (
                      <td key={attr} className="px-1 py-1">
                        <div
                          className={`rounded px-2 py-1 text-center font-mono text-[11px] ${getCellColor(val)}`}
                          title={`${country} / ${attr}: ${val.toFixed(1)}%`}
                        >
                          {val > 0 ? `${val.toFixed(0)}%` : "—"}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {/* Legend */}
        <div className="mt-3 flex items-center gap-2 text-[10px] text-gray-400">
          <span>낮음</span>
          <div className="flex gap-0.5">
            <div className="size-3 rounded-sm bg-blue-50" />
            <div className="size-3 rounded-sm bg-blue-200" />
            <div className="size-3 rounded-sm bg-blue-400" />
            <div className="size-3 rounded-sm bg-blue-600" />
          </div>
          <span>높음</span>
        </div>
      </CardContent>
    </Card>
  );
}

// ── CausalChainView ──

function CausalChainView({ data }: { data: unknown }) {
  const chains = data as CausalChain[];
  if (!Array.isArray(chains) || chains.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <CardTitle className="text-sm">인과 체인</CardTitle>
          <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-600">
            kg
          </span>
        </div>
        <CardDescription>기후 → 피부 고민 → 기능 수요</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-3">
          {chains.map((chain, idx) => (
            <div
              key={idx}
              className={`rounded-lg border p-3 ${idx === 0 ? "border-emerald-200 bg-emerald-50/30" : "border-gray-100"}`}
            >
              {/* Flow: climate → skinConcern → function */}
              <div className="flex items-center gap-1.5 flex-wrap">
                {/* Climate */}
                <div className="rounded-md bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700">
                  {chain.climate}
                </div>
                {/* Arrow + strength */}
                <div className="flex flex-col items-center">
                  <span className="font-mono text-[10px] text-gray-400">
                    {chain.triggerStrength.toFixed(2)}
                  </span>
                  <span className="text-gray-300">→</span>
                </div>
                {/* Skin concern */}
                <div className="rounded-md bg-red-50 px-2 py-1 text-xs font-medium text-red-700">
                  {chain.skinConcern}
                </div>
                {/* Arrow + strength */}
                <div className="flex flex-col items-center">
                  <span className="font-mono text-[10px] text-gray-400">
                    {chain.demandStrength.toFixed(2)}
                  </span>
                  <span className="text-gray-300">→</span>
                </div>
                {/* Function */}
                <div className="rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">
                  {chain.function}
                </div>
              </div>
              {/* Meta row */}
              <div className="mt-2 flex gap-3 text-[10px] text-gray-400">
                <span>계절: {chain.season}</span>
                <span>메커니즘: {chain.mechanism}</span>
                <span className="font-mono">
                  체인 강도: {chain.chainStrength.toFixed(2)}
                </span>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

// ── IngredientBarView ──

const BAR_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#6366f1"];

function IngredientBarView({ data }: { data: unknown }) {
  const ingredients = data as TrendingIngredient[];
  if (!Array.isArray(ingredients) || ingredients.length === 0) return null;

  const chartData = ingredients.map((ing) => ({
    name: ing.ingredient,
    count: ing.productCount,
    inci: ing.inci,
  }));

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <CardTitle className="text-sm">인기 성분</CardTitle>
          <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-600">
            kg
          </span>
        </div>
        <CardDescription>성분별 포함 상품 수</CardDescription>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={Math.max(160, ingredients.length * 36)}>
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 4, right: 8, bottom: 4, left: 60 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 11, fill: "#9ca3af" }} />
            <YAxis
              type="category"
              dataKey="name"
              tick={{ fontSize: 11, fill: "#374151" }}
              width={56}
            />
            <Tooltip
              contentStyle={{
                fontSize: 12,
                borderRadius: 8,
                border: "1px solid #e5e7eb",
              }}
              formatter={(value) => [`${value}건`]}
            />
            <Bar dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={24}>
              {chartData.map((_, idx) => (
                <Cell key={idx} fill={BAR_COLORS[idx % BAR_COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

// ── SynergyListView ──

function SynergyListView({ data }: { data: unknown }) {
  const synergies = data as Synergy[];
  if (!Array.isArray(synergies) || synergies.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <CardTitle className="text-sm">성분 시너지</CardTitle>
          <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-600">
            kg
          </span>
        </div>
        <CardDescription>{synergies.length}개 시너지 성분</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-2">
          {synergies.map((s, idx) => (
            <div
              key={idx}
              className="flex items-start gap-3 rounded-lg border border-gray-100 px-3 py-2"
            >
              <span className="shrink-0 text-sm font-medium text-gray-800">
                {s.partner}
              </span>
              <span className="flex-1 text-xs text-gray-500 leading-relaxed">
                {s.mechanism}
              </span>
              <span
                className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium ${
                  s.source === "explicit_synergy"
                    ? "bg-emerald-50 text-emerald-600"
                    : "bg-gray-100 text-gray-500"
                }`}
              >
                {s.source === "explicit_synergy" ? "도메인 지식" : "동시 출현"}
              </span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

// ── VisualizationRenderer ──

export function VisualizationRenderer({ visual }: { visual: Visualization }) {
  switch (visual.type) {
    case "trend_chart":
      return <TrendChartView data={visual.data} />;
    case "heatmap":
      return <HeatmapView data={visual.data} />;
    case "causal_chain":
      return <CausalChainView data={visual.data} />;
    case "ingredient_bar":
      return <IngredientBarView data={visual.data} />;
    case "synergy_list":
      return <SynergyListView data={visual.data} />;
    default:
      return null;
  }
}
