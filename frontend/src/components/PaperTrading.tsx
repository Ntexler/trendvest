"use client";
import { useState, useEffect, useCallback } from "react";
import { useI18n } from "@/i18n/context";
import { getPortfolio, getTradeHistory, executeTrade, getSessionId, getTrends } from "@/lib/api";
import type { Portfolio, TradeHistoryItem, TrendTopic } from "@/lib/types";
import { AlertTriangle, TrendingUp, TrendingDown, DollarSign, Zap } from "lucide-react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";
import TradeModal from "./TradeModal";
import Term from "./Term";

interface Props {
  onStockClick: (ticker: string) => void;
}

const PIE_COLORS = ["#22d3ee", "#a78bfa", "#4ade80", "#f97316", "#f43f5e", "#facc15", "#818cf8", "#2dd4bf"];

export default function PaperTrading({ onStockClick }: Props) {
  const { t, locale } = useI18n();
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [history, setHistory] = useState<TradeHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [tradeModalOpen, setTradeModalOpen] = useState(false);
  const [selectedTicker, setSelectedTicker] = useState("");
  const [hotStocks, setHotStocks] = useState<{ ticker: string; name: string; change: number | null }[]>([]);
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

  // Load hot stocks from top trends
  useEffect(() => {
    getTrends()
      .then((trends) => {
        const stocks: { ticker: string; name: string; change: number | null }[] = [];
        for (const trend of trends.slice(0, 3)) {
          for (const s of trend.stocks.slice(0, 2)) {
            if (stocks.length < 6 && !stocks.find((x) => x.ticker === s.ticker)) {
              stocks.push({ ticker: s.ticker, name: s.company_name, change: s.daily_change_pct });
            }
          }
        }
        setHotStocks(stocks);
      })
      .catch(() => {});
  }, []);

  const handleTrade = async (ticker: string, action: "buy" | "sell", quantity: number) => {
    await executeTrade({ session_id: sessionId, ticker, action, quantity });
    setTradeModalOpen(false);
    loadData();
  };

  // Pie chart data
  const pieData =
    portfolio && portfolio.holdings.length > 0
      ? [
          ...portfolio.holdings.map((h) => ({
            name: h.ticker,
            value: h.market_value || h.quantity * h.avg_cost,
          })),
          { name: t("trade.cashSlice" as any), value: portfolio.cash_balance },
        ]
      : [];

  if (loading) {
    return <div className="text-center py-12 text-[#94a3b8]">{t("general.loading")}</div>;
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-white">
        <Term termKey="paper-trading">{t("trade.title")}</Term>
      </h2>

      {/* Disclaimer */}
      <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4 flex gap-3">
        <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
        <p className="text-sm text-amber-200">{t("trade.disclaimerStrong" as any)}</p>
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

      {/* Portfolio Pie Chart */}
      {pieData.length > 0 && (
        <div className="bg-[#111827] rounded-xl border border-[#334155] p-4">
          <h3 className="text-sm font-semibold text-[#94a3b8] uppercase tracking-wider mb-3">
            {t("trade.allocation" as any)}
          </h3>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={80}
                dataKey="value"
                paddingAngle={2}
              >
                {pieData.map((_, i) => (
                  <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: "#1e293b",
                  border: "1px solid #334155",
                  borderRadius: "8px",
                  color: "#fff",
                  fontSize: "12px",
                }}
                formatter={(value: number) => [`$${value.toFixed(2)}`, ""]}
              />
              <Legend
                formatter={(value: string) => (
                  <span className="text-xs text-[#94a3b8]">{value}</span>
                )}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Quick Buy Grid */}
      {hotStocks.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-[#94a3b8] uppercase tracking-wider mb-3 flex items-center gap-2">
            <Zap className="w-4 h-4 text-amber-400" />
            {t("trade.quickBuy" as any)}
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {hotStocks.map((stock) => (
              <button
                key={stock.ticker}
                onClick={() => {
                  setSelectedTicker(stock.ticker);
                  setTradeModalOpen(true);
                }}
                className="bg-[#111827] rounded-xl border border-[#334155] p-3 text-start hover:border-cyan-500/30 transition"
              >
                <div className="font-mono text-sm font-bold text-cyan-400">{stock.ticker}</div>
                <div className="text-xs text-[#94a3b8] truncate mt-0.5">{stock.name}</div>
                {stock.change !== null && (
                  <div
                    className={`text-xs font-mono mt-1 tabular-nums ${
                      stock.change >= 0 ? "text-green-400" : "text-red-400"
                    }`}
                  >
                    {stock.change >= 0 ? "+" : ""}
                    {stock.change.toFixed(2)}%
                  </div>
                )}
              </button>
            ))}
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
          holdings={portfolio?.holdings || []}
        />
      )}
    </div>
  );
}
