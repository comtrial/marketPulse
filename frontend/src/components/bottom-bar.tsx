"use client";

import { useQuery } from "@tanstack/react-query";
import { api, type ExtractStats } from "@/lib/api";
import { Separator } from "@/components/ui/separator";

function StatItem({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-center gap-1.5 text-xs text-gray-500">
      <span className="text-gray-400">{label}</span>
      <span className="font-medium text-gray-700 font-mono">{value}</span>
    </div>
  );
}

export function BottomBar() {
  const { data: stats } = useQuery<ExtractStats>({
    queryKey: ["extract-stats"],
    queryFn: () => api.stats(),
    refetchInterval: 30_000,
  });

  return (
    <footer className="flex-none border-t border-gray-200 bg-white px-4 py-2">
      <div className="flex items-center gap-4">
        <StatItem
          label="Extractions"
          value={stats?.total_extractions ?? "---"}
        />
        <Separator orientation="vertical" className="h-3" />
        <StatItem
          label="Cost"
          value={
            stats ? `$${stats.total_cost_usd.toFixed(4)}` : "---"
          }
        />
        <Separator orientation="vertical" className="h-3" />
        <StatItem
          label="Neo4j Synced"
          value={stats?.graph_synced_count ?? "---"}
        />
        <Separator orientation="vertical" className="h-3" />
        <StatItem
          label="Errors"
          value={stats?.error_count ?? "---"}
        />
        <Separator orientation="vertical" className="h-3" />
        <StatItem
          label="Avg Latency"
          value={
            stats ? `${stats.avg_latency_ms.toFixed(0)}ms` : "---"
          }
        />
        <div className="ml-auto text-[10px] text-gray-300 font-mono">
          MarketPulse v0.1
        </div>
      </div>
    </footer>
  );
}
