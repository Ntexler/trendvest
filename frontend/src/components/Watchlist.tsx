"use client";
import { useState, useEffect } from "react";
import { useI18n } from "@/i18n/context";
import { getNews } from "@/lib/api";
import type { StockDetail, NewsItem } from "@/lib/types";
import { Star, Trash2, Newspaper, TrendingUp, ExternalLink } from "lucide-react";

interface Props {
  watchlist: string[];
  removeTicker: (ticker: string) => void;
  onStockClick: (ticker: string) => void;
}

type Tab = "stocks" | "news";

export default function Watchlist({ watchlist, removeTicker, onStockClick }: Props) {
  const { t } = useI18n();
  const [stocks, setStocks] = useState<StockDetail[]>([]);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<Tab>("stocks");
  const [news, setNews] = useState<NewsItem[]>([]);
  const [newsLoading, setNewsLoading] = useState(false);

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
        // Deduplicate by URL
        const seen = new Set<string>();
        const unique = allNews.filter((n) => {
          if (seen.has(n.url)) return false;
          seen.add(n.url);
          return true;
        });
        // Sort by date (newest first)
        unique.sort(
          (a, b) =>
            new Date(b.published_at).getTime() - new Date(a.published_at).getTime()
        );
        setNews(unique.slice(0, 50));
      })
      .finally(() => setNewsLoading(false));
  }, [watchlist, tab]);

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
          {stocks.map((stock) => (
            <div
              key={stock.ticker}
              onClick={() => onStockClick(stock.ticker)}
              className="flex items-center gap-4 p-4 bg-[#111827] rounded-xl border border-[#334155] hover:border-cyan-500/30 transition cursor-pointer"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-cyan-400">{stock.ticker}</span>
                  <span className="text-sm text-white truncate">{stock.company_name}</span>
                </div>
              </div>
              <div className="text-end">
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
              </div>
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
          ))}
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
