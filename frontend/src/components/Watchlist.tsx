"use client";
import { useState, useEffect } from "react";
import { useI18n } from "@/i18n/context";
import type { StockDetail } from "@/lib/types";
import { Star, Trash2 } from "lucide-react";

interface Props {
  watchlist: string[];
  removeTicker: (ticker: string) => void;
  onStockClick: (ticker: string) => void;
}

export default function Watchlist({ watchlist, removeTicker, onStockClick }: Props) {
  const { t } = useI18n();
  const [stocks, setStocks] = useState<StockDetail[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (watchlist.length === 0) {
      setStocks([]);
      return;
    }
    setLoading(true);
    // Fetch each stock individually
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

  const totalChange =
    stocks.length > 0
      ? stocks.reduce((sum, s) => sum + (s.daily_change_pct || 0), 0) / stocks.length
      : 0;

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-white">{t("watchlist.title")}</h2>

      {/* Summary */}
      {stocks.length > 0 && (
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
      )}
    </div>
  );
}
