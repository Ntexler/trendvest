"use client";
import { useState } from "react";
import { useI18n } from "@/i18n/context";
import { getTopicInsight } from "@/lib/api";
import type { TrendTopic } from "@/lib/types";
import {
  ChevronDown,
  ChevronUp,
  Star,
  TrendingUp,
  TrendingDown,
  Minus,
  Lightbulb,
  Loader2,
  Link2,
  Sparkles,
} from "lucide-react";

interface Props {
  topic: TrendTopic;
  onStockClick: (ticker: string) => void;
  isWatched: (ticker: string) => boolean;
  toggleWatch: (ticker: string) => void;
}

interface InsightData {
  why_trending: string;
  stock_connections: Record<string, string>;
  ai_analysis?: string;
  related_topics?: { slug: string; name: string; connection: string }[];
  hidden_connections?: { ticker: string; company: string; connection: string }[];
}

export default function TopicCard({ topic, onStockClick, isWatched, toggleWatch }: Props) {
  const { locale, t } = useI18n();
  const [expanded, setExpanded] = useState(false);
  const [insight, setInsight] = useState<InsightData | null>(null);
  const [insightLoading, setInsightLoading] = useState(false);
  const [showInsight, setShowInsight] = useState(false);

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

  const handleInsightClick = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (insight) {
      setShowInsight(!showInsight);
      return;
    }
    setInsightLoading(true);
    setShowInsight(true);
    try {
      const data = await getTopicInsight(topic.slug, locale);
      setInsight(data);
    } catch (err) {
      console.error("Failed to load insight:", err);
    } finally {
      setInsightLoading(false);
    }
  };

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
        <div className="border-t border-[#1e293b]">
          {/* Why is this trending? button */}
          <div className="px-4 pt-3">
            <button
              onClick={handleInsightClick}
              className={`w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition ${
                showInsight
                  ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
                  : "bg-gradient-to-r from-cyan-500/10 to-purple-500/10 text-cyan-400 hover:from-cyan-500/20 hover:to-purple-500/20 border border-[#334155]"
              }`}
            >
              {insightLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Lightbulb className="w-4 h-4" />
              )}
              {t("insight.whyTrending")}
            </button>
          </div>

          {/* Insight Panel */}
          {showInsight && (
            <div className="px-4 py-3 space-y-3">
              {insightLoading ? (
                <div className="text-sm text-[#94a3b8] text-center py-4">
                  {t("insight.loading")}
                </div>
              ) : insight ? (
                <>
                  {/* AI Analysis (if available) */}
                  {insight.ai_analysis && (
                    <div className="bg-gradient-to-br from-purple-500/10 to-cyan-500/10 border border-purple-500/20 rounded-lg p-3">
                      <div className="flex items-center gap-1.5 text-xs text-purple-400 mb-2">
                        <Sparkles className="w-3 h-3" />
                        AI Analysis
                      </div>
                      <p className="text-sm text-[#e2e8f0] whitespace-pre-line leading-relaxed">
                        {insight.ai_analysis}
                      </p>
                    </div>
                  )}

                  {/* Why trending */}
                  {insight.why_trending && !insight.ai_analysis && (
                    <div className="bg-[#0f172a] rounded-lg p-3">
                      <p className="text-sm text-[#e2e8f0] leading-relaxed">
                        {insight.why_trending}
                      </p>
                    </div>
                  )}

                  {/* Stock connections */}
                  {Object.keys(insight.stock_connections).length > 0 && (
                    <div className="space-y-1.5">
                      {Object.entries(insight.stock_connections).map(([ticker, explanation]) => (
                        <div
                          key={ticker}
                          className="bg-[#0f172a] rounded-lg p-2.5 cursor-pointer hover:bg-[#1e293b] transition"
                          onClick={() => onStockClick(ticker)}
                        >
                          <div className="flex items-center gap-2 mb-1">
                            <Link2 className="w-3 h-3 text-cyan-400" />
                            <span className="font-mono text-xs font-bold text-cyan-400">{ticker}</span>
                          </div>
                          <p className="text-xs text-[#94a3b8] leading-relaxed">{explanation}</p>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Related Topics */}
                  {insight.related_topics && insight.related_topics.length > 0 && (
                    <div>
                      <h4 className="text-xs font-semibold text-[#94a3b8] uppercase mb-1.5">
                        {t("insight.relatedTopics")}
                      </h4>
                      <div className="flex flex-wrap gap-1.5">
                        {insight.related_topics.map((rt) => (
                          <span
                            key={rt.slug}
                            className="text-xs bg-purple-500/10 text-purple-300 px-2 py-1 rounded-full"
                            title={rt.connection}
                          >
                            {rt.name}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Hidden Connections */}
                  {insight.hidden_connections && insight.hidden_connections.length > 0 && (
                    <div>
                      <h4 className="text-xs font-semibold text-[#94a3b8] uppercase mb-1.5 flex items-center gap-1">
                        <Sparkles className="w-3 h-3 text-amber-400" />
                        {t("insight.hiddenConnections")}
                      </h4>
                      {insight.hidden_connections.map((hc) => (
                        <div
                          key={hc.ticker}
                          className="bg-amber-500/5 border border-amber-500/10 rounded-lg p-2.5 mb-1.5 cursor-pointer hover:bg-amber-500/10 transition"
                          onClick={() => onStockClick(hc.ticker)}
                        >
                          <span className="font-mono text-xs font-bold text-amber-400">{hc.ticker}</span>
                          <span className="text-xs text-[#94a3b8] ml-2">{hc.company}</span>
                          <p className="text-xs text-[#94a3b8] mt-1">{hc.connection}</p>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Disclaimer */}
                  <p className="text-[10px] text-[#64748b] text-center">
                    {t("insight.disclaimer")}
                  </p>
                </>
              ) : null}
            </div>
          )}

          {/* Stock list */}
          <div className="p-4 space-y-2 border-t border-[#1e293b]">
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
        </div>
      )}
    </div>
  );
}
