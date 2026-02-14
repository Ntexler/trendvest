"use client";
import { useState } from "react";
import { useI18n } from "@/i18n/context";
import type { TrendTopic } from "@/lib/types";
import { ChevronDown, ChevronUp, Star, TrendingUp, TrendingDown, Minus } from "lucide-react";

interface Props {
  topic: TrendTopic;
  onStockClick: (ticker: string) => void;
  isWatched: (ticker: string) => boolean;
  toggleWatch: (ticker: string) => void;
}

export default function TopicCard({ topic, onStockClick, isWatched, toggleWatch }: Props) {
  const { locale } = useI18n();
  const [expanded, setExpanded] = useState(false);

  const dirIcon =
    topic.direction === "rising" ? (
      <TrendingUp className="w-4 h-4 text-green-400" />
    ) : topic.direction === "falling" ? (
      <TrendingDown className="w-4 h-4 text-red-400" />
    ) : (
      <Minus className="w-4 h-4 text-yellow-400" />
    );

  const dirColor =
    topic.direction === "rising"
      ? "text-green-400"
      : topic.direction === "falling"
      ? "text-red-400"
      : "text-yellow-400";

  return (
    <div className="bg-[#111827] rounded-xl border border-[#334155] overflow-hidden hover:border-cyan-500/30 transition">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full p-4 text-start"
      >
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <h3 className="font-semibold text-white">
              {locale === "he" ? topic.name_he : topic.name_en}
            </h3>
            <p className="text-sm text-[#94a3b8] mt-0.5">
              {locale === "he" ? topic.sector : topic.sector_en}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {dirIcon}
            <span className={`text-sm font-medium ${dirColor}`}>
              {topic.momentum_score.toFixed(0)}
            </span>
            {expanded ? (
              <ChevronUp className="w-4 h-4 text-[#94a3b8]" />
            ) : (
              <ChevronDown className="w-4 h-4 text-[#94a3b8]" />
            )}
          </div>
        </div>

        {/* Momentum Bar */}
        <div className="mt-3 h-1.5 bg-[#1e293b] rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${
              topic.direction === "rising"
                ? "bg-green-400"
                : topic.direction === "falling"
                ? "bg-red-400"
                : "bg-yellow-400"
            }`}
            style={{ width: `${Math.min(100, topic.momentum_score)}%` }}
          />
        </div>
      </button>

      {expanded && (
        <div className="border-t border-[#1e293b] p-4 space-y-2">
          {topic.stocks.map((stock) => (
            <div
              key={stock.ticker}
              className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-[#1e293b] transition cursor-pointer"
              onClick={() => onStockClick(stock.ticker)}
            >
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-semibold text-cyan-400 text-sm">
                    {stock.ticker}
                  </span>
                  <span className="text-sm text-white">{stock.company_name}</span>
                </div>
                {stock.relevance_note && (
                  <p className="text-xs text-[#94a3b8] mt-0.5">{stock.relevance_note}</p>
                )}
              </div>
              <div className="flex items-center gap-2">
                {stock.daily_change_pct !== null && (
                  <span
                    className={`text-sm font-medium tabular-nums ${
                      stock.daily_change_pct >= 0 ? "text-green-400" : "text-red-400"
                    }`}
                  >
                    {stock.daily_change_pct >= 0 ? "+" : ""}
                    {stock.daily_change_pct.toFixed(2)}%
                  </span>
                )}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleWatch(stock.ticker);
                  }}
                  className="p-1"
                >
                  <Star
                    className={`w-4 h-4 ${
                      isWatched(stock.ticker)
                        ? "fill-yellow-400 text-yellow-400"
                        : "text-[#94a3b8] hover:text-yellow-400"
                    }`}
                  />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
