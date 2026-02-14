"use client";
import { useState, useEffect } from "react";
import { useI18n } from "@/i18n/context";
import { getTrends, trackInteraction } from "@/lib/api";
import type { TrendTopic } from "@/lib/types";
import TopicCard from "./TopicCard";
import { TrendingUp, Zap } from "lucide-react";

interface Props {
  onStockClick: (ticker: string) => void;
  isWatched: (ticker: string) => boolean;
  toggleWatch: (ticker: string) => void;
}

const SECTORS = [
  { key: "", he: "הכל", en: "All" },
  { key: "Technology", he: "טכנולוגיה", en: "Technology" },
  { key: "Energy", he: "אנרגיה", en: "Energy" },
  { key: "Healthcare", he: "בריאות", en: "Healthcare" },
  { key: "Finance", he: "פיננסים", en: "Finance" },
  { key: "Automotive", he: "רכב", en: "Automotive" },
  { key: "Defense", he: "ביטחון", en: "Defense" },
  { key: "Aerospace", he: "חלל", en: "Aerospace" },
  { key: "Biotech", he: "ביוטק", en: "Biotech" },
];

export default function Dashboard({ onStockClick, isWatched, toggleWatch }: Props) {
  const { locale, t } = useI18n();
  const [topics, setTopics] = useState<TrendTopic[]>([]);
  const [sector, setSector] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getTrends(sector || undefined)
      .then(setTopics)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [sector]);

  const topMovers = [...topics]
    .filter((t) => t.direction === "rising")
    .slice(0, 3);

  return (
    <div className="space-y-6">
      {/* Top Movers */}
      {topMovers.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-[#94a3b8] uppercase tracking-wider mb-3 flex items-center gap-2">
            <Zap className="w-4 h-4 text-yellow-400" />
            {t("dashboard.topMovers")}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {topMovers.map((topic) => (
              <div
                key={topic.slug}
                className="bg-gradient-to-br from-green-500/10 to-cyan-500/10 border border-green-500/20 rounded-xl p-4"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-white">
                    {locale === "he" ? topic.name_he : topic.name_en}
                  </span>
                  <span className="text-green-400 text-xs font-medium bg-green-400/10 px-2 py-0.5 rounded-full">
                    Rising
                  </span>
                </div>
                <div className="text-sm text-[#94a3b8]">
                  {locale === "he" ? topic.sector : topic.sector_en}
                </div>
                {topic.stocks[0] && (
                  <div className="mt-2 text-xs text-cyan-400">
                    {topic.stocks[0].ticker}: {topic.stocks[0].company_name}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Sector Filter */}
      <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
        {SECTORS.map((s) => (
          <button
            key={s.key}
            onClick={() => setSector(s.key)}
            className={`whitespace-nowrap px-3 py-1.5 rounded-full text-sm font-medium transition ${
              sector === s.key
                ? "bg-cyan-500 text-white"
                : "bg-[#1e293b] text-[#94a3b8] hover:bg-[#334155]"
            }`}
          >
            {locale === "he" ? s.he : s.en}
          </button>
        ))}
      </div>

      {/* Topics Grid */}
      {loading ? (
        <div className="text-center py-12 text-[#94a3b8]">{t("general.loading")}</div>
      ) : topics.length === 0 ? (
        <div className="text-center py-12 text-[#94a3b8]">{t("dashboard.noTopics")}</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {topics.map((topic) => (
            <TopicCard
              key={topic.slug}
              topic={topic}
              onStockClick={(ticker) => {
                trackInteraction({ interaction_type: "stock_click", target_slug: topic.slug });
                onStockClick(ticker);
              }}
              isWatched={isWatched}
              toggleWatch={toggleWatch}
            />
          ))}
        </div>
      )}
    </div>
  );
}
