"use client";
import { useState, useEffect } from "react";
import { useI18n } from "@/i18n/context";
import { getFeed, translateArticle, getTrendingTopics, generateNewsletter, trackInteraction } from "@/lib/api";
import type {
  UnifiedFeed, FeedItem, NewsItem, PodcastEpisode, InstitutionalItem,
  BlogPost, TrendingTopic, TranslatedArticle, Newsletter,
} from "@/lib/types";
import Sparkline from "./Sparkline";
import HeatGauge from "./HeatGauge";
import {
  TrendingUp,
  TrendingDown,
  Minus,
  ExternalLink,
  Star,
  Newspaper,
  Podcast,
  Clock,
  BarChart3,
  Zap,
  ChevronDown,
  ChevronUp,
  Globe,
  Languages,
  Flame,
  ScrollText,
  Building2,
  BookOpen,
  Loader2,
  X,
  MapPin,
} from "lucide-react";

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

const MARKETS = [
  { key: "", he: "כל השווקים", en: "All Markets", icon: "🌍" },
  { key: "israel", he: "ישראל", en: "Israel", icon: "🇮🇱" },
  { key: "us", he: "ארה״ב", en: "US", icon: "🇺🇸" },
  { key: "europe", he: "אירופה", en: "Europe", icon: "🇪🇺" },
  { key: "asia", he: "אסיה", en: "Asia", icon: "🌏" },
];

function timeAgo(dateStr: string, locale: string): string {
  if (!dateStr) return "";
  try {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (locale === "he") {
      if (minutes < 1) return "עכשיו";
      if (minutes < 60) return `לפני ${minutes} דק׳`;
      if (hours < 24) return `לפני ${hours} שע׳`;
      if (days < 7) return `לפני ${days} ימים`;
      return date.toLocaleDateString("he-IL");
    }
    if (minutes < 1) return "now";
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    return date.toLocaleDateString("en-US");
  } catch {
    return "";
  }
}

function DirectionBadge({ direction, locale }: { direction: string; locale: string }) {
  const config = {
    rising: {
      icon: <TrendingUp className="w-3 h-3" />,
      label: locale === "he" ? "עולה" : "Rising",
      cls: "bg-green-500/15 text-green-400 border-green-500/30",
    },
    falling: {
      icon: <TrendingDown className="w-3 h-3" />,
      label: locale === "he" ? "יורד" : "Falling",
      cls: "bg-red-500/15 text-red-400 border-red-500/30",
    },
    stable: {
      icon: <Minus className="w-3 h-3" />,
      label: locale === "he" ? "יציב" : "Stable",
      cls: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
    },
  }[direction] || { icon: null, label: direction, cls: "bg-gray-500/15 text-gray-400" };

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${config.cls}`}>
      {config.icon}
      {config.label}
    </span>
  );
}

function TranslateButton({ article, locale }: { article: NewsItem; locale: string }) {
  const [translation, setTranslation] = useState<TranslatedArticle | null>(null);
  const [loading, setLoading] = useState(false);
  const [show, setShow] = useState(false);

  const targetLang = locale === "he" ? "he" : "en";
  // Don't show translate button if article is already in target language
  const articleLang = article.language || (article.source_type === "il_news" ? "he" : "en");
  if (articleLang === targetLang) return null;

  const handleTranslate = async () => {
    if (translation) {
      setShow(!show);
      return;
    }
    setLoading(true);
    try {
      const result = await translateArticle({
        title: article.title,
        description: article.description || "",
        source: article.source,
        url: article.url,
        target_language: targetLang,
      });
      setTranslation(result);
      setShow(true);
    } catch (e) {
      console.error("Translation error:", e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <button
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          handleTranslate();
        }}
        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-violet-500/15 text-violet-400 text-[10px] font-medium hover:bg-violet-500/25 transition"
      >
        {loading ? (
          <Loader2 className="w-2.5 h-2.5 animate-spin" />
        ) : (
          <Languages className="w-2.5 h-2.5" />
        )}
        {loading ? (locale === "he" ? "מתרגם..." : "...") : (locale === "he" ? "תרגם" : "Translate")}
      </button>
      {show && translation && (
        <div className="mt-2 p-2 rounded-lg bg-violet-500/10 border border-violet-500/20 text-xs">
          <div className="flex items-center justify-between mb-1">
            <span className="text-violet-400 font-medium flex items-center gap-1">
              <Languages className="w-3 h-3" />
              {translation.ai_generated ? "AI" : ""} {locale === "he" ? "תרגום" : "Translation"}
            </span>
            <button onClick={(e) => { e.preventDefault(); e.stopPropagation(); setShow(false); }}>
              <X className="w-3 h-3 text-[#64748b]" />
            </button>
          </div>
          <p className="text-white font-medium mb-1">{translation.translated_title}</p>
          <p className="text-[#94a3b8]">{translation.summary}</p>
          {translation.key_points.length > 0 && (
            <ul className="mt-1 space-y-0.5">
              {translation.key_points.map((kp, i) => (
                <li key={i} className="text-[#94a3b8] flex items-start gap-1">
                  <span className="text-violet-400 mt-0.5">•</span>
                  {kp}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function FeedCard({
  item,
  onStockClick,
  isWatched,
  toggleWatch,
  locale,
  isTopMover,
}: {
  item: FeedItem;
  onStockClick: (ticker: string) => void;
  isWatched: (ticker: string) => boolean;
  toggleWatch: (ticker: string) => void;
  locale: string;
  isTopMover: boolean;
}) {
  const [expanded, setExpanded] = useState(isTopMover);
  const { topic, momentum_history, stocks, top_article, articles, il_news } = item;

  const sparkData = momentum_history.map((p) => p.mentions);
  const sparkColor = topic.direction === "rising" ? "#4ade80" : topic.direction === "falling" ? "#f87171" : "#facc15";

  const allArticles = [...articles, ...il_news, ...(item.global_news || [])];

  return (
    <article
      className={`rounded-xl border overflow-hidden transition-all ${
        isTopMover
          ? "bg-gradient-to-br from-[#111827] to-[#0c1a2e] border-cyan-500/30 shadow-lg shadow-cyan-500/5"
          : "bg-[#111827] border-[#334155] hover:border-[#475569]"
      }`}
    >
      {/* Header — always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full p-4 text-start"
      >
        <div className="flex items-start gap-3">
          {/* Left: Topic info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className={`font-bold text-white ${isTopMover ? "text-lg" : "text-base"}`}>
                {locale === "he" ? topic.name_he : topic.name_en}
              </h3>
              <DirectionBadge direction={topic.direction} locale={locale} />
              {isTopMover && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30">
                  <Zap className="w-2.5 h-2.5" />
                  {locale === "he" ? "חם" : "HOT"}
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 mt-1 text-xs text-[#94a3b8]">
              <span>{locale === "he" ? topic.sector : topic.sector_en}</span>
              <span className="flex items-center gap-1">
                <BarChart3 className="w-3 h-3" />
                {topic.mention_count_today} {locale === "he" ? "אזכורים היום" : "mentions today"}
              </span>
              {topic.updated_at && (
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {timeAgo(topic.updated_at, locale)}
                </span>
              )}
            </div>
          </div>

          {/* Right: Sparkline + Score */}
          <div className="flex items-center gap-2 shrink-0">
            {sparkData.length >= 2 && (
              <Sparkline data={sparkData} color={sparkColor} width={72} height={28} />
            )}
            <HeatGauge score={topic.momentum_score} size="md" />
            {expanded ? (
              <ChevronUp className="w-4 h-4 text-[#64748b]" />
            ) : (
              <ChevronDown className="w-4 h-4 text-[#64748b]" />
            )}
          </div>
        </div>

        {/* Momentum bar */}
        <div className="mt-3 h-1 bg-[#1e293b] rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              topic.direction === "rising"
                ? "bg-gradient-to-r from-green-500 to-cyan-400"
                : topic.direction === "falling"
                ? "bg-gradient-to-r from-red-500 to-orange-400"
                : "bg-gradient-to-r from-yellow-500 to-amber-400"
            }`}
            style={{ width: `${Math.min(100, topic.momentum_score)}%` }}
          />
        </div>

        {/* Inline article preview (when collapsed) */}
        {!expanded && top_article && (
          <p className="mt-2 text-sm text-[#94a3b8] line-clamp-1">
            <Newspaper className="w-3 h-3 inline me-1 opacity-50" />
            {top_article.title}
          </p>
        )}

        {/* Inline stock chips (when collapsed) */}
        {!expanded && stocks.length > 0 && (
          <div className="flex gap-2 mt-2 overflow-x-auto">
            {stocks.slice(0, 4).map((s) => (
              <span
                key={s.ticker}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-[#1e293b] text-xs shrink-0"
              >
                <span className="font-mono font-semibold text-cyan-400">{s.ticker}</span>
                {s.daily_change_pct !== null && (
                  <span className={s.daily_change_pct >= 0 ? "text-green-400" : "text-red-400"}>
                    {s.daily_change_pct >= 0 ? "+" : ""}{s.daily_change_pct.toFixed(1)}%
                  </span>
                )}
              </span>
            ))}
          </div>
        )}
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-[#1e293b]">
          {/* Top article with image */}
          {top_article && (
            <a
              href={top_article.url}
              target="_blank"
              rel="noopener noreferrer"
              className="block group"
              onClick={() => trackInteraction({ interaction_type: "news_click", target_slug: topic.slug })}
            >
              {top_article.image_url && (
                <div className="h-44 overflow-hidden bg-[#0f172a]">
                  <img
                    src={top_article.image_url}
                    alt=""
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    onError={(e) => (e.currentTarget.style.display = "none")}
                  />
                </div>
              )}
              <div className="px-4 py-3">
                <h4 className="font-semibold text-white group-hover:text-cyan-400 transition line-clamp-2">
                  {top_article.title}
                </h4>
                <div className="flex items-center gap-2 mt-1 text-xs text-[#94a3b8]">
                  {top_article.source && <span>{top_article.source}</span>}
                  {top_article.source_type === "il_news" && (
                    <span className="px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 text-[10px] font-medium">IL</span>
                  )}
                  {top_article.published_at && <span>{timeAgo(top_article.published_at, locale)}</span>}
                  <ExternalLink className="w-3 h-3 ms-auto" />
                </div>
              </div>
            </a>
          )}

          {/* Translate button for top article */}
          {top_article && (
            <div className="px-4 pb-2">
              <TranslateButton article={top_article} locale={locale} />
            </div>
          )}

          {/* More articles */}
          {allArticles.length > 1 && (
            <div className="px-4 pb-3 space-y-1.5">
              {allArticles.slice(1, 4).map((article, i) => (
                <a
                  key={i}
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 py-1.5 px-2 rounded-lg hover:bg-[#1e293b] transition text-sm group"
                >
                  <Newspaper className="w-3.5 h-3.5 text-[#64748b] shrink-0" />
                  <span className="text-[#e2e8f0] group-hover:text-cyan-400 transition line-clamp-1 flex-1">
                    {article.title}
                  </span>
                  <span className="text-[10px] text-[#64748b] shrink-0">{article.source}</span>
                  {article.source_type === "il_news" && (
                    <span className="px-1 py-0.5 rounded bg-blue-500/20 text-blue-400 text-[9px] font-medium shrink-0">IL</span>
                  )}
                </a>
              ))}
            </div>
          )}

          {/* Stocks list */}
          <div className="px-4 pb-4 border-t border-[#1e293b]">
            <div className="py-2 text-xs text-[#64748b] font-medium">
              {locale === "he" ? "מניות קשורות" : "Related Stocks"}
            </div>
            <div className="space-y-1">
              {stocks.map((stock) => (
                <div
                  key={stock.ticker}
                  className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-[#1e293b] transition cursor-pointer"
                  onClick={() => {
                    trackInteraction({ interaction_type: "stock_click", target_slug: topic.slug });
                    onStockClick(stock.ticker);
                  }}
                >
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-semibold text-cyan-400 text-sm">{stock.ticker}</span>
                    <span className="text-sm text-white">{stock.company_name}</span>
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
        </div>
      )}
    </article>
  );
}

function IsraeliNewsSidebar({ items, locale }: { items: NewsItem[]; locale: string }) {
  if (items.length === 0) return null;

  return (
    <section className="bg-[#111827] rounded-xl border border-[#334155] p-4">
      <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-3">
        <Globe className="w-4 h-4 text-blue-400" />
        {locale === "he" ? "חדשות ישראל" : "Israel News"}
      </h3>
      <div className="space-y-3">
        {items.map((item, i) => (
          <a
            key={i}
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="block group"
          >
            <p className="text-sm text-[#e2e8f0] group-hover:text-cyan-400 transition line-clamp-2 leading-snug">
              {item.title}
            </p>
            <div className="flex items-center gap-2 mt-1 text-[10px] text-[#64748b]">
              <span className="px-1.5 py-0.5 rounded bg-blue-500/15 text-blue-400 font-medium">{item.source}</span>
              {item.published_at && <span>{timeAgo(item.published_at, locale)}</span>}
            </div>
          </a>
        ))}
      </div>
    </section>
  );
}

function GlobalNewsSidebar({ items, locale }: { items: NewsItem[]; locale: string }) {
  if (!items || items.length === 0) return null;

  return (
    <section className="bg-[#111827] rounded-xl border border-[#334155] p-4">
      <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-3">
        <Newspaper className="w-4 h-4 text-emerald-400" />
        {locale === "he" ? "חדשות גלובליות" : "Global News"}
      </h3>
      <div className="space-y-3">
        {items.map((item, i) => (
          <div key={i}>
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="block group"
            >
              <p className="text-sm text-[#e2e8f0] group-hover:text-emerald-400 transition line-clamp-2 leading-snug">
                {item.title}
              </p>
              <div className="flex items-center gap-2 mt-1 text-[10px] text-[#64748b]">
                <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 font-medium">{item.source}</span>
                {item.published_at && <span>{timeAgo(item.published_at, locale)}</span>}
              </div>
            </a>
            <TranslateButton article={item} locale={locale} />
          </div>
        ))}
      </div>
    </section>
  );
}

function PodcastsSidebar({ episodes, locale }: { episodes: PodcastEpisode[]; locale: string }) {
  if (episodes.length === 0) return null;

  return (
    <section className="bg-[#111827] rounded-xl border border-[#334155] p-4">
      <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-3">
        <Podcast className="w-4 h-4 text-purple-400" />
        {locale === "he" ? "פודקאסטים" : "Podcasts"}
      </h3>
      <div className="space-y-3">
        {episodes.map((ep, i) => (
          <a
            key={i}
            href={ep.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex gap-3 group"
          >
            {ep.image_url && (
              <img
                src={ep.image_url}
                alt=""
                className="w-12 h-12 rounded-lg object-cover shrink-0 bg-[#1e293b]"
                onError={(e) => (e.currentTarget.style.display = "none")}
              />
            )}
            <div className="flex-1 min-w-0">
              <p className="text-sm text-[#e2e8f0] group-hover:text-purple-400 transition line-clamp-2 leading-snug">
                {ep.title}
              </p>
              <div className="flex items-center gap-2 mt-1 text-[10px] text-[#64748b]">
                <span className="text-purple-400">{ep.podcast_name}</span>
                {ep.duration && <span>{ep.duration}</span>}
              </div>
            </div>
          </a>
        ))}
      </div>
    </section>
  );
}

function InstitutionalSidebar({ items, locale }: { items: InstitutionalItem[]; locale: string }) {
  if (!items || items.length === 0) return null;

  return (
    <section className="bg-[#111827] rounded-xl border border-[#334155] p-4">
      <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-3">
        <Building2 className="w-4 h-4 text-amber-400" />
        {locale === "he" ? "מוסדי" : "Institutional"}
      </h3>
      <div className="space-y-3">
        {items.slice(0, 6).map((item, i) => (
          <div key={i}>
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="block group"
            >
              <p className="text-sm text-[#e2e8f0] group-hover:text-amber-400 transition line-clamp-2 leading-snug">
                {item.title}
              </p>
              <div className="flex items-center gap-2 mt-1 text-[10px] text-[#64748b]">
                <span className="px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400 font-medium">{item.source}</span>
                {item.category && <span className="capitalize">{item.category}</span>}
                {item.published_at && <span>{timeAgo(item.published_at, locale)}</span>}
              </div>
            </a>
            <TranslateButton article={{ title: item.title, url: item.url, source: item.source, description: item.description, language: item.language } as NewsItem} locale={locale} />
          </div>
        ))}
      </div>
    </section>
  );
}

function BlogsSidebar({ items, locale }: { items: BlogPost[]; locale: string }) {
  if (!items || items.length === 0) return null;

  return (
    <section className="bg-[#111827] rounded-xl border border-[#334155] p-4">
      <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-3">
        <BookOpen className="w-4 h-4 text-rose-400" />
        {locale === "he" ? "בלוגים" : "Blogs"}
      </h3>
      <div className="space-y-3">
        {items.slice(0, 6).map((item, i) => (
          <div key={i}>
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="block group"
            >
              <p className="text-sm text-[#e2e8f0] group-hover:text-rose-400 transition line-clamp-2 leading-snug">
                {item.title}
              </p>
              <div className="flex items-center gap-2 mt-1 text-[10px] text-[#64748b]">
                <span className="px-1.5 py-0.5 rounded bg-rose-500/15 text-rose-400 font-medium">{item.source}</span>
                {item.published_at && <span>{timeAgo(item.published_at, locale)}</span>}
              </div>
            </a>
            <TranslateButton article={{ title: item.title, url: item.url, source: item.source, description: item.description, language: item.language } as NewsItem} locale={locale} />
          </div>
        ))}
      </div>
    </section>
  );
}

function TrendingTopicsSidebar({ market, locale }: { market: string; locale: string }) {
  const [topics, setTopics] = useState<TrendingTopic[]>([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const load = () => {
    if (topics.length > 0) {
      setExpanded(!expanded);
      return;
    }
    setLoading(true);
    getTrendingTopics({ market: market || undefined, limit: 10 })
      .then((data) => {
        setTopics(data.trending_topics);
        setExpanded(true);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  return (
    <section className="bg-[#111827] rounded-xl border border-[#334155] p-4">
      <button
        onClick={load}
        className="w-full flex items-center justify-between text-sm font-semibold text-white"
      >
        <span className="flex items-center gap-2">
          <Flame className="w-4 h-4 text-orange-400" />
          {locale === "he" ? "נושאים טרנדיים (הצלבת מקורות)" : "Trending Topics (Cross-Referenced)"}
        </span>
        {loading ? (
          <Loader2 className="w-4 h-4 animate-spin text-[#64748b]" />
        ) : expanded ? (
          <ChevronUp className="w-4 h-4 text-[#64748b]" />
        ) : (
          <ChevronDown className="w-4 h-4 text-[#64748b]" />
        )}
      </button>

      {expanded && topics.length > 0 && (
        <div className="mt-3 space-y-2">
          {topics.map((topic, i) => (
            <div
              key={i}
              className="p-2 rounded-lg bg-[#0f172a] border border-[#1e293b]"
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-white capitalize">{topic.topic}</span>
                <span className="text-xs font-mono text-orange-400">{topic.score}</span>
              </div>
              <div className="flex items-center gap-2 mt-1 text-[10px] text-[#64748b]">
                <span>{topic.mention_count} {locale === "he" ? "אזכורים" : "mentions"}</span>
                <span>•</span>
                <span>{topic.source_count} {locale === "he" ? "מקורות" : "sources"}</span>
              </div>
              {topic.articles.length > 0 && (
                <a
                  href={topic.articles[0].url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-1 text-[10px] text-[#94a3b8] hover:text-orange-400 line-clamp-1 block transition"
                >
                  {topic.articles[0].title}
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function NewsletterPanel({ market, locale }: { market: string; locale: string }) {
  const [newsletter, setNewsletter] = useState<Newsletter | null>(null);
  const [loading, setLoading] = useState(false);
  const [show, setShow] = useState(false);

  const handleGenerate = () => {
    if (newsletter) {
      setShow(!show);
      return;
    }
    setLoading(true);
    generateNewsletter({ language: locale, market: market || undefined })
      .then((data) => {
        setNewsletter(data);
        setShow(true);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  return (
    <section className="bg-[#111827] rounded-xl border border-[#334155] p-4">
      <button
        onClick={handleGenerate}
        className="w-full flex items-center justify-between text-sm font-semibold text-white"
      >
        <span className="flex items-center gap-2">
          <ScrollText className="w-4 h-4 text-cyan-400" />
          {locale === "he" ? "ניוזלטר שבועי" : "Weekly Newsletter"}
        </span>
        {loading ? (
          <Loader2 className="w-4 h-4 animate-spin text-cyan-400" />
        ) : show ? (
          <ChevronUp className="w-4 h-4 text-[#64748b]" />
        ) : (
          <span className="text-xs text-cyan-400 bg-cyan-500/10 px-2 py-0.5 rounded">
            {locale === "he" ? "צור" : "Generate"}
          </span>
        )}
      </button>

      {show && newsletter && (
        <div className="mt-3">
          {newsletter.ai_generated && (
            <div className="flex items-center gap-2 mb-2 text-[10px] text-[#64748b]">
              <span className="px-1.5 py-0.5 rounded bg-cyan-500/15 text-cyan-400 font-medium">AI</span>
              <span>
                {locale === "he" ? "מבוסס על" : "Based on"} {newsletter.source_count} {locale === "he" ? "מקורות" : "sources"},
                {" "}{newsletter.total_mentions} {locale === "he" ? "אזכורים" : "mentions"}
              </span>
            </div>
          )}
          <div className="prose prose-sm prose-invert max-w-none text-sm text-[#e2e8f0] leading-relaxed whitespace-pre-wrap">
            {newsletter.newsletter}
          </div>
        </div>
      )}
    </section>
  );
}

export default function TrendFeed({ onStockClick, isWatched, toggleWatch }: Props) {
  const { locale, t } = useI18n();
  const [feed, setFeed] = useState<UnifiedFeed | null>(null);
  const [sector, setSector] = useState("");
  const [market, setMarket] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getFeed({
      sector: sector || undefined,
      market: market || undefined,
    })
      .then(setFeed)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [sector, market]);

  return (
    <div className="space-y-4">
      {/* Market Region Filter */}
      <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
        {MARKETS.map((m) => (
          <button
            key={m.key}
            onClick={() => setMarket(m.key)}
            className={`whitespace-nowrap px-3 py-1.5 rounded-full text-sm font-medium transition flex items-center gap-1.5 ${
              market === m.key
                ? "bg-gradient-to-r from-cyan-500 to-blue-500 text-white shadow-md shadow-cyan-500/20"
                : "bg-[#1e293b] text-[#94a3b8] hover:bg-[#334155]"
            }`}
          >
            <span>{m.icon}</span>
            {locale === "he" ? m.he : m.en}
          </button>
        ))}
      </div>

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

      {loading ? (
        <div className="text-center py-12 text-[#94a3b8]">{t("general.loading")}</div>
      ) : !feed || feed.feed.length === 0 ? (
        <div className="text-center py-12 text-[#94a3b8]">{t("dashboard.noTopics")}</div>
      ) : (
        <div className="flex gap-6">
          {/* Main Feed — single column */}
          <div className="flex-1 min-w-0 space-y-4">
            {feed.feed.map((item, i) => (
              <FeedCard
                key={item.topic.slug}
                item={item}
                onStockClick={onStockClick}
                isWatched={isWatched}
                toggleWatch={toggleWatch}
                locale={locale}
                isTopMover={i < 2 && item.topic.direction === "rising"}
              />
            ))}
          </div>

          {/* Sidebar (desktop only) */}
          <aside className="hidden lg:block w-72 shrink-0 space-y-4">
            {/* Trending Topics — cross-referenced */}
            <TrendingTopicsSidebar market={market} locale={locale} />

            {/* Newsletter */}
            <NewsletterPanel market={market} locale={locale} />

            <IsraeliNewsSidebar items={feed.il_news_general} locale={locale} />
            <GlobalNewsSidebar items={feed.global_news_general || []} locale={locale} />
            <InstitutionalSidebar items={feed.institutional || []} locale={locale} />
            <BlogsSidebar items={feed.blogs || []} locale={locale} />
            <PodcastsSidebar episodes={feed.podcasts} locale={locale} />
          </aside>
        </div>
      )}

      {/* Mobile: Sidebars below feed */}
      {!loading && feed && (
        <div className="lg:hidden space-y-4">
          <TrendingTopicsSidebar market={market} locale={locale} />
          <NewsletterPanel market={market} locale={locale} />
          <IsraeliNewsSidebar items={feed.il_news_general} locale={locale} />
          <GlobalNewsSidebar items={feed.global_news_general || []} locale={locale} />
          <InstitutionalSidebar items={feed.institutional || []} locale={locale} />
          <BlogsSidebar items={feed.blogs || []} locale={locale} />
          <PodcastsSidebar episodes={feed.podcasts} locale={locale} />
        </div>
      )}
    </div>
  );
}
