"use client";
import { useState, useEffect, useMemo } from "react";
import { useI18n } from "@/i18n/context";
import { useMode } from "@/contexts/ModeContext";
import { getNews, getTrends } from "@/lib/api";
import type { StockDetail, NewsItem, TrendTopic } from "@/lib/types";
import { Star, Trash2, Newspaper, TrendingUp, TrendingDown, Minus, ExternalLink, ShoppingCart } from "lucide-react";
import HeatGauge from "./HeatGauge";
import Sparkline from "./Sparkline";

interface Props {
  watchlist: string[];
  removeTicker: (ticker: string) => void;
  onStockClick: (ticker: string) => void;
  onBuy?: (ticker: string) => void;
}

type Tab = "stocks" | "news";

function generateSparklineData(slug: string, score: number, direction: string): number[] {
  let seed = 0;
  for (let i = 0; i < slug.length; i++) seed = (seed * 31 + slug.charCodeAt(i)) & 0x7fffffff;
  const rand = () => {
    seed = (seed * 1103515245 + 12345) & 0x7fffffff;
    return (seed % 1000) / 1000;
  };
  const points: number[] = [];
  let val = score * 0.6;
  for (let i = 0; i < 12; i++) {
    const drift = direction === "rising" ? 0.5 : direction === "falling" ? -0.5 : 0;
    val += (rand() - 0.5 + drift) * 4;
    val = Math.max(5, Math.min(100, val));
    points.push(val);
  }
  return points;
}

export default function Watchlist({ watchlist, removeTicker, onStockClick, onBuy }: Props) {
  const { t, locale } = useI18n();
  const { isExpert } = useMode();
  const [stocks, setStocks] = useState<StockDetail[]>([]);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<Tab>("stocks");
  const [news, setNews] = useState<NewsItem[]>([]);
  const [newsLoading, setNewsLoading] = useState(false);
  const [trends, setTrends] = useState<TrendTopic[]>([]);

  useEffect(() => {
    getTrends().then(setTrends).catch(() => {});
  }, []);

  useEffect(() => {
    if (watchlist.length === 0) {
      setStocks([]);
      return;
    }
    setLoading(true);
    Promise.all(
      watchlist.map((ticker) =>
        fetch(`/api/stocks/${ticker}`)
          .then((r) => (r.ok ? r.json() : null))
          .catch(() => null)
      )
    )
      .then((results) => setStocks(results.filter(Boolean)))
      .finally(() => setLoading(false));
  }, [watchlist]);

  // Fetch news for all watched tickers
  useEffect(() => {
    if (watchlist.length === 0 || tab !== "news") {
      setNews([]);
      return;
    }
    setNewsLoading(true);
    Promise.all(
      watchlist.map((ticker) =>
        getNews({ ticker }).catch(() => [] as NewsItem[])
      )
    )
      .then((results) => {
        const allNews = results.flat();
        const seen = new Set<string>();
        const unique = allNews.filter((n) => {
          if (seen.has(n.url)) return false;
          seen.add(n.url);
          return true;
        });
        unique.sort(
          (a, b) =>
            new Date(b.published_at).getTime() - new Date(a.published_at).getTime()
        );
        setNews(unique.slice(0, 50));
      })
      .finally(() => setNewsLoading(false));
  }, [watchlist, tab]);

  // Map stock tickers to parent trends
  const stockTrendMap = useMemo(() => {
    const map: Record<string, TrendTopic> = {};
    for (const trend of trends) {
      for (const s of trend.stocks) {
        map[s.ticker] = trend;
      }
    }
    return map;
  }, [trends]);

  const totalChange =
    stocks.length > 0
      ? stocks.reduce((sum, s) => sum + (s.daily_change_pct || 0), 0) / stocks.length
      : 0;

  const formatTime = (dateStr: string) => {
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffH = Math.floor(diffMs / 3600000);
    if (diffH < 1) return t("watchlist.justNow");
    if (diffH < 24) return `${diffH}h`;
    const diffD = Math.floor(diffH / 24);
    return `${diffD}d`;
  };

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-white">{t("watchlist.title")}</h2>

      {/* Tabs */}
      {watchlist.length > 0 && (
        <div className="flex gap-1 bg-[#111827] rounded-xl p-1 border border-[#334155]">
          <button
            onClick={() => setTab("stocks")}
            className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium transition ${
              tab === "stocks"
                ? "bg-cyan-500/20 text-cyan-400"
                : "text-[#94a3b8] hover:text-white"
            }`}
          >
            <TrendingUp className="w-4 h-4" />
            {t("watchlist.stocksTab")}
          </button>
          <button
            onClick={() => setTab("news")}
            className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium transition ${
              tab === "news"
                ? "bg-cyan-500/20 text-cyan-400"
                : "text-[#94a3b8] hover:text-white"
            }`}
          >
            <Newspaper className="w-4 h-4" />
            {t("watchlist.newsTab")}
          </button>
        </div>
      )}

      {/* Summary */}
      {stocks.length > 0 && tab === "stocks" && (
        <div className="bg-[#111827] rounded-xl border border-[#334155] p-4 flex items-center justify-between">
          <div>
            <div className="text-sm text-[#94a3b8]">
              {stocks.length} {stocks.length === 1 ? "stock" : "stocks"}
            </div>
          </div>
          <div
            className={`text-lg font-bold tabular-nums ${
              totalChange >= 0 ? "text-green-400" : "text-red-400"
            }`}
          >
            {totalChange >= 0 ? "+" : ""}
            {totalChange.toFixed(2)}% avg
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-[#94a3b8]">{t("general.loading")}</div>
      ) : watchlist.length === 0 ? (
        <div className="text-center py-12">
          <Star className="w-12 h-12 text-[#334155] mx-auto mb-3" />
          <p className="text-[#94a3b8]">{t("watchlist.empty")}</p>
          <p className="text-sm text-[#64748b] mt-1">{t("watchlist.addTip")}</p>
        </div>
      ) : tab === "stocks" ? (
        <div className="space-y-2">
          {stocks.map((stock) => {
            const parentTrend = stockTrendMap[stock.ticker];
            const trendDirection = parentTrend?.direction;
            const dirColor =
              trendDirection === "rising"
                ? "bg-green-500/20 text-green-400"
                : trendDirection === "falling"
                ? "bg-red-500/20 text-red-400"
                : "bg-yellow-500/20 text-yellow-400";
            const sparkColor =
              trendDirection === "rising"
                ? "#4ade80"
                : trendDirection === "falling"
                ? "#f87171"
                : "#facc15";
            const sparkData = parentTrend
              ? generateSparklineData(parentTrend.slug, parentTrend.momentum_score, parentTrend.direction)
              : [];

            return (
              <div
                key={stock.ticker}
                onClick={() => onStockClick(stock.ticker)}
                className="p-4 bg-[#111827] rounded-xl border border-[#334155] hover:border-cyan-500/30 transition cursor-pointer"
              >
                <div className="flex items-center gap-3">
                  {/* Gauge */}
                  {parentTrend && (
                    <HeatGauge score={parentTrend.momentum_score} size="md" />
                  )}

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-cyan-400">{stock.ticker}</span>
                      <span className="text-sm text-white truncate">{stock.company_name}</span>
                    </div>
                    {/* Trend badge */}
                    {parentTrend && (
                      <div className="flex items-center gap-2 mt-1">
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${dirColor}`}>
                          {trendDirection === "rising" ? (
                            <TrendingUp className="w-3 h-3 inline-block me-0.5 -mt-0.5" />
                          ) : trendDirection === "falling" ? (
                            <TrendingDown className="w-3 h-3 inline-block me-0.5 -mt-0.5" />
                          ) : (
                            <Minus className="w-3 h-3 inline-block me-0.5 -mt-0.5" />
                          )}
                          {locale === "he" ? parentTrend.name_he : parentTrend.name_en}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Sparkline */}
                  {sparkData.length > 0 && (
                    <Sparkline data={sparkData} color={sparkColor} width={56} height={22} />
                  )}

                  <div className="text-end shrink-0">
                    {stock.current_price !== null && (
                      <div className="font-mono font-semibold text-white tabular-nums">
                        ${stock.current_price.toFixed(2)}
                      </div>
                    )}
                    {stock.daily_change_pct !== null && (
                      <div
                        className={`text-sm font-medium tabular-nums ${
                          stock.daily_change_pct >= 0 ? "text-green-400" : "text-red-400"
                        }`}
                      >
                        {stock.daily_change_pct >= 0 ? "+" : ""}
                        {stock.daily_change_pct.toFixed(2)}%
                      </div>
                    )}
                    {/* Expert mode: P/E */}
                    {isExpert && parentTrend && (
                      <div className="text-[10px] text-[#64748b] mt-0.5">
                        P/E: N/A
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-1">
                    {onBuy && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onBuy(stock.ticker);
                        }}
                        className="p-2 rounded-lg hover:bg-green-500/10 transition"
                        title={t("watchlist.buyAction" as any)}
                      >
                        <ShoppingCart className="w-4 h-4 text-green-400" />
                      </button>
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        removeTicker(stock.ticker);
                      }}
                      className="p-2 rounded-lg hover:bg-red-500/10"
                    >
                      <Trash2 className="w-4 h-4 text-red-400" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* News Tab */
        <div className="space-y-3">
          {newsLoading ? (
            <div className="text-center py-12 text-[#94a3b8]">{t("general.loading")}</div>
          ) : news.length === 0 ? (
            <div className="text-center py-12">
              <Newspaper className="w-12 h-12 text-[#334155] mx-auto mb-3" />
              <p className="text-[#94a3b8]">{t("watchlist.noNews")}</p>
            </div>
          ) : (
            news.map((item, i) => (
              <a
                key={`${item.url}-${i}`}
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block p-4 bg-[#111827] rounded-xl border border-[#334155] hover:border-cyan-500/30 transition"
              >
                <div className="flex gap-3">
                  {item.image_url && (
                    <img
                      src={item.image_url}
                      alt=""
                      className="w-16 h-16 rounded-lg object-cover flex-shrink-0"
                      onError={(e) => (e.currentTarget.style.display = "none")}
                    />
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-white font-medium line-clamp-2">
                      {item.title}
                    </p>
                    <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                      {item.related_ticker && (
                        <span className="px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-400 text-xs font-mono font-bold">
                          {item.related_ticker}
                        </span>
                      )}
                      <span className="text-xs text-[#64748b]">{item.source}</span>
                      <span className="text-xs text-[#64748b]">
                        {formatTime(item.published_at)}
                      </span>
                      <ExternalLink className="w-3 h-3 text-[#64748b] ml-auto" />
                    </div>
                  </div>
                </div>
              </a>
            ))
          )}
        </div>
      )}
    </div>
  );
}
