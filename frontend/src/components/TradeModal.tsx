"use client";
import { useState, useEffect } from "react";
import { useI18n } from "@/i18n/context";
import { X, AlertTriangle } from "lucide-react";
import type { Holding } from "@/lib/types";

interface Props {
  initialTicker: string;
  onExecute: (ticker: string, action: "buy" | "sell", quantity: number) => Promise<void>;
  onClose: () => void;
  cashBalance: number;
  holdings: Holding[];
}

export default function TradeModal({ initialTicker, onExecute, onClose, cashBalance, holdings }: Props) {
  const { t } = useI18n();
  const [ticker, setTicker] = useState(initialTicker);
  const [action, setAction] = useState<"buy" | "sell">("buy");
  const [quantity, setQuantity] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [estimatedPrice, setEstimatedPrice] = useState<number | null>(null);

  // Fetch current price for estimate
  useEffect(() => {
    if (!ticker.trim()) {
      setEstimatedPrice(null);
      return;
    }
    const timer = setTimeout(() => {
      fetch(`/api/stocks/${ticker.toUpperCase()}`)
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => {
          if (data?.current_price) setEstimatedPrice(data.current_price);
          else setEstimatedPrice(null);
        })
        .catch(() => setEstimatedPrice(null));
    }, 300);
    return () => clearTimeout(timer);
  }, [ticker]);

  const estimatedTotal = estimatedPrice ? estimatedPrice * quantity : null;
  const insufficientFunds = action === "buy" && estimatedTotal !== null && estimatedTotal > cashBalance;

  // Find holding for sell info
  const currentHolding = holdings.find((h) => h.ticker === ticker.toUpperCase());

  const handleSubmit = async () => {
    if (!ticker.trim()) return;
    setLoading(true);
    setError("");
    try {
      await onExecute(ticker.toUpperCase(), action, quantity);
    } catch (e: any) {
      setError(e.message || "Trade failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-end md:items-center justify-center">
      <div className="w-full max-w-md bg-[#111827] rounded-t-2xl md:rounded-2xl border border-[#334155] p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-bold text-white">{t("trade.execute")}</h2>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-[#1e293b]">
            <X className="w-5 h-5 text-[#94a3b8]" />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="text-sm text-[#94a3b8] mb-1 block">Ticker</label>
            <input
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              placeholder="NVDA"
              className="w-full px-3 py-2 bg-[#1e293b] border border-[#334155] rounded-lg text-white font-mono focus:outline-none focus:border-cyan-500"
            />
          </div>

          <div>
            <label className="text-sm text-[#94a3b8] mb-1 block">Action</label>
            <div className="flex gap-2">
              <button
                onClick={() => setAction("buy")}
                className={`flex-1 py-2 rounded-lg font-medium transition ${
                  action === "buy"
                    ? "bg-green-500 text-white"
                    : "bg-[#1e293b] text-[#94a3b8] hover:bg-[#334155]"
                }`}
              >
                {t("trade.buy")}
              </button>
              <button
                onClick={() => setAction("sell")}
                className={`flex-1 py-2 rounded-lg font-medium transition ${
                  action === "sell"
                    ? "bg-red-500 text-white"
                    : "bg-[#1e293b] text-[#94a3b8] hover:bg-[#334155]"
                }`}
              >
                {t("trade.sell")}
              </button>
            </div>
          </div>

          <div>
            <label className="text-sm text-[#94a3b8] mb-1 block">{t("trade.quantity")}</label>
            <input
              type="number"
              value={quantity}
              onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value) || 1))}
              min={1}
              className="w-full px-3 py-2 bg-[#1e293b] border border-[#334155] rounded-lg text-white font-mono focus:outline-none focus:border-cyan-500"
            />
          </div>

          {/* Estimated Total */}
          {estimatedTotal !== null && (
            <div className="bg-[#0f172a] rounded-lg p-3 space-y-1">
              <div className="flex justify-between text-sm">
                <span className="text-[#94a3b8]">{t("trade.estimatedTotal" as any)}</span>
                <span className="font-mono text-white tabular-nums">
                  ${estimatedTotal.toFixed(2)}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-[#94a3b8]">{t("trade.availableCash" as any)}</span>
                <span className="font-mono text-white tabular-nums">
                  ${cashBalance.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </span>
              </div>
            </div>
          )}

          {/* Insufficient funds warning */}
          {insufficientFunds && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 flex gap-2">
              <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
              <p className="text-xs text-red-300">{t("trade.insufficientFunds" as any)}</p>
            </div>
          )}

          {/* Current shares held (for sell) */}
          {action === "sell" && currentHolding && (
            <div className="text-sm text-[#94a3b8]">
              {t("trade.currentShares" as any)}:{" "}
              <span className="text-white font-mono">{currentHolding.quantity}</span>
            </div>
          )}

          {/* Cash display (when no estimated total) */}
          {estimatedTotal === null && (
            <div className="text-sm text-[#94a3b8]">
              {t("trade.cash")}:{" "}
              <span className="text-white font-mono tabular-nums">
                ${cashBalance.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </span>
            </div>
          )}

          {error && (
            <div className="text-sm text-red-400 bg-red-400/10 rounded-lg p-2">{error}</div>
          )}

          <button
            onClick={handleSubmit}
            disabled={loading || !ticker.trim() || insufficientFunds}
            className="w-full py-3 bg-cyan-500 hover:bg-cyan-600 disabled:opacity-50 text-white font-semibold rounded-xl transition"
          >
            {loading ? "..." : `${action === "buy" ? t("trade.buy") : t("trade.sell")} ${quantity}x ${ticker || "..."}`}
          </button>

          {/* Footer disclaimer */}
          <p className="text-[10px] text-[#64748b] text-center">
            {t("trade.paperDisclaimer" as any)}
          </p>
        </div>
      </div>
    </div>
  );
}
