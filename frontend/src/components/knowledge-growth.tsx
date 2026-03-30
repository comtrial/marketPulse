"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Markdown } from "@/components/ui/markdown";
import { api } from "@/lib/api";
import type { EvalFullResult } from "@/lib/api";
import { ChevronDown } from "lucide-react";

// ── Axis Badge ──

function AxisBadge({
  icon,
  label,
  value,
  sub,
}: {
  icon: string;
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-sm">{icon}</span>
      <div>
        <p className="text-[10px] text-gray-400">{label}</p>
        <p className="text-xs font-medium text-gray-700 font-mono">{value}</p>
      </div>
      {sub && <span className="text-[10px] text-gray-400">{sub}</span>}
    </div>
  );
}

// ── Answer Quality Chart ──

function AnswerQualityChart({ data }: { data: EvalFullResult }) {
  const sessions = data.answer_quality.session_history;
  if (sessions.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">답변 품질 추이</CardTitle>
          <CardDescription>discovered_usage_rate 세션별 변화</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-gray-400 text-center py-6">
            아직 분석 이력이 없습니다
          </p>
        </CardContent>
      </Card>
    );
  }

  const chartData = sessions.map((s, i) => ({
    session: `S${i + 1}`,
    rate: s.used_discovered ? 1 : 0,
    traceId: s.trace_id.slice(0, 8),
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">답변 품질 추이</CardTitle>
        <CardDescription>
          {data.answer_quality.total_analyses}건 분석 중{" "}
          {data.answer_quality.used_discovered_link}건이 발견된 관계 활용
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={160}>
          <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: -8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="session" tick={{ fontSize: 10, fill: "#9ca3af" }} />
            <YAxis
              domain={[0, 1]}
              tick={{ fontSize: 10, fill: "#9ca3af" }}
              tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
            />
            <Tooltip
              contentStyle={{ fontSize: 11, borderRadius: 8, border: "1px solid #e5e7eb" }}
              formatter={(value) => [`${(Number(value) * 100).toFixed(0)}%`, "활용률"]}
            />
            <Line
              type="monotone"
              dataKey="rate"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={{ r: 3, fill: "#3b82f6" }}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

// ── Coverage Matrix ──

const COUNTRIES = ["KR", "JP", "SG"];
const PRODUCT_TYPES = [
  { key: "sunscreen", label: "Sunscreen" },
  { key: "toner", label: "Toner" },
  { key: "serum", label: "Serum" },
  { key: "cream", label: "Cream" },
  { key: "lip", label: "Lip" },
];

function CoverageMatrix({ data }: { data: EvalFullResult }) {
  const matrix = data.reasoning_coverage.matrix;

  function getCellStatus(key: string): "full" | "partial" | "none" {
    const cell = matrix[key];
    if (!cell) return "none";
    if (cell.full) return "full";
    if (cell.causal || cell.data) return "partial";
    return "none";
  }

  const statusStyle = {
    full: "bg-emerald-100 text-emerald-700",
    partial: "bg-amber-50 text-amber-600",
    none: "bg-gray-50 text-gray-300",
  };

  const statusLabel = {
    full: "●●",
    partial: "●○",
    none: "○○",
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">추론 커버리지</CardTitle>
        <CardDescription>
          {data.reasoning_coverage.full_coverage_cells}/{data.reasoning_coverage.total_cells} 조합 완전 커버 (
          {(data.reasoning_coverage.full_coverage_rate * 100).toFixed(0)}%)
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr>
                <th className="px-2 py-1.5 text-left font-medium text-gray-500 w-12" />
                {PRODUCT_TYPES.map((pt) => (
                  <th key={pt.key} className="px-2 py-1.5 text-center font-medium text-gray-500">
                    {pt.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {COUNTRIES.map((country) => (
                <tr key={country} className="border-t border-gray-100">
                  <td className="px-2 py-1.5 font-medium text-gray-700">{country}</td>
                  {PRODUCT_TYPES.map((pt) => {
                    const key = `${country}_${pt.key}`;
                    const status = getCellStatus(key);
                    return (
                      <td key={pt.key} className="px-1 py-1 text-center">
                        <span
                          className={`inline-block rounded px-2 py-0.5 font-mono text-[11px] ${statusStyle[status]}`}
                          title={`${country}/${pt.label}: ${status}`}
                        >
                          {statusLabel[status]}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-2 flex gap-3 text-[10px] text-gray-400">
          <span><span className="text-emerald-600">●●</span> causal + data</span>
          <span><span className="text-amber-500">●○</span> partial</span>
          <span><span className="text-gray-300">○○</span> none</span>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Proposal Table ──

function ProposalTable() {
  const { data: proposals } = useQuery({
    queryKey: ["knowledge-proposals"],
    queryFn: () => api.knowledgeProposals(),
    refetchInterval: 30_000,
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">제안된 관계</CardTitle>
        <CardDescription>PatternScout가 발견한 관계 후보</CardDescription>
      </CardHeader>
      <CardContent>
        {!proposals || proposals.length === 0 ? (
          <div className="text-center py-6">
            <p className="text-xs text-gray-400">
              아직 제안된 관계가 없습니다
            </p>
            <p className="mt-1 text-[10px] text-gray-300">
              Phase 2에서 PatternScout가 활성화되면 여기에 표시됩니다
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="px-2 py-1.5 text-left text-gray-500">타입</th>
                  <th className="px-2 py-1.5 text-left text-gray-500">소스 → 타겟</th>
                  <th className="px-2 py-1.5 text-center text-gray-500">신뢰도</th>
                  <th className="px-2 py-1.5 text-center text-gray-500">상태</th>
                </tr>
              </thead>
              <tbody>
                {proposals.map((p) => (
                  <tr key={p.id} className="border-t border-gray-50">
                    <td className="px-2 py-1.5 font-mono text-gray-600">{p.relationship_type}</td>
                    <td className="px-2 py-1.5 text-gray-700">{p.source} → {p.target}</td>
                    <td className="px-2 py-1.5 text-center font-mono">{(p.confidence * 100).toFixed(0)}%</td>
                    <td className="px-2 py-1.5 text-center">
                      <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
                        p.status === "approved" ? "bg-emerald-50 text-emerald-600" :
                        p.status === "rejected" ? "bg-red-50 text-red-500" :
                        "bg-amber-50 text-amber-600"
                      }`}>
                        {p.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── Before/After Comparison ──

function BeforeAfterComparison({ data }: { data: EvalFullResult }) {
  const pairs = data.before_after_pairs;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Before / After 답변 비교</CardTitle>
        <CardDescription>동일 질문의 관계 승인 전후 답변 차이</CardDescription>
      </CardHeader>
      <CardContent>
        {!pairs || pairs.length === 0 ? (
          <div className="text-center py-6">
            <p className="text-xs text-gray-400">
              아직 비교할 데이터가 없습니다
            </p>
            <p className="mt-1 text-[10px] text-gray-300">
              동일 질문의 승인 전/후 답변이 축적되면 여기에 비교가 표시됩니다
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {pairs.map((pair, idx) => (
              <div key={idx}>
                <p className="mb-2 text-xs font-medium text-gray-800">{pair.query}</p>
                <div className="grid grid-cols-2 gap-2">
                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                    <p className="mb-1 text-[10px] font-semibold text-gray-400">BEFORE</p>
                    <div className="text-xs text-gray-600 leading-relaxed">
                      <Markdown content={pair.before_answer.slice(0, 300)} />
                    </div>
                  </div>
                  <div className="rounded-lg border border-blue-200 bg-blue-50 p-3">
                    <p className="mb-1 text-[10px] font-semibold text-blue-500">AFTER</p>
                    <div className="text-xs text-gray-700 leading-relaxed">
                      <Markdown content={pair.after_answer.slice(0, 300)} />
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── System Efficiency ──

function SystemEfficiency({ data }: { data: EvalFullResult }) {
  const eff = data.system_efficiency;

  if (eff.status === "insufficient_data" || eff.total_sessions < 2) {
    return null;
  }

  const reduction = eff.cost_reduction;
  const isImproved = reduction > 0;

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-gray-400">비용 변화</span>
      <span className={`font-mono font-medium ${isImproved ? "text-emerald-600" : "text-red-500"}`}>
        {isImproved ? "-" : "+"}{(Math.abs(reduction) * 100).toFixed(1)}%
      </span>
      <span className="text-[10px] text-gray-300">
        (${eff.avg_cost_first_half.toFixed(3)} → ${eff.avg_cost_second_half.toFixed(3)})
      </span>
    </div>
  );
}

// ── Main Knowledge Growth Bar + Detail ──

export function KnowledgeGrowthBar() {
  const [isExpanded, setIsExpanded] = useState(false);

  const { data } = useQuery<EvalFullResult>({
    queryKey: ["eval-full"],
    queryFn: () => api.evalFull(),
    refetchInterval: 30_000,
  });

  if (!data) return null;

  const pd = data.pattern_discovery;
  const aq = data.answer_quality;
  const rc = data.reasoning_coverage;
  const se = data.system_efficiency;

  return (
    <div className="flex-none border-t border-gray-200 bg-white">
      {/* Summary Bar */}
      <button
        onClick={() => setIsExpanded((e) => !e)}
        className="flex w-full items-center gap-4 px-4 py-2 hover:bg-gray-50 transition-colors"
      >
        <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">
          Knowledge Growth
        </span>
        <Separator orientation="vertical" className="h-4" />

        <AxisBadge
          icon="🔍"
          label="패턴 탐지"
          value={`${pd.approved}/${pd.total_proposed}건`}
        />
        <Separator orientation="vertical" className="h-4" />

        <AxisBadge
          icon="📈"
          label="답변 품질"
          value={aq.total_analyses > 0 ? `${(aq.discovered_usage_rate * 100).toFixed(0)}% 활용` : "데이터 부족"}
        />
        <Separator orientation="vertical" className="h-4" />

        <AxisBadge
          icon="🧠"
          label="추론 커버"
          value={`${(rc.full_coverage_rate * 100).toFixed(0)}%`}
          sub={`(${rc.full_coverage_cells}/${rc.total_cells})`}
        />
        <Separator orientation="vertical" className="h-4" />

        <AxisBadge
          icon="⚡"
          label="효율"
          value={se.status === "insufficient_data" ? "데이터 부족" : `${(se.cost_reduction * 100).toFixed(1)}%`}
        />

        <div className="ml-auto">
          <ChevronDown className={`size-3.5 text-gray-400 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
        </div>
      </button>

      {/* Detail Panel */}
      {isExpanded && (
        <div className="border-t border-gray-100 bg-gray-50/50 px-4 py-4">
          <div className="grid grid-cols-2 gap-4 max-h-[400px] overflow-y-auto">
            <AnswerQualityChart data={data} />
            <CoverageMatrix data={data} />
            <ProposalTable />
            <BeforeAfterComparison data={data} />
          </div>
          {se.status !== "insufficient_data" && (
            <div className="mt-3 flex justify-end">
              <SystemEfficiency data={data} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
