"use client";
import { useState, useEffect } from "react";
import { useI18n } from "@/i18n/context";
import { getNews } from "@/lib/api";
import type { NewsItem } from "@/lib/types";
import { ExternalLink, Heart, Repeat2, TrendingUp, Twitter } from "lucide-react";

const SOURCE_BADGES: Record<string, { label: string; color: string }> = {
  news: { label: "News", color: "bg-blue-500/20 text-blue-400" },
  x: { label: "X", color: "bg-sky-500/20 text-sky-400" },
  google_trends: { label: "Trends", color: "bg-green-500/20 text-green-400" },
};

export default function NewsFeed() {
  const { t } = useI18n();
  const [news, setNews] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [sourceFilter, setSourceFilter] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getNews()
      .then(setNews)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const filtered = sourceFilter
    ? news.filter((item) => item.source_type === sourceFilter)
    : news;

  if (loading) {
    return <div className="text-center py-12 text-[#94a3b8]">{t("general.loading")}</div>;
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-white">{t("news.latest")}</h2>

      {/* Source filter chips */}
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={() => setSourceFilter(null)}
          className={`px-3 py-1 rounded-full text-xs font-medium transition ${
            sourceFilter === null
              ? "bg-cyan-500 text-white"
              : "bg-[#1e293b] text-[#94a3b8] hover:text-white"
          }`}
        >
          All
        </button>
        {Object.entries(SOURCE_BADGES).map(([key, { label, color }]) => (
          <button
            key={key}
            onClick={() => setSourceFilter(sourceFilter === key ? null : key)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition ${
              sourceFilter === key
                ? "bg-cyan-500 text-white"
                : `${color} hover:opacity-80`
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="text-center py-12 text-[#94a3b8]">{t("news.noArticles")}</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filtered.map((item, i) => (
            <a
              key={i}
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="group bg-[#111827] rounded-xl border border-[#334155] overflow-hidden hover:border-cyan-500/30 transition block"
            >
              {item.image_url && (
                <div className="h-40 overflow-hidden bg-[#1e293b]">
                  <img
                    src={item.image_url}
                    alt=""
                    className="w-full h-full object-cover group-hover:scale-105 transition"
                    onError={(e) => (e.currentTarget.style.display = "none")}
                  />
                </div>
              )}
              <div className="p-4">
                <h3 className="font-semibold text-white group-hover:text-cyan-400 transition line-clamp-2">
                  {item.title}
                </h3>
                <div className="flex items-center gap-2 mt-2 text-xs text-[#94a3b8] flex-wrap">
                  {/* Source type badge */}
                  {item.source_type && SOURCE_BADGES[item.source_type] && (
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                        SOURCE_BADGES[item.source_type].color
                      }`}
                    >
                      {SOURCE_BADGES[item.source_type].label}
                    </span>
                  )}
                  {item.source && <span>{item.source}</span>}
                  {item.related_ticker && (
                    <span className="bg-cyan-400/10 text-cyan-400 px-1.5 py-0.5 rounded">
                      {item.related_ticker}
                    </span>
                  )}
                  {/* X tweet engagement */}
                  {item.source_type === "x" && (
                    <>
                      {(item.likes ?? 0) > 0 && (
                        <span className="flex items-center gap-0.5">
                          <Heart className="w-3 h-3" />
                          {item.likes}
                        </span>
                      )}
                      {(item.retweets ?? 0) > 0 && (
                        <span className="flex items-center gap-0.5">
                          <Repeat2 className="w-3 h-3" />
                          {item.retweets}
                        </span>
                      )}
                    </>
                  )}
                  <ExternalLink className="w-3 h-3 ms-auto" />
                </div>
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
