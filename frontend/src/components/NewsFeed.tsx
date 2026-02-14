"use client";
import { useState, useEffect } from "react";
import { useI18n } from "@/i18n/context";
import { getNews } from "@/lib/api";
import type { NewsItem } from "@/lib/types";
import { ExternalLink, Clock } from "lucide-react";

export default function NewsFeed() {
  const { t } = useI18n();
  const [news, setNews] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getNews()
      .then(setNews)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="text-center py-12 text-[#94a3b8]">{t("general.loading")}</div>;
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-white">{t("news.latest")}</h2>

      {news.length === 0 ? (
        <div className="text-center py-12 text-[#94a3b8]">{t("news.noArticles")}</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {news.map((item, i) => (
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
                <div className="flex items-center gap-3 mt-2 text-xs text-[#94a3b8]">
                  {item.source && <span>{item.source}</span>}
                  {item.related_ticker && (
                    <span className="bg-cyan-400/10 text-cyan-400 px-1.5 py-0.5 rounded">
                      {item.related_ticker}
                    </span>
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
