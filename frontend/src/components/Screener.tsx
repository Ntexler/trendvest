"use client";
import { useState, useEffect } from "react";
import { useI18n } from "@/i18n/context";
import { getStocks } from "@/lib/api";
import type { StockDetail } from "@/lib/types";
import { Search, Star, ChevronRight } from "lucide-react";

interface Props {
  onStockClick: (ticker: string) => void;
  isWatched: (ticker: string) => boolean;
  toggleWatch: (ticker: string) => void;
}

export default function Screener({ onStockClick, isWatched, toggleWatch }: Props) {
  const { locale, t } = useI18n();
  const [stocks, setStocks] = useState<StockDetail[]>([]);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("change");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getStocks({ search: search || undefined, sort_by: sortBy })
      .then(setStocks)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [search, sortBy]);

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-white">{t("screener.title")}</h2>

      <div className="flex gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute start-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#94a3b8]" />
          <input
            type="text"
            placeholder={t("screener.search")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full ps-10 pe-4 py-2 bg-[#1e293b] border border-[#334155] rounded-lg text-white placeholder-[#94a3b8] focus:outline-none focus:border-cyan-500"
          />
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
