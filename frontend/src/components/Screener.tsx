"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import { useI18n } from "@/i18n/context";
import { useMode } from "@/contexts/ModeContext";
import { getStocks, getTrends } from "@/lib/api";
import type { StockDetail, TrendTopic } from "@/lib/types";
import { Search, Star, ChevronRight, X } from "lucide-react";

interface Props {
  onStockClick: (ticker: string) => void;
  isWatched: (ticker: string) => boolean;
  toggleWatch: (ticker: string) => void;
}

export default function Screener({ onStockClick, isWatched, toggleWatch }: Props) {
  const { locale, t } = useI18n();
  const { isBeginner } = useMode();
  const [stocks, setStocks] = useState<StockDetail[]>([]);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [sortBy, setSortBy] = useState("change");
  const [loading, setLoading] = useState(true);
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [selectedTopic, setSelectedTopic] = useState("");
  const [topics, setTopics] = useState<TrendTopic[]>([]);

  // Autocomplete state
  const [showAutocomplete, setShowAutocomplete] = useState(false);
  const [acIndex, setAcIndex] = useState(-1);
  const searchRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getTrends().then(setTopics).catch(() => {});
  }, []);

  // Debounce search input (300ms)
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    setLoading(true);
    getStocks({
      search: debouncedSearch || undefined,
      sort_by: sortBy,
      min_price: minPrice ? parseFloat(minPrice) : undefined,
      max_price: maxPrice ? parseFloat(maxPrice) : undefined,
      topic: selectedTopic || undefined,
    })
      .then(setStocks)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [debouncedSearch, sortBy, minPrice, maxPrice, selectedTopic]);

  // Autocomplete suggestions
  const acQuery = search.trim().toLowerCase();
  const suggestions = acQuery.length >= 1
    ? stocks
        .filter(
          (s) =>
            s.ticker.toLowerCase().startsWith(acQuery) ||
            s.company_name.toLowerCase().includes(acQuery)
        )
        .slice(0, 8)
    : [];

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(e.target.value);
    setShowAutocomplete(true);
    setAcIndex(-1);
  };

  const selectSuggestion = useCallback(
    (ticker: string) => {
      setSearch(ticker);
      setShowAutocomplete(false);
      onStockClick(ticker);
    },
    [onStockClick]
  );

  const handleSearchKeyDown = (e: React.KeyboardEvent) => {
    if (!showAutocomplete || suggestions.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setAcIndex((prev) => (prev + 1) % suggestions.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setAcIndex((prev) => (prev <= 0 ? suggestions.length - 1 : prev - 1));
    } else if (e.key === "Enter" && acIndex >= 0) {
      e.preventDefault();
      selectSuggestion(suggestions[acIndex].ticker);
    } else if (e.key === "Escape") {
      setShowAutocomplete(false);
    }
  };

  // Click outside to close autocomplete
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowAutocomplete(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-white">{t("screener.title")}</h2>

      {/* Search + Sort row */}
      <div className="flex gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]" ref={searchRef}>
          <Search className="absolute start-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#94a3b8]" />
          <input
            type="text"
            placeholder={t("screener.search")}
            value={search}
            onChange={handleSearchChange}
            onFocus={() => setShowAutocomplete(true)}
            onKeyDown={handleSearchKeyDown}
            className="w-full ps-10 pe-9 py-2 bg-[#1e293b] border border-[#334155] rounded-lg text-white placeholder-[#94a3b8] focus:outline-none focus:border-cyan-500"
          />
          {/* Clear button */}
          {search && (
            <button
              onClick={() => {
                setSearch("");
                setShowAutocomplete(false);
              }}
              className="absolute end-3 top-1/2 -translate-y-1/2 p-0.5 text-[#94a3b8] hover:text-white transition"
            >
              <X className="w-4 h-4" />
            </button>
          )}
          {/* Autocomplete dropdown */}
          {showAutocomplete && suggestions.length > 0 && acQuery.length >= 1 && (
            <div className="absolute z-50 top-full mt-1 w-full bg-[#1e293b] border border-[#334155] rounded-lg shadow-xl overflow-hidden">
              {suggestions.map((s, i) => (
                <button
                  key={s.ticker}
                  onClick={() => selectSuggestion(s.ticker)}
                  className={`w-full flex items-center gap-3 px-3 py-2 text-start transition ${
                    i === acIndex ? "bg-[#334155]" : "hover:bg-[#263548]"
                  }`}
                >
                  <span className="font-mono text-sm font-bold text-cyan-400">{s.ticker}</span>
                  <span className="text-sm text-[#94a3b8] truncate">{s.company_name}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className="px-3 py-2 bg-[#1e293b] border border-[#334155] rounded-lg text-white focus:outline-none focus:border-cyan-500"
        >
          <option value="change">{t("stock.change")}</option>
          <option value="price">{t("stock.price")}</option>
          <option value="name">A-Z</option>
        </select>
      </div>

      {/* Filters row: price range + topic (hidden for beginners) */}
      {!isBeginner && (
        <div className="flex gap-3 flex-wrap items-center">
          <input
            type="number"
            placeholder={t("screener.minPrice")}
            value={minPrice}
            onChange={(e) => setMinPrice(e.target.value)}
            className="w-28 px-3 py-2 bg-[#1e293b] border border-[#334155] rounded-lg text-white placeholder-[#94a3b8] text-sm focus:outline-none focus:border-cyan-500"
          />
          <span className="text-[#64748b] text-sm">&mdash;</span>
          <input
            type="number"
            placeholder={t("screener.maxPrice")}
            value={maxPrice}
            onChange={(e) => setMaxPrice(e.target.value)}
            className="w-28 px-3 py-2 bg-[#1e293b] border border-[#334155] rounded-lg text-white placeholder-[#94a3b8] text-sm focus:outline-none focus:border-cyan-500"
          />
          <select
            value={selectedTopic}
            onChange={(e) => setSelectedTopic(e.target.value)}
            className="px-3 py-2 bg-[#1e293b] border border-[#334155] rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500"
          >
            <option value="">{t("screener.allTopics")}</option>
            {topics.map((topic) => (
              <option key={topic.slug} value={topic.slug}>
                {locale === "he" ? topic.name_he : topic.name_en}
              </option>
            ))}
          </select>
          {(minPrice || maxPrice || selectedTopic) && (
            <button
              onClick={() => {
                setMinPrice("");
                setMaxPrice("");
                setSelectedTopic("");
              }}
              className="p-2 text-[#94a3b8] hover:text-white transition"
              title="Clear filters"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-[#94a3b8]">{t("general.loading")}</div>
      ) : (
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
                <p className="text-xs text-[#94a3b8] mt-0.5">
                  {stock.topic} · {locale === "he" ? stock.sector : stock.sector}
                </p>
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
                  toggleWatch(stock.ticker);
                }}
                className="p-1"
              >
                <Star
                  className={`w-5 h-5 ${
                    isWatched(stock.ticker)
                      ? "fill-yellow-400 text-yellow-400"
                      : "text-[#94a3b8] hover:text-yellow-400"
                  }`}
                />
              </button>
              <ChevronRight className="w-4 h-4 text-[#94a3b8]" />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
