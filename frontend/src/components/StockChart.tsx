"use client";
import { useState, useEffect } from "react";
import { getStockHistory } from "@/lib/api";
import type { StockHistory } from "@/lib/types";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface Props {
  ticker: string;
}

const PERIODS = [
  { value: "1mo", label: "1M" },
  { value: "3mo", label: "3M" },
  { value: "6mo", label: "6M" },
  { value: "1y", label: "1Y" },
];

export default function StockChart({ ticker }: Props) {
  const [period, setPeriod] = useState("1mo");
  const [data, setData] = useState<StockHistory | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getStockHistory(ticker, period)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [ticker, period]);

  const chartData = data?.data || [];
  const isPositive =
    chartData.length >= 2
      ? chartData[chartData.length - 1].close >= chartData[0].close
      : true;
  const color = isPositive ? "#22c55e" : "#ef4444";

  return (
    <div>
      <div className="flex gap-2 mb-3">
        {PERIODS.map((p) => (
          <button
            key={p.value}
            onClick={() => setPeriod(p.value)}
            className={`px-3 py-1 rounded-lg text-sm font-medium transition ${
              period === p.value
                ? "bg-cyan-500 text-white"
                : "bg-[#1e293b] text-[#94a3b8] hover:bg-[#334155]"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="h-48 flex items-center justify-center text-[#94a3b8]">Loading...</div>
      ) : chartData.length === 0 ? (
        <div className="h-48 flex items-center justify-center text-[#94a3b8]">No data</div>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id={`grad-${ticker}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.3} />
                <stop offset="95%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="date"
              tick={{ fill: "#94a3b8", fontSize: 10 }}
              tickFormatter={(v) => v.slice(5)}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              domain={["auto", "auto"]}
              tick={{ fill: "#94a3b8", fontSize: 10 }}
              axisLine={false}
              tickLine={false}
              width={60}
              tickFormatter={(v) => `$${v}`}
            />
            <Tooltip
              contentStyle={{
                background: "#1e293b",
                border: "1px solid #334155",
                borderRadius: "8px",
                color: "#e2e8f0",
              }}
              formatter={(value: number) => [`$${value.toFixed(2)}`, "Price"]}
            />
            <Area
              type="monotone"
              dataKey="close"
              stroke={color}
              strokeWidth={2}
              fill={`url(#grad-${ticker})`}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
