"use client";
import { useState, useEffect, useCallback } from "react";
import { useI18n } from "@/i18n/context";
import { getPortfolio, getTradeHistory, executeTrade, getSessionId } from "@/lib/api";
import type { Portfolio, TradeHistoryItem } from "@/lib/types";
import { AlertTriangle, TrendingUp, TrendingDown, DollarSign } from "lucide-react";
import TradeModal from "./TradeModal";

interface Props {
  onStockClick: (ticker: string) => void;
}

export default function PaperTrading({ onStockClick }: Props) {
  const { t } = useI18n();
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [history, setHistory] = useState<TradeHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [tradeModalOpen, setTradeModalOpen] = useState(false);
  const [selectedTicker, setSelectedTicker] = useState("");
  const sessionId = typeof window !== "undefined" ? getSessionId() : "";

  const loadData = useCallback(() => {
    if (!sessionId) return;
    Promise.all([getPortfolio(sessionId), getTradeHistory(sessionId)])
      .then(([p, h]) => {
        setPortfolio(p);
        setHistory(h);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [sessionId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleTrade = async (ticker: string, action: "buy" | "sell", quantity: number) => {
    await executeTrade({ session_id: sessionId, ticker, action, quantity });
    setTradeModalOpen(false);
    loadData();
  };

  if (loading) {
    return <div className="text-center py-12 text-[#94a3b8]">{t("general.loading")}</div>;
  }

  return (
    <div className="space-y-6">
      {/* Disclaimer */}
      <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4 flex gap-3">
        <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
        <p className="text-sm text-yellow-200">{t("trade.disclaimer")}</p>
      </div>

      {/* Portfolio Summary */}
      {portfolio && (
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-[#111827] rounded-xl border border-[#334155] p-4">
            <div className="text-xs text-[#94a3b8] mb-1">{t("trade.cash")}</div>
            <div className="font-mono font-bold text-white tabular-nums">
              ${portfolio.cash_balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </div>
          </div>
          <div className="bg-[#111827] rounded-xl border border-[#334155] p-4">
            <div className="text-xs text-[#94a3b8] mb-1">{t("trade.totalValue")}</div>
            <div className="font-mono font-bold text-white tabular-nums">
              ${portfolio.total_value.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </div>
          </div>
          <div className="bg-[#111827] rounded-xl border border-[#334155] p-4">
            <div className="text-xs text-[#94a3b8] mb-1">{t("trade.pnl")}</div>
            <div
              className={`font-mono font-bold tabular-nums ${
                portfolio.total_pnl >= 0 ? "text-green-400" : "text-red-400"
              }`}
            >
              {portfolio.total_pnl >= 0 ? "+" : ""}$
              {portfolio.total_pnl.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </div>
          </div>
        </div>
      )}

      {/* Trade Button */}
      <button
        onClick={() => {
          setSelectedTicker("");
          setTradeModalOpen(true);
        }}
        className="w-full py-3 bg-cyan-500 hover:bg-cyan-600 text-white font-semibold rounded-xl transition"
      >
        {t("trade.startTrading")}
      </button>

      {/* Holdings */}
      <div>
        <h3 className="text-sm font-semibold text-[#94a3b8] uppercase tracking-wider mb-3">
          {t("trade.holdings")}
        </h3>
        {!portfolio || portfolio.holdings.length === 0 ? (
          <div className="text-center py-8 text-[#94a3b8] bg-[#111827] rounded-xl border border-[#334155]">
            {t("trade.noHoldings")}
          </div>
        ) : (
          <div className="space-y-2">
            {portfolio.holdings.map((h) => (
              <div
                key={h.ticker}
                onClick={() => onStockClick(h.ticker)}
                className="flex items-center gap-4 p-4 bg-[#111827] rounded-xl border border-[#334155] hover:border-cyan-500/30 transition cursor-pointer"
              >
                <div className="flex-1">
                  <div className="font-mono font-bold text-cyan-400">{h.ticker}</div>
                  <div className="text-xs text-[#94a3b8]">
                    {h.quantity} shares @ ${h.avg_cost.toFixed(2)}
                  </div>
                </div>
                <div className="text-end">
                  <div className="font-mono text-white tabular-nums">
                    ${(h.market_value || 0).toFixed(2)}
                  </div>
                  <div
                    className={`text-sm tabular-nums ${
                      (h.pnl || 0) >= 0 ? "text-green-400" : "text-red-400"
                    }`}
                  >
                    {(h.pnl || 0) >= 0 ? "+" : ""}${(h.pnl || 0).toFixed(2)} (
                    {(h.pnl_pct || 0).toFixed(1)}%)
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Trade History */}
      {history.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-[#94a3b8] uppercase tracking-wider mb-3">
            {t("trade.history")}
          </h3>
          <div className="space-y-2">
            {history.slice(0, 10).map((trade, i) => (
              <div
                key={i}
                className="flex items-center justify-between p-3 bg-[#111827] rounded-lg border border-[#334155]"
              >
                <div className="flex items-center gap-3">
                  {trade.action === "buy" ? (
                    <TrendingUp className="w-4 h-4 text-green-400" />
                  ) : (
                    <TrendingDown className="w-4 h-4 text-red-400" />
                  )}
                  <div>
                    <span className="font-mono font-semibold text-white">{trade.ticker}</span>
                    <span className="text-xs text-[#94a3b8] ms-2">
                      {trade.action.toUpperCase()} x{trade.quantity}
                    </span>
                  </div>
                </div>
                <div className="text-end">
                  <div className="text-sm font-mono text-white tabular-nums">
                    ${trade.total.toFixed(2)}
                  </div>
                  <div className="text-xs text-[#94a3b8]">
                    @ ${trade.price.toFixed(2)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tradeModalOpen && (
        <TradeModal
          initialTicker={selectedTicker}
          onExecute={handleTrade}
          onClose={() => setTradeModalOpen(false)}
          cashBalance={portfolio?.cash_balance || 0}
        />
      )}
    </div>
  );
}
